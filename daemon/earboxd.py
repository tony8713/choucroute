#!/usr/bin/env python3
"""
earboxd - the earbox capture -> transcribe -> memory daemon.

Privacy invariants enforced here (see docs/architecture.md):
  1. Raw audio is written only to a tmpfs scratch path and DELETED immediately
     after transcription. It is never persisted to disk-at-rest, never sent
     off-device.
  2. Only text (transcripts) is written to the owner's git-backed memory.
  3. A physical mute switch (GPIO on the Pi) or a mute flag file gates capture:
     when muted, no audio is captured at all.
  4. Nothing leaves the device from this process. Egress (daily summary to the
     owner's agent) is a separate, text-only step (summarize.py).

The daemon is source-agnostic. On the Pi the source is `arecord`; on a Mac dev
box it is `ffmpeg`/avfoundation; in tests it is a wav file replayed as chunks.
"""

import argparse
import array
import datetime as dt
import math
import os
import re
import shutil
import subprocess
import sys
import tomllib
import wave
from pathlib import Path

# ---- config -----------------------------------------------------------------

DEFAULTS = {
    "segment_seconds": 30,
    "sample_rate": 16000,
    "model_path": os.path.expanduser("~/.whisper-models/ggml-base.bin"),
    "language": "fr",
    "whisper_bin": "whisper-cli",
    "whisper_threads": 4,
    "memory_repo": os.path.expanduser("~/earbox-memory"),
    "scratch_dir": "/dev/shm/earbox",          # tmpfs on Linux -> never hits disk
    "vad_rms_threshold": 0.012,                 # 0..1, skip chunks quieter than this
    "vad_min_voiced_ratio": 0.06,               # >=6% of frames must be "loud"
    "mute_flag": os.path.expanduser("~/.earbox-muted"),
    "gpio_mute_pin": 0,                          # 0 = disabled; else BCM pin number
    "auto_commit": True,
    "keep_debug_audio": False,                   # MUST stay false in production
}

# whisper on silence/noise hallucinates these; drop them.
HALLUCINATIONS = {
    "", "[blank_audio]", "[ silence ]", "[silence]", "(silence)",
    "merci", "merci.", "sous-titres réalisés par la communauté d'amara.org",
    "sous-titrage société radio-canada", "thank you.", "thanks for watching!",
    "you", "so", ".", "...", "[music]", "(applause)", "[applause]", "♪",
}


def load_config(path):
    cfg = dict(DEFAULTS)
    if path and Path(path).exists():
        with open(path, "rb") as f:
            cfg.update(tomllib.load(f))
    return cfg


# ---- mute -------------------------------------------------------------------

def is_muted(cfg):
    if Path(cfg["mute_flag"]).exists():
        return True
    pin = int(cfg.get("gpio_mute_pin") or 0)
    if pin:
        try:
            import gpiozero  # only present on the Pi
            btn = _gpio_button(pin)
            return btn.is_pressed  # switch closed == muted
        except Exception:
            return False
    return False


_GPIO_CACHE = {}
def _gpio_button(pin):
    if pin not in _GPIO_CACHE:
        from gpiozero import Button
        _GPIO_CACHE[pin] = Button(pin, pull_up=True)
    return _GPIO_CACHE[pin]


# ---- capture ----------------------------------------------------------------

def capture_arecord(cfg, out_path):
    subprocess.run(
        ["arecord", "-q", "-D", cfg.get("alsa_device", "default"),
         "-f", "S16_LE", "-r", str(cfg["sample_rate"]), "-c", "1",
         "-d", str(cfg["segment_seconds"]), str(out_path)],
        check=True,
    )


def capture_ffmpeg(cfg, out_path):
    # macOS dev harness: :0 is the default avfoundation audio input.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "avfoundation",
         "-i", cfg.get("av_device", ":0"), "-t", str(cfg["segment_seconds"]),
         "-ar", str(cfg["sample_rate"]), "-ac", "1", "-c:a", "pcm_s16le",
         str(out_path)],
        check=True,
    )


# ---- VAD (energy based, dependency-free) ------------------------------------

def rms_voiced_ratio(wav_path, frame_ms=30):
    """Return (overall_rms_0_1, voiced_frame_ratio). Pure stdlib."""
    with wave.open(str(wav_path), "rb") as w:
        assert w.getsampwidth() == 2, "expect 16-bit PCM"
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    if not raw:
        return 0.0, 0.0
    samples = array.array("h")
    samples.frombytes(raw)
    n = len(samples)
    if n == 0:
        return 0.0, 0.0
    total_sq = sum(s * s for s in samples)
    overall = math.sqrt(total_sq / n) / 32768.0
    fs = max(1, int(rate * frame_ms / 1000))
    loud = 0
    frames = 0
    thr = 0.02  # per-frame loudness gate
    for i in range(0, n - fs, fs):
        frames += 1
        seg = samples[i:i + fs]
        fr = math.sqrt(sum(s * s for s in seg) / len(seg)) / 32768.0
        if fr > thr:
            loud += 1
    ratio = loud / frames if frames else 0.0
    return overall, ratio


