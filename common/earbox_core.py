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
    # ---- anti-hallucination filtering (STT rejects invented text on silence) --
    "fw_condition_on_previous_text": False,      # stop the model feeding its own noise
    "fw_temperature": 0.0,                       # deterministic; no sampling that invents
    "fw_no_speech_threshold": 0.6,               # drop segments whose no_speech_prob exceeds this
    "fw_min_avg_logprob": -1.0,                  # drop segments whose avg_logprob is below this
    "fw_log_prob_threshold": -1.0,               # whisper-internal silence gate
    "fw_compression_ratio_threshold": 2.4,       # whisper-internal degenerate-repeat gate
    "fw_hallucination_silence_threshold": 2.0,   # passed only if the fw version supports it
    "fw_vad_threshold": 0.5,                      # vad speech probability gate
    "fw_vad_min_silence_ms": 500,                # silence run that splits speech
    "fw_vad_speech_pad_ms": 200,                 # pad kept speech so words aren't clipped
    "hallucination_blacklist_file": "",          # "" = packaged common/hallucinations.txt
    "filter_min_chars": 2,                        # drop near-empty / punctuation-only segments
    "filter_drop_repeated_token": True,          # drop a single short token repeated
}

# whisper on silence/noise hallucinates these; drop them. This built-in set is
# merged with the editable common/hallucinations.txt asset at load time.
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

def normalize_phrase(text):
    s = (text or "").lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


_BLACKLIST_CACHE = {}

def load_blacklist(cfg):
    path = cfg.get("hallucination_blacklist_file") or \
        str(Path(__file__).with_name("hallucinations.txt"))
    key = path
    if key not in _BLACKLIST_CACHE:
        phrases = {normalize_phrase(x) for x in HALLUCINATIONS}
        p = Path(path)
        if p.exists():
            for ln in p.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                phrases.add(normalize_phrase(ln))
        _BLACKLIST_CACHE[key] = {x for x in phrases if x}
    return _BLACKLIST_CACHE[key]


def _is_repeated_token(norm):
    words = norm.split()
    return len(words) >= 2 and len(set(words)) == 1


def _collapse_repeats(words):
    out, i, n = [], 0, len(words)
    while i < n:
        hit = False
        for k in range(1, 5):
            if i + 2 * k > n:
                continue
            unit = words[i:i + k]
            j = i + k
            reps = 1
            while j + k <= n and words[j:j + k] == unit:
                reps += 1
                j += k
            if reps >= 3:
                out.extend(unit)
                i = j
                hit = True
                break
        if not hit:
            out.append(words[i])
            i += 1
    return out


def is_hallucination(cfg, text, blacklist=None):
    if blacklist is None:
        blacklist = load_blacklist(cfg)
    norm = normalize_phrase(text)
    if len(norm) < int(cfg.get("filter_min_chars", 2)):
        return True
    if norm in blacklist:
        return True
    if cfg.get("filter_drop_repeated_token", True) and _is_repeated_token(norm):
        return True
    return False


def filter_segments(cfg, segments, blacklist=None):
    """Reject-on-silence gate over faster-whisper segment objects. Returns the
    surviving segment texts. Drops high no_speech_prob, low avg_logprob,
    blacklisted / near-empty / single-repeated-token segments."""
    if blacklist is None:
        blacklist = load_blacklist(cfg)
    no_speech_max = float(cfg.get("fw_no_speech_threshold", 0.6))
    min_logprob = float(cfg.get("fw_min_avg_logprob", -1.0))
    kept = []
    for s in segments:
        text = (getattr(s, "text", "") or "").strip()
        nsp = getattr(s, "no_speech_prob", None)
        alp = getattr(s, "avg_logprob", None)
        if nsp is not None and nsp > no_speech_max:
            continue
        if alp is not None and alp < min_logprob:
            continue
        if is_hallucination(cfg, text, blacklist):
            continue
        kept.append(text)
    return kept


def clean_transcript(text, cfg=None, blacklist=None):
    if blacklist is None and cfg is not None:
        blacklist = load_blacklist(cfg)
    lines = [ln.strip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        norm = ln.lower().strip()
        norm = re.sub(r"\s+", " ", norm)
        if norm in HALLUCINATIONS:
            continue
        if blacklist is not None and normalize_phrase(ln) in blacklist:
            continue
        # drop pure bracket/paren tags like [_BEG_], (wind blowing)
        if re.fullmatch(r"[\[\(].*[\]\)]", norm):
            continue
        if _is_repeated_token(normalize_phrase(ln)):
            continue
        if ln:
            out.append(ln)
    joined = " ".join(out).strip()
    # collapse whisper's degenerate repetition loops (single word or short phrase)
    joined = " ".join(_collapse_repeats(joined.split()))
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
    return clean_transcript(proc.stdout, cfg=cfg)


# ---- memory (git-backed) ----------------------------------------------------

def ensure_repo(cfg):
    repo = Path(cfg["memory_repo"])
    repo.mkdir(parents=True, exist_ok=True)
    fresh = not (repo / ".git").exists()
    if fresh:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    # Set identity unconditionally: heals a repo that was `git init`ed without
    # one (else every transcript commit dies with "Author identity unknown").
    _git_identity(repo)
    if fresh:
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
