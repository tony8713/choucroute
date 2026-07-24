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

CAPTURE CONTRACT — arecord emits a WAV STREAM (not headerless raw) and ffmpeg
reads the format/rate/channels from that header. This is deliberate: the XVF3800
firmware presents an ODD channel count (a processed ASR channel plus a silent
reference channel), and the previous code hard-coded ffmpeg's input as
`-f s16le -ac <channels>`. When the assumed channel count did not match what the
device actually delivered, ffmpeg mis-framed the interleaved PCM and folded the
silent channel into the mono output on every Nth sample, producing a periodic
buzz over the real audio (the "horrible digital sound" listeners reported). By
handing ffmpeg a self-describing WAV header we never assume the layout: ffmpeg
extracts the requested ASR channel and resamples to the 16 kHz mono the ingest
API expects, whatever the device's native format / rate / channel count is.

COEXISTENCE — orind holds hw:CARD=Array EXCLUSIVELY (no dsnoop). This streamer
opens the SAME device, so it CANNOT run at the same time as orind. For a test,
stop orind first (or set the mute flag so orind stops opening the mic, then run
this against a free ALSA device). Do NOT auto-start this alongside prod orind.

Run (on the box, orind stopped):
  python3 orin/stream.py \
    --url wss://earbox-ingest.fly.dev/ingest \
    --device hw:0,0 --channels 3 --asr-channel 0

If unsure of the device's real channel count / format, probe first:
  arecord -D hw:0,0 --dump-hw-params
  arecord -D hw:0,0 -f S16_LE -c 3 -r 16000 -d 1 -t wav /tmp/x.wav && ffprobe /tmp/x.wav

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


class CaptureUnavailable(Exception):
    """arecord/ffmpeg produced no audio at all (mic busy, held by orind, or the
    device rejected the requested params). Distinct from a network drop so the
    retry loop can back off hard instead of hammering a busy device."""


def is_muted(mute_flag):
    return bool(mute_flag) and Path(os.path.expanduser(mute_flag)).exists()


def build_capture_cmd(device, channels, asr_channel, in_format, in_rate):
    """arecord (WAV stream) -> ffmpeg (extract ASR channel, resample) -> raw
    S16LE / 16 kHz / mono on stdout.

    arecord emits a WAV header so ffmpeg reads the TRUE format/rate/channel
    layout instead of assuming it; this is what keeps a device that presents an
    unexpected (e.g. odd) channel count from garbling the mono downmix.
    """
    arecord = [
        "arecord", "-q", "-D", device, "-t", "wav",
        "-f", in_format, "-r", str(in_rate), "-c", str(channels),
    ]
    ffmpeg = [
        "ffmpeg", "-nostdin", "-loglevel", "error",
        "-i", "-",
        "-filter:a", f"pan=mono|c0=c{asr_channel}",
        "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-",
    ]
    return arecord, ffmpeg


async def _log_stderr(name, stream):
    """Surface arecord/ffmpeg stderr into the log instead of swallowing it.

    Returns the last few lines so a caller can attach them to an error (a
    device-busy failure is otherwise invisible with stderr sent to DEVNULL)."""
    tail = []
    if stream is None:
        return tail
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").rstrip()
            if not text:
                continue
            tail.append(text)
            del tail[:-8]
            sys.stderr.write(f"[{name}] {text}\n")
    except (asyncio.CancelledError, ValueError):
        pass
    return tail


async def open_capture(device, channels, asr_channel, in_format, in_rate):
    arecord, ffmpeg = build_capture_cmd(device, channels, asr_channel, in_format, in_rate)
    # arecord -> ffmpeg must be wired with a REAL OS pipe: the asyncio StreamReader
    # from rec.stdout has no fileno(), so handing it to ffmpeg as stdin crashes.
    # Give arecord the write end and ffmpeg the read end as inherited fds, then
    # close both ends in the parent so ffmpeg sees EOF when arecord exits. Each
    # child gets its own session (start_new_session) so teardown can killpg the
    # whole group and never leak a process that keeps holding the mic.
    r_fd, w_fd = os.pipe()
    try:
        rec = await asyncio.create_subprocess_exec(
            *arecord, stdout=w_fd, stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        conv = await asyncio.create_subprocess_exec(
            *ffmpeg, stdin=r_fd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, start_new_session=True,
        )
    finally:
        os.close(r_fd)
        os.close(w_fd)
    rec.stderr_tail = []
    rec.stderr_task = asyncio.ensure_future(_log_stderr("arecord", rec.stderr))
    conv.stderr_task = asyncio.ensure_future(_log_stderr("ffmpeg", conv.stderr))
    return rec, conv, conv.stdout


async def stop_procs(*procs):
    for p in procs:
        if p is None:
            continue
        task = getattr(p, "stderr_task", None)
        if task is not None:
            task.cancel()
        if p.returncode is not None:
            continue
        _killpg(p, signal.SIGTERM)
        try:
            await asyncio.wait_for(p.wait(), timeout=2)
        except asyncio.TimeoutError:
            _killpg(p, signal.SIGKILL)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(p.wait(), timeout=2)


def _killpg(p, sig):
    """Signal the child's whole process group; fall back to the bare pid."""
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(p.pid), sig)
        return
    with contextlib.suppress(ProcessLookupError):
        p.send_signal(sig)


async def _arecord_detail(rec):
    tail = getattr(rec, "stderr_task", None)
    if tail is not None:
        with contextlib.suppress(Exception):
            lines = await asyncio.wait_for(asyncio.shield(tail), timeout=1)
            if lines:
                return "; ".join(lines)
    return f"arecord exited rc={rec.returncode}"


async def pump_once(args, stop_event):
    """One connect+capture session. Returns when the stream drops or is stopped.

    Raises CaptureUnavailable if the capture never yields a single byte (mic busy
    / held by orind / device rejected params), so run() can back off hard rather
    than reconnect-spin."""
    chunk_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * args.chunk_ms / 1000)
    async with websockets.connect(
        args.url, max_size=None, ping_interval=20, ping_timeout=20,
    ) as ws:
        sys.stderr.write(f"connected: {args.url}\n")
        rec = conv = None
        produced = False
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
                        args.device, args.channels, args.asr_channel,
                        args.in_format, args.in_rate,
                    )
                    produced = False
                chunk = await out.read(chunk_bytes)
                if not chunk:
                    if not produced:
                        detail = await _arecord_detail(rec)
                        raise CaptureUnavailable(detail)
                    break
                produced = True
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
        except CaptureUnavailable as exc:
            sys.stderr.write(
                f"capture unavailable (mic busy? device rejected params?): {exc}; "
                f"retry in {args.busy_backoff:.1f}s\n"
            )
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=args.busy_backoff)
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
    p.add_argument("--channels", type=int, default=3, help="channels the device presents (arecord --dump-hw-params)")
    p.add_argument("--asr-channel", type=int, default=0, help="processed ASR channel index")
    p.add_argument("--in-format", default="S16_LE", help="arecord capture sample format (e.g. S16_LE, S32_LE)")
    p.add_argument("--in-rate", type=int, default=SAMPLE_RATE, help="arecord capture sample rate; ffmpeg resamples to 16k")
    p.add_argument("--chunk-ms", type=int, default=100, help="ms of audio per WS frame")
    p.add_argument("--mute-flag", default="~/.earbox-muted", help="path to mute flag file")
    p.add_argument("--min-backoff", type=float, default=0.5)
    p.add_argument("--max-backoff", type=float, default=10.0)
    p.add_argument("--busy-backoff", type=float, default=5.0, help="backoff when the mic is busy / capture yields nothing")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
