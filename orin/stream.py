#!/usr/bin/env python3
"""
stream - box-side LIVE audio streamer (earbox -> Fly audio-ingest API).

Captures the reSpeaker XVF3800 USB array on the Orin and streams the
DSP-processed ASR channel as raw PCM S16LE / 16 kHz / mono over a WebSocket to
the cloud ingest endpoint (services/../apps/ingest on Fly). Binary WS frames of
raw PCM, ~100 ms each; auto-reconnect on drop; honors the earbox mute flag.

This REVERSES the earlier "audio never leaves the box" model: it is a deliberate
product decision (Less, 2026-07-23) to stream to a cloud STT. Auth is currently
open (deferred for the MVP); add a token here when the API re-enables it.

COEXISTENCE — orind holds hw:CARD=Array EXCLUSIVELY (no dsnoop). This streamer
opens the SAME device, so it CANNOT run at the same time as orind. For a test,
stop orind first (or set the mute flag so orind stops opening the mic, then run
this against a free ALSA device). Do NOT auto-start this alongside prod orind.

Run (on the box, orind stopped):
  python3 orin/stream.py \
    --url wss://earbox-ingest.fly.dev/ingest \
    --device hw:0,0 --channels 2 --asr-channel 0

Dependency: `websockets` (pip install websockets). arecord + ffmpeg already on
the box for the capture pipeline.
"""

import argparse
import asyncio
import contextlib
import os
import signal
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.stderr.write("missing dependency: pip install websockets\n")
    raise

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


def is_muted(mute_flag):
    return bool(mute_flag) and Path(os.path.expanduser(mute_flag)).exists()


def build_capture_cmd(device, channels, asr_channel, chunk_bytes):
    """arecord (+ optional ffmpeg down-select) -> raw S16LE mono on stdout."""
    arecord = [
        "arecord", "-q", "-D", device, "-t", "raw",
        "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", str(channels),
    ]
    if channels <= 1:
        return arecord, None
    ffmpeg = [
        "ffmpeg", "-nostdin", "-loglevel", "error",
        "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", str(channels), "-i", "-",
        "-af", f"pan=mono|c0=c{asr_channel}",
        "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-",
    ]
    return arecord, ffmpeg


async def open_capture(device, channels, asr_channel, chunk_bytes):
    arecord, ffmpeg = build_capture_cmd(device, channels, asr_channel, chunk_bytes)
    rec = await asyncio.create_subprocess_exec(
        *arecord, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    if ffmpeg is None:
        return rec, None, rec.stdout
    conv = await asyncio.create_subprocess_exec(
        *ffmpeg, stdin=rec.stdout, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return rec, conv, conv.stdout


async def stop_procs(*procs):
    for p in procs:
        if p is None or p.returncode is not None:
            continue
        with contextlib.suppress(ProcessLookupError):
            p.terminate()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(p.wait(), timeout=2)


async def pump_once(args, stop_event):
    """One connect+capture session. Returns when the stream drops or is stopped."""
    chunk_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * args.chunk_ms / 1000)
    async with websockets.connect(
        args.url, max_size=None, ping_interval=20, ping_timeout=20,
    ) as ws:
        sys.stderr.write(f"connected: {args.url}\n")
        rec = conv = None
        muted_logged = False
        try:
            while not stop_event.is_set():
                if is_muted(args.mute_flag):
                    if rec is not None:
                        await stop_procs(conv, rec)
                        rec = conv = None
                    if not muted_logged:
                        sys.stderr.write("muted: mic closed, holding stream\n")
                        muted_logged = True
                    await asyncio.sleep(0.5)
                    continue
                muted_logged = False
                if rec is None:
                    rec, conv, out = await open_capture(
                        args.device, args.channels, args.asr_channel, chunk_bytes,
                    )
                chunk = await out.read(chunk_bytes)
                if not chunk:
                    break
                await ws.send(chunk)
        finally:
            await stop_procs(conv, rec)


async def run(args):
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    backoff = args.min_backoff
    while not stop_event.is_set():
        try:
            await pump_once(args, stop_event)
            backoff = args.min_backoff
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            sys.stderr.write(f"stream dropped: {exc}; retry in {backoff:.1f}s\n")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            backoff = min(args.max_backoff, backoff * 2)
    sys.stderr.write("stopped\n")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="stream earbox mic PCM to the Fly ingest API")
    p.add_argument("--url", required=True, help="wss://earbox-ingest.fly.dev/ingest")
    p.add_argument("--device", default="hw:0,0", help="ALSA capture device (arecord -l)")
    p.add_argument("--channels", type=int, default=2, help="channels the XVF3800 presents")
    p.add_argument("--asr-channel", type=int, default=0, help="processed ASR channel index")
    p.add_argument("--chunk-ms", type=int, default=100, help="ms of audio per WS frame")
    p.add_argument("--mute-flag", default="~/.earbox-muted", help="path to mute flag file")
    p.add_argument("--min-backoff", type=float, default=0.5)
    p.add_argument("--max-backoff", type=float, default=10.0)
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