def has_speech(cfg, wav_path):
    overall, ratio = rms_voiced_ratio(wav_path)
    return overall >= cfg["vad_rms_threshold"] and ratio >= cfg["vad_min_voiced_ratio"]


# ---- transcription ----------------------------------------------------------

def transcribe(cfg, wav_path):
    proc = subprocess.run(
        [cfg["whisper_bin"], "-m", cfg["model_path"], "-l", cfg["language"],
         "-t", str(cfg["whisper_threads"]), "-nt", "-f", str(wav_path)],
        capture_output=True, text=True, check=True,
    )
    return clean_transcript(proc.stdout)


def clean_transcript(text):
    lines = [ln.strip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        norm = ln.lower().strip()
        norm = re.sub(r"\s+", " ", norm)
        if norm in HALLUCINATIONS:
            continue
        # drop pure bracket/paren tags like [_BEG_], (wind blowing)
        if re.fullmatch(r"[\[\(].*[\]\)]", norm):
            continue
        if ln:
            out.append(ln)
    joined = " ".join(out).strip()
    # collapse whisper's degenerate repetition loops
    joined = re.sub(r"(\b\w+\b)( \1){3,}", r"\1", joined)
    return joined


# ---- memory (git-backed) ----------------------------------------------------

def ensure_repo(cfg):
    repo = Path(cfg["memory_repo"])
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        _git_identity(repo)
        gi = repo / ".gitignore"
        gi.write_text("*.wav\n*.aiff\n*.raw\n*.pcm\n")  # never commit audio
        (repo / "README.md").write_text(
            "# earbox memory\n\nText transcripts only. No audio ever lives here.\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init earbox memory"],
                       cwd=repo, check=True)
    return repo


def _git_identity(repo):
    subprocess.run(["git", "config", "user.name", "earbox"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "earbox@localhost"],
                   cwd=repo, check=True)


def append_transcript(cfg, repo, text, when=None):
    when = when or dt.datetime.now()
    day = when.strftime("%Y-%m-%d")
    daydir = repo / "transcripts"
    daydir.mkdir(exist_ok=True)
    md = daydir / f"{day}.md"
    if not md.exists():
        md.write_text(f"# {day}\n\n")
    with open(md, "a") as f:
        f.write(f"- **{when.strftime('%H:%M')}** {text}\n")
    if cfg["auto_commit"]:
        subprocess.run(["git", "add", str(md)], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"transcript {when.strftime('%Y-%m-%d %H:%M')}"],
            cwd=repo, check=True,
        )
    return md


# ---- main loop --------------------------------------------------------------

def process_segment(cfg, repo, wav_path, when=None):
    """VAD -> transcribe -> memory -> DELETE. Returns transcript text or None."""
    text = None
    try:
        if not has_speech(cfg, wav_path):
            return None
        text = transcribe(cfg, wav_path)
        if not text:
            return None
        append_transcript(cfg, repo, text, when)
        return text
    finally:
        # PRIVACY INVARIANT: raw audio is destroyed no matter what.
        if not cfg["keep_debug_audio"]:
            try:
                os.remove(wav_path)
            except FileNotFoundError:
                pass


def run(cfg, source):
    repo = ensure_repo(cfg)
    scratch = Path(cfg["scratch_dir"])
    scratch.mkdir(parents=True, exist_ok=True)
    capture = capture_arecord if source == "arecord" else capture_ffmpeg
    seg = 0
    print(f"[earboxd] listening: model={Path(cfg['model_path']).name} "
          f"lang={cfg['language']} seg={cfg['segment_seconds']}s "
          f"source={source} memory={cfg['memory_repo']}", flush=True)
    while True:
        if is_muted(cfg):
            _sleep(1)
            continue
        wav = scratch / f"seg_{seg:06d}.wav"
        try:
            capture(cfg, wav)
        except subprocess.CalledProcessError as e:
            print(f"[earboxd] capture failed: {e}", file=sys.stderr, flush=True)
            _sleep(2)
            continue
        text = process_segment(cfg, repo, wav)
        if text:
            print(f"[earboxd] +{len(text)} chars committed", flush=True)
        seg += 1


def _sleep(s):
    import time
    time.sleep(s)


def main(argv=None):
    p = argparse.ArgumentParser(description="earbox capture->transcribe->memory daemon")
    p.add_argument("--config", default=os.path.expanduser("~/.config/earbox/config.toml"))
    p.add_argument("--source", choices=["arecord", "ffmpeg"], default=None,
                   help="capture source (default: arecord on Linux, ffmpeg on macOS)")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    source = args.source or ("arecord" if sys.platform.startswith("linux") else "ffmpeg")
    run(cfg, source)


if __name__ == "__main__":
    main()
