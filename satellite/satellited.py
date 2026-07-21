#!/usr/bin/env python3
"""
satellited - the earbox MIC SATELLITE daemon (Raspberry Pi 4).

OPTIONAL multi-room tier. The founder unit does NOT need this (the Orin captures
its local XVF3800 directly). A satellite is a cheap Pi 4 + mic in another room
that streams that room's speech to the Orin brain over the LAN.

Pipeline (ZERO storage on the Pi):
  arecord (mic) -> tmpfs wav -> energy VAD gate -> encode (opus/pcm)
    -> stream over TLS to the Orin -> DELETE the tmpfs wav immediately.

The Pi keeps no transcripts and no audio: it is a dumb, encrypted microphone.
All transcription, memory and deletion-of-record happen on the Orin. If the
mute flag/GPIO is set, the mic is never opened.

Discovery: set `orin_host` statically, or leave it empty to mDNS-discover the
Orin advertising _earbox._tcp (needs python zeroconf on the Pi).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root on path

from common import earbox_core as core       # noqa: E402
from common import wire                       # noqa: E402
from common import codec as codeclib          # noqa: E402

SAT_DEFAULTS = dict(core.DEFAULTS)
SAT_DEFAULTS.update({
    "satellite_id": "satellite",
    "orin_host": "",                 # empty -> mDNS discover
    "orin_port": 7217,
    "codec": "opus",                 # opus (opus-tools) or pcm
    "tls_cafile": "/opt/earbox/tls/orin.crt",   # pinned Orin cert
    "alsa_device": "default",
    "memory_repo": "",               # satellites have NO memory
})


def discover_orin(cfg, timeout=8):
    host = cfg.get("orin_host") or ""
    if host:
        return host, int(cfg["orin_port"])
    from zeroconf import Zeroconf, ServiceBrowser
    import time
    found = {}

    class _L:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info and info.addresses:
                import socket as _s
                found["host"] = _s.inet_ntoa(info.addresses[0])
                found["port"] = info.port

        def update_service(self, *a):
            pass

        def remove_service(self, *a):
            pass

    zc = Zeroconf()
    ServiceBrowser(zc, "_earbox._tcp.local.", _L())
    deadline = time.time() + timeout
    while time.time() < deadline and "host" not in found:
        time.sleep(0.2)
    zc.close()
    if "host" not in found:
        raise RuntimeError("no Orin found via mDNS; set orin_host in config")
    return found["host"], found["port"]


def capture_segment(cfg, out_wav_path):
    import subprocess
    subprocess.run(
        ["arecord", "-q", "-D", cfg.get("alsa_device", "default"),
         "-f", "S16_LE", "-r", str(cfg["sample_rate"]), "-c", "1",
         "-d", str(cfg["segment_seconds"]), str(out_wav_path)],
        check=True,
    )
    return out_wav_path


def run(cfg, grab=None):
    grab = grab or capture_segment
    host, port = discover_orin(cfg)
    ctx = wire.client_tls_context(cfg["tls_cafile"])
    scratch = Path(cfg["scratch_dir"]); scratch.mkdir(parents=True, exist_ok=True)
    codec = cfg["codec"]
    core.log("satellite", f"'{cfg['satellite_id']}' -> orin {host}:{port} "
                          f"(codec={codec}, TLS)")
    conn = wire.connect(host, int(port), ctx)
    wire.send_header(conn, cfg["satellite_id"], codec,
                     cfg["sample_rate"], cfg["segment_seconds"])
    seg = 0
    try:
        while True:
            if core.is_muted(cfg):
                core.sleep(1); continue
            wav = scratch / f"sat_{seg:06d}.wav"
            try:
                grab(cfg, wav)
                if core.has_speech(cfg, wav):
                    payload = codeclib.encode(codec, wav)
                    wire.send_frame(conn, payload)
                    core.log("satellite", f"seg {seg}: sent {len(payload)} bytes")
            finally:
                # ZERO STORAGE: the raw wav is destroyed on the Pi immediately,
                # whether or not it was voiced or sent.
                if wav.exists():
                    try:
                        os.remove(wav)
                    except FileNotFoundError:
                        pass
            seg += 1
    finally:
        try:
            conn.unwrap()  # clean TLS close so the Orin sees EOF, not a reset
        except OSError:
            pass
        conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="earbox Pi mic satellite")
    p.add_argument("--config", default=os.path.expanduser("~/.config/earbox/satellite.toml"))
    args = p.parse_args(argv)
    cfg = core.load_config(args.config, defaults=SAT_DEFAULTS)
    run(cfg)


if __name__ == "__main__":
    main()
