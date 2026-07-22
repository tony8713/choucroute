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

import inspect

from common import earbox_core as core

_FW_MODEL = None


def _supported_kwargs(fn, kwargs, cfg):
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return kwargs
    if "hallucination_silence_threshold" in params:
        kwargs["hallucination_silence_threshold"] = \
            cfg.get("fw_hallucination_silence_threshold", 2.0)
    return {k: v for k, v in kwargs.items() if k in params}


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
    kwargs = dict(
        language=None if lang == "auto" else lang,
        beam_size=cfg.get("fw_beam_size", 1),
        vad_filter=cfg.get("fw_vad_filter", True),
        vad_parameters=dict(
            threshold=cfg.get("fw_vad_threshold", 0.5),
            min_silence_duration_ms=cfg.get("fw_vad_min_silence_ms", 500),
            speech_pad_ms=cfg.get("fw_vad_speech_pad_ms", 200),
        ),
        condition_on_previous_text=cfg.get("fw_condition_on_previous_text", False),
        temperature=cfg.get("fw_temperature", 0.0),
        no_speech_threshold=cfg.get("fw_no_speech_threshold", 0.6),
        log_prob_threshold=cfg.get("fw_log_prob_threshold", -1.0),
        compression_ratio_threshold=cfg.get("fw_compression_ratio_threshold", 2.4),
    )
    kwargs = _supported_kwargs(_FW_MODEL.transcribe, kwargs, cfg)
    segments, _info = _FW_MODEL.transcribe(str(wav_path), **kwargs)
    blacklist = core.load_blacklist(cfg)
    kept = core.filter_segments(cfg, segments, blacklist=blacklist)
    return core.clean_transcript(" ".join(kept), blacklist=blacklist)


def _echo(cfg, wav_path):
    from pathlib import Path
    return core.clean_transcript(f"[echo] {Path(wav_path).name}")
