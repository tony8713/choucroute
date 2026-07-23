#!/usr/bin/env python3
"""
capture - the Orin's LOCAL microphone capture (founder unit, no LAN hop).

The founder unit is an Orin + reSpeaker XMOS XVF3800 USB 4-mic array in one
enclosure. The XVF3800 enumerates as a standard USB audio class device, so we
capture it with plain ALSA `arecord` on the Orin (JetPack/L4T is Linux).

CHANNEL LAYOUT — VERIFY ON-DEVICE (D3): the XVF3800 exposes several output
channels; the one we want is the DSP-PROCESSED ASR channel (post beamforming +
noise suppression + AEC + AGC), NOT the raw per-mic channels. On XMOS XVF3800
USB firmware the processed output is the first playback-capture channel; exact
index/layout depends on the loaded firmware, so it is configurable here:

  usb_capture_device   ALSA device, e.g. "plughw:CARD=XVF3800,DEV=0" (see
                       `arecord -l` / `arecord -L` on the Orin).
  usb_channels         total channels the device presents (e.g. 1, 2, or 6).
  usb_asr_channel      index of the processed ASR channel to feed whisper.

If the device presents a single already-processed mono channel we just record
it directly; if it presents multiple, we down-select usb_asr_channel with an
ffmpeg pan filter. This whole module is UNTESTED-ON-TARGET (no Orin/XVF3800
here); the channel selection MUST be confirmed against the reSpeaker XVF3800
docs + `arecord` on the real device on D3.
"""

import os
import subprocess


def capture_segment(cfg, out_wav_path):
    device = cfg.get("usb_capture_device", "default")
    rate = cfg["sample_rate"]
    seconds = cfg["segment_seconds"]
    channels = int(cfg.get("usb_channels", 1))
    asr_ch = int(cfg.get("usb_asr_channel", 0))

    if channels <= 1:
        # already a single processed mono channel -> record straight to 16k mono
        subprocess.run(
            ["arecord", "-q", "-D", device, "-f", "S16_LE",
             "-r", str(rate), "-c", "1", "-d", str(seconds), str(out_wav_path)],
            check=True,
        )
        return out_wav_path

    # multi-channel device: capture all channels, then pan-select the ASR one.
    raw = str(out_wav_path) + ".multi.wav"
    subprocess.run(
        ["arecord", "-q", "-D", device, "-f", "S16_LE",
         "-r", str(rate), "-c", str(channels), "-d", str(seconds), raw],
        check=True,
    )
    # arecord can exit 0 with a header-only (44-byte) file when the USB array is
    # momentarily contended (a desktop PulseAudio/PipeWire session re-grabbing the
    # card); ffmpeg would then die with a cryptic "No such file or directory".
    if not os.path.exists(raw) or os.path.getsize(raw) <= 44:
        have = os.path.getsize(raw) if os.path.exists(raw) else "missing"
        raise RuntimeError(f"arecord produced no audio at {raw} (size={have}); "
                           "USB array likely contended")
    # single-in/single-out downmix -> simple filter (-af), not -filter_complex;
    # surface ffmpeg stderr instead of swallowing it in a bare non-zero exit.
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", raw,
         "-af", f"pan=mono|c0=c{asr_ch}",
         "-ar", str(rate), "-ac", "1", "-c:a", "pcm_s16le", str(out_wav_path)],
        stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg downmix failed (exit {proc.returncode}) on "
                           f"{raw}: {proc.stderr.strip()}")
    try:
        os.remove(raw)
    except FileNotFoundError:
        pass
    return out_wav_path


def capture_segment_ffmpeg_mac(cfg, out_wav_path):
    """Mac dev convenience: capture the default avfoundation input. Not used on
    the Orin; here so `orind.py --source direct` can be smoke-tested on a Mac."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "avfoundation",
         "-i", cfg.get("av_device", ":0"), "-t", str(cfg["segment_seconds"]),
         "-ar", str(cfg["sample_rate"]), "-ac", "1", "-c:a", "pcm_s16le",
         str(out_wav_path)],
        check=True,
    )
    return out_wav_path
