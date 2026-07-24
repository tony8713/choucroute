#!/usr/bin/env python3
"""Lock the mute -> ALSA-release behavior.

Field bug: `touch ~/.earbox-muted` stopped transcription but orind kept the
arecord child (and thus the ALSA capture handle) alive, so any other arecord
got "Device or resource busy". The fix makes the capture child killable and
tears it down the moment the mute flag appears, respawning cleanly on removal.

These tests use a stub recorder binary (no ALSA hardware) that records its PID
so we can prove the child is terminated while the flag exists and a fresh child
is spawned after it's removed. Two layers:

  * capture.capture_segment  - the killable primitive, in isolation.
  * orind.run_direct         - the real daemon loop, driven with the stub.
"""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "orin"))

import capture  # noqa: E402
import orind    # noqa: E402
from common import earbox_core as core  # noqa: E402


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait(pred, timeout, step=0.02):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return pred()


# Stub recorder: append its PID to $SPAWN_LOG, create the (partial) output file
# passed as the last arg, then hold the "device" by sleeping. Writes "$$ done"
# only if it survives the full sleep -> absence of "done" proves it was killed.
STUB = r"""#!/bin/bash
out="${@: -1}"
echo "start $$" >> "$SPAWN_LOG"
: > "$out"
# background the sleep + wait so a SIGTERM trap fires immediately (bash defers
# traps until a foreground command returns, which would delay a mid-sleep kill).
term() { kill "$child" 2>/dev/null; exit 143; }
trap term TERM
sleep "${STUB_DUR:-3}" &
child=$!
wait "$child"
echo "done $$" >> "$out"
echo "done $$" >> "$SPAWN_LOG"
"""


class MuteReleaseBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.stub = self.d / "stub_arecord"
        self.stub.write_text(STUB)
        self.stub.chmod(0o755)
        self.spawn_log = self.d / "spawns.log"
        self.spawn_log.write_text("")
        os.environ["SPAWN_LOG"] = str(self.spawn_log)
        os.environ["STUB_DUR"] = "5"
        self.mute_flag = self.d / "muted"

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("SPAWN_LOG", None)
        os.environ.pop("STUB_DUR", None)

    def spawns(self):
        return [ln for ln in self.spawn_log.read_text().splitlines() if ln]

    def started_pids(self):
        return [int(ln.split()[1]) for ln in self.spawns() if ln.startswith("start")]


class CaptureSegmentAbortTest(MuteReleaseBase):
    def cfg(self):
        return {"usb_capture_device": "stub", "sample_rate": 16000,
                "segment_seconds": 5, "usb_channels": 1, "usb_asr_channel": 0,
                "_arecord_bin": str(self.stub)}

    def test_abort_terminates_child_and_discards_partial(self):
        cfg = self.cfg()
        out = self.d / "seg.wav"
        abort = {"v": False}
        result = {}

        def run():
            try:
                capture.capture_segment(cfg, out, should_abort=lambda: abort["v"])
                result["ok"] = True
            except capture.CaptureAborted:
                result["aborted"] = True

        t = threading.Thread(target=run); t.start()
        self.assertTrue(_wait(lambda: self.started_pids(), 3), "recorder never started")
        pid = self.started_pids()[0]
        self.assertTrue(_alive(pid))
        self.assertTrue(out.exists(), "partial output should exist mid-capture")

        # engage mute; capture must abort well within 1s and free the device.
        t0 = time.time()
        abort["v"] = True
        t.join(timeout=3)
        self.assertFalse(t.is_alive(), "capture_segment did not return after abort")
        self.assertLess(time.time() - t0, 1.0, "abort took >1s")
        self.assertTrue(result.get("aborted"), "expected CaptureAborted")
        self.assertTrue(_wait(lambda: not _alive(pid), 2), "child not terminated")
        self.assertFalse(out.exists(), "partial segment must be discarded")
        # it was killed, not completed:
        self.assertNotIn("done", self.spawn_log.read_text())

    def test_completes_normally_when_not_aborted(self):
        os.environ["STUB_DUR"] = "0.3"
        cfg = self.cfg()
        out = self.d / "seg2.wav"
        capture.capture_segment(cfg, out, should_abort=lambda: False)
        self.assertTrue(out.exists())
        self.assertIn("done", out.read_text())


class RunDirectMuteTest(MuteReleaseBase):
    def test_run_direct_releases_and_respawns(self):
        cfg = {"usb_capture_device": "stub", "sample_rate": 16000,
               "segment_seconds": 5, "usb_channels": 1, "usb_asr_channel": 0,
               "scratch_dir": str(self.d / "scratch"),
               "mute_flag": str(self.mute_flag), "gpio_mute_pin": 0,
               "stt_backend": "echo", "memory_repo": str(self.d / "mem"),
               "_arecord_bin": str(self.stub), "source_label": "orin"}

        orig = orind.handle_segment
        orind.handle_segment = lambda *a, **k: ""  # skip STT/denoise
        stop = threading.Event()

        # start MUTED: the loop must not open the device at all.
        self.mute_flag.write_text("")
        try:
            t = threading.Thread(
                target=orind.run_direct, args=(cfg, None, None), kwargs={"stop_event": stop})
            t.start()
            time.sleep(1.2)
            self.assertEqual(self.started_pids(), [], "device opened while muted")

            # unmute -> a recorder spawns within ~1s.
            self.mute_flag.unlink()
            self.assertTrue(_wait(lambda: len(self.started_pids()) >= 1, 3.5), "no respawn after unmute")
            pid1 = self.started_pids()[0]
            self.assertTrue(_alive(pid1))

            # re-mute mid-capture -> child killed, daemon survives.
            self.mute_flag.write_text("")
            self.assertTrue(_wait(lambda: not _alive(pid1), 3), "child not killed on mute")
            self.assertTrue(t.is_alive(), "run_direct died on mute")

            # unmute again -> a NEW, distinct recorder spawns (clean respawn).
            self.mute_flag.unlink()
            self.assertTrue(_wait(lambda: len(self.started_pids()) >= 2, 3.5), "no second respawn")
            pid2 = self.started_pids()[1]
            self.assertNotEqual(pid1, pid2)

            # never two device holders at once: only the latest child is alive.
            self.assertFalse(_alive(pid1))
        finally:
            stop.set()
            self.mute_flag.write_text("")   # unblock any in-flight sleep loop
            t.join(timeout=5)
            orind.handle_segment = orig
        self.assertFalse(t.is_alive(), "run_direct did not stop on stop_event")


if __name__ == "__main__":
    unittest.main(verbosity=2)
