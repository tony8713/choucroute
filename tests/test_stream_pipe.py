#!/usr/bin/env python3
"""Lock stream.open_capture's arecord->ffmpeg wiring.

The bug: passing the arecord asyncio subprocess's rec.stdout (a StreamReader,
no fileno()) as ffmpeg's stdin crashed on every channels>1 run. The fix wires
them with a real os.pipe(). These tests run stub `arecord`/`ffmpeg` shell
scripts on PATH and assert bytes actually flow end to end for both the
single-channel (no ffmpeg) and multi-channel (through the pipe) paths.

No ALSA, no websockets, no ffmpeg binary required.
"""

import asyncio
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path

ORIN = Path(__file__).resolve().parent.parent / "orin"
sys.path.insert(0, str(ORIN))

# stream.py hard-imports `websockets`; stub it so the module imports without the
# real dependency (this test never touches the WS path).
if "websockets" not in sys.modules:
    ws = types.ModuleType("websockets")
    ws.exceptions = types.SimpleNamespace(WebSocketException=Exception)
    ws.connect = None
    sys.modules["websockets"] = ws

import stream  # noqa: E402

PAYLOAD = b"ARECORD_PCM_PAYLOAD_0123456789" * 4  # what the stub "mic" emits


def _write_stub(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class StreamPipeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        # stub arecord: ignore all args, emit the fixed payload, exit.
        _write_stub(d / "arecord",
                    "printf '%s' 'ARECORD_PCM_PAYLOAD_0123456789'\n"
                    "printf '%s' 'ARECORD_PCM_PAYLOAD_0123456789'\n"
                    "printf '%s' 'ARECORD_PCM_PAYLOAD_0123456789'\n"
                    "printf '%s' 'ARECORD_PCM_PAYLOAD_0123456789'\n")
        # stub ffmpeg: ignore the pan args, pass stdin straight to stdout, so any
        # bytes we read from ffmpeg PROVE they traversed arecord -> pipe -> ffmpeg.
        _write_stub(d / "ffmpeg", "exec cat\n")
        self._old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{d}{os.pathsep}{self._old_path}"

    def tearDown(self):
        os.environ["PATH"] = self._old_path
        self.tmp.cleanup()

    def _drain(self, channels):
        async def go():
            rec, conv, out = await stream.open_capture(
                device="stub", channels=channels, asr_channel=0, chunk_bytes=4096,
            )
            data = await out.read()  # read to EOF
            await stream.stop_procs(conv, rec)
            return data, rec, conv
        return asyncio.run(go())

    def test_single_channel_no_ffmpeg(self):
        data, rec, conv = self._drain(channels=1)
        self.assertIsNone(conv, "single channel must not spawn ffmpeg")
        self.assertEqual(data, PAYLOAD)

    def test_multi_channel_through_os_pipe(self):
        data, rec, conv = self._drain(channels=2)
        self.assertIsNotNone(conv, "multi channel must spawn the ffmpeg downmix")
        # bytes came out of ffmpeg's stdout => they flowed arecord -> os.pipe ->
        # ffmpeg -> us. This is exactly the path that used to crash on fileno().
        self.assertEqual(data, PAYLOAD)


if __name__ == "__main__":
    unittest.main(verbosity=2)
