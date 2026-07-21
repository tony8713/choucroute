#!/usr/bin/env python3
"""
stt - the Orin's speech-to-text backends.

Primary (production, on the Jetson Orin Nano Super):
    faster-whisper (CTranslate2) on CUDA with int8 compute. small/medium int8
    is EXPECTED to run comfortably faster than real time on the Orin's GPU, but
    that number MUST be benchmarked on the device (D3) — there is no Orin in
    this dev environment, so this path is UNTESTED-ON-TARGET.

Fallbacks:
    whisper_cli  - whisper.cpp `whisper-cli`; the D1 path, runs on the Mac, used
                   by the two-tier harness so we can prove the full plumbing
                   locally with real transcription.
    echo         - no model; returns a marker. Pure plumbing tests only.

Select with config `stt_backend = "faster_whisper" | "whisper_cli" | "echo"`.
Every backend is a callable (cfg, wav_path) -> cleaned text.
"""

from common import earbox_core as core

_FW_MODEL = None


def get_transcriber(cfg):
    backend = cfg.get("stt_backend", "faster_whisper")
    if backend == "faster_whisper":
        return _faster_whisper
    if backend == "whisper_cli":
        return core.transcribe_whisper_cli
    if backend == "echo":
        return _echo
    raise ValueError(f"unknown stt_backend {backend!r}")


def _faster_whisper(cfg, wav_path):
    """
    UNTESTED-ON-TARGET: requires a CUDA Jetson (JetPack 6.x) with faster-whisper
    + CTranslate2 CUDA wheels installed. Benchmark small vs medium int8 on the
    Orin on D3 and pin whichever holds real time in kitchen noise.
    """
    global _FW_MODEL
    if _FW_MODEL is None:
        from faster_whisper import WhisperModel
        _FW_MODEL = WhisperModel(
            cfg.get("fw_model_size", "small"),
            device=cfg.get("fw_device", "cuda"),
            compute_type=cfg.get("fw_compute_type", "int8"),
        )
    lang = cfg.get("language", "fr")
    segments, _info = _FW_MODEL.transcribe(
        str(wav_path),
        language=None if lang == "auto" else lang,
        vad_filter=cfg.get("fw_vad_filter", True),
        beam_size=cfg.get("fw_beam_size", 1),
    )
    text = " ".join(s.text for s in segments)
    return core.clean_transcript(text)


def _echo(cfg, wav_path):
    from pathlib import Path
    return core.clean_transcript(f"[echo] {Path(wav_path).name}")
