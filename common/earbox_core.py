#!/usr/bin/env python3
"""
earbox_core - shared building blocks for both tiers (orin brain + pi satellite).

This is the single source of truth for the privacy-critical pieces that D1
proved on the Mac: the energy VAD, transcript cleaning, the git-backed text
memory, the mute gate, and the delete-in-finally segment pipeline. Both
`orin/orind.py` and `daemon/earboxd.py` (legacy single-box) import from here so
the VAD/cleaning/memory logic can never drift between tiers.

Privacy invariants (see docs/architecture.md):
  1. Raw audio lives only in a tmpfs scratch path and is DELETED in a `finally`
     after transcription. It is never persisted, never written to disk-at-rest.
  2. Only text (transcripts) is written to the owner's git memory.
  3. A physical mute switch or a mute flag file gates capture.
  4. On the LAN hop (satellite -> orin) audio is encrypted and stays on the LAN;
     it never reaches the internet.
"""

import array
import datetime as dt
import math
import os
import re
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import wave
from pathlib import Path

# ---- config -----------------------------------------------------------------

DEFAULTS = {
    "segment_seconds": 30,
    "sample_rate": 16000,
    "language": "fr",
    "memory_repo": os.path.expanduser("~/earbox-memory"),
    "scratch_dir": "/dev/shm/earbox",           # tmpfs on Linux -> never hits disk
    "vad_rms_threshold": 0.012,                  # 0..1, skip chunks quieter than this
    "vad_min_voiced_ratio": 0.06,                # >=6% of frames must be "loud"
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


def load_config(path, defaults=None):
    cfg = dict(defaults if defaults is not None else DEFAULTS)
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
            import gpiozero  # noqa: F401  (only present on a Pi)
            return _gpio_button(pin).is_pressed  # switch closed == muted
        except Exception:
            return False
    return False


_GPIO_CACHE = {}
def _gpio_button(pin):
    if pin not in _GPIO_CACHE:
        from gpiozero import Button
        _GPIO_CACHE[pin] = Button(pin, pull_up=True)
    return _GPIO_CACHE[pin]


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


# ---- transcript cleaning ----------------------------------------------------

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


# ---- whisper.cpp backend (D1 path; used on the Mac + as an Orin fallback) ----

def transcribe_whisper_cli(cfg, wav_path):
    """Transcribe via whisper.cpp `whisper-cli`. Returns cleaned text."""
    proc = subprocess.run(
        [cfg.get("whisper_bin", "whisper-cli"),
         "-m", cfg["model_path"], "-l", cfg["language"],
         "-t", str(cfg.get("whisper_threads", 4)), "-nt", "-f", str(wav_path)],
        capture_output=True, text=True, check=True,
    )
    return clean_transcript(proc.stdout)


# ---- memory (git-backed) ----------------------------------------------------

def ensure_repo(cfg):
    repo = Path(cfg["memory_repo"])
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        _git_identity(repo)
        gi = repo / ".gitignore"
        gi.write_text("*.wav\n*.aiff\n*.raw\n*.pcm\n*.opus\n")  # never commit audio
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


def append_transcript(cfg, repo, text, when=None, source=None):
    """Append one transcript line to the day file. `source` tags the room/mic."""
    when = when or dt.datetime.now()
    day = when.strftime("%Y-%m-%d")
    daydir = repo / "transcripts"
    daydir.mkdir(exist_ok=True)
    md = daydir / f"{day}.md"
    if not md.exists():
        md.write_text(f"# {day}\n\n")
    tag = f" _({source})_" if source else ""
    with open(md, "a") as f:
        f.write(f"- **{when.strftime('%H:%M')}**{tag} {text}\n")
    if cfg["auto_commit"]:
        subprocess.run(["git", "add", str(md)], cwd=repo, check=True)
        msg = f"transcript {when.strftime('%Y-%m-%d %H:%M')}"
        if source:
            msg += f" [{source}]"
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)
    return md


# ---- the segment pipeline (VAD -> transcribe -> memory -> DELETE) -----------

def process_segment(cfg, repo, wav_path, transcribe, when=None, source=None):
    """
    Run one raw-audio segment through the full pipeline and DESTROY the audio.

    `transcribe` is a callable (cfg, wav_path) -> text so callers pick the
    backend: faster-whisper (Orin/CUDA), whisper.cpp (Mac/fallback), or a
    plumbing echo. Audio is deleted in the `finally` no matter what.
    """
    text = None
    try:
        if not has_speech(cfg, wav_path):
            return None
        text = transcribe(cfg, wav_path)
        if not text:
            return None
        append_transcript(cfg, repo, text, when=when, source=source)
        return text
    finally:
        # PRIVACY INVARIANT: raw audio is destroyed no matter what.
        if not cfg.get("keep_debug_audio", False):
            try:
                os.remove(wav_path)
            except FileNotFoundError:
                pass


def slice_wav(src, seconds, rate, scratch, prefix="seg"):
    """Slice a wav into fixed-length chunks written to `scratch`. Returns paths."""
    with wave.open(str(src), "rb") as w:
        sw, ch, sr = w.getsampwidth(), w.getnchannels(), w.getframerate()
        frames = w.readframes(w.getnframes())
    assert sr == rate, f"source is {sr}Hz, expected {rate}Hz (resample first)"
    step = seconds * sr * sw * ch
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(0, len(frames), step):
        chunk = frames[i:i + step]
        p = scratch / f"{prefix}_{i//step:04d}.wav"
        with wave.open(str(p), "wb") as o:
            o.setsampwidth(sw); o.setnchannels(ch); o.setframerate(sr)
            o.writeframes(chunk)
        out.append(p)
    return out


def sleep(s):
    import time
    time.sleep(s)


def log(tag, msg):
    print(f"[{tag}] {msg}", file=sys.stderr if False else sys.stdout, flush=True)
