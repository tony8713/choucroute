#!/usr/bin/env python3
"""
denoise - the OPTIONAL pre-processing stage in front of whisper.

Default is BYPASS. The founder unit's reSpeaker XMOS XVF3800 does beamforming,
noise suppression, acoustic echo cancellation (AEC) and AGC ON-CHIP, so the
audio the Orin receives on the XVF3800's processed channel is already cleaned.
Running a second software denoise on top usually hurts WER, so `denoise_enabled`
defaults to false.

It stays here as a pluggable stage for (a) the Pi-satellite path, whose raw mic
has no on-chip DSP, and (b) whatever chain Laurent lands. Laurent's chain name
is still PENDING (D3). Wire it in one of two ways:
  - set `denoise_cmd` to an external filter: reads a WAV on stdin, writes a WAV
    on stdout (same rate/format). Same pattern as summarize.py's egress hook.
  - or replace `_builtin_denoise` with an in-process call.

Contract: denoise(cfg, in_wav_path) -> path to a cleaned WAV (may be the same
path). Must preserve 16-bit PCM mono at cfg['sample_rate'].
"""

import subprocess
from pathlib import Path


def denoise(cfg, in_wav_path):
    if not cfg.get("denoise_enabled", False):
        return in_wav_path  # BYPASS (XVF3800 already did DSP)

    cmd = cfg.get("denoise_cmd")
    if cmd:
        return _external_denoise(cmd, in_wav_path)
    return _builtin_denoise(cfg, in_wav_path)


def _external_denoise(cmd, in_wav_path):
    in_wav_path = Path(in_wav_path)
    out_path = in_wav_path.with_suffix(".dn.wav")
    with open(in_wav_path, "rb") as fin, open(out_path, "wb") as fout:
        subprocess.run(cmd, shell=True, stdin=fin, stdout=fout, check=True)
    # replace original (still in tmpfs; both get deleted by the pipeline)
    return out_path


def _builtin_denoise(cfg, in_wav_path):
    # Placeholder for Laurent's chain (name PENDING). Currently a no-op so an
    # accidental denoise_enabled=true without a denoise_cmd is harmless.
    return in_wav_path
