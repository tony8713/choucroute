#!/usr/bin/env python3
"""
codec - encode/decode one segment for the LAN hop (satellite <-> orin).

Two codecs:
  pcm  - the WAV file bytes verbatim. Zero dependencies. ~1MB per 30s segment
         at 16kHz mono; fine on a LAN. Used by the Mac two-tier harness.
  opus - Ogg/Opus via opus-tools (`opusenc`/`opusdec`) as subprocesses, to keep
         the dependency-light, subprocess-first style of the rest of earbox.
         ~40x smaller; recommended for real Pi satellites over Wi-Fi.

Everything is a file<->bytes transform; the raw wav lives in tmpfs and is
deleted by the caller. Nothing here persists audio.
"""

import subprocess
from pathlib import Path


def encode(codec, wav_path):
    """Read a WAV file, return the on-the-wire payload bytes."""
    if codec == "pcm":
        return Path(wav_path).read_bytes()
    if codec == "opus":
        p = subprocess.run(
            ["opusenc", "--quiet", "--bitrate", "24", str(wav_path), "-"],
            capture_output=True, check=True,
        )
        return p.stdout
    raise ValueError(f"unknown codec {codec!r}")


def decode_to_wav(codec, payload, out_wav_path):
    """Write the on-the-wire payload to a WAV file at out_wav_path."""
    out_wav_path = Path(out_wav_path)
    if codec == "pcm":
        out_wav_path.write_bytes(payload)
        return out_wav_path
    if codec == "opus":
        p = subprocess.run(
            ["opusdec", "--quiet", "--force-wav", "-", str(out_wav_path)],
            input=payload, capture_output=True, check=True,
        )
        return out_wav_path
    raise ValueError(f"unknown codec {codec!r}")
