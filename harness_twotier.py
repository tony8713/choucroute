#!/usr/bin/env python3
"""
harness_twotier - prove the FULL two-tier plumbing on a Mac, no Pi, no Orin.

It runs the REAL Orin daemon (orin/orind.py) as a subprocess in `lan` mode with
real self-signed TLS, then runs a loopback "satellite" that slices a source wav
into segments and streams them over the real TLS socket using the exact wire
framing + codec the Pi satellite uses. The Orin decodes each segment in tmpfs,
runs it through denoise(bypass) -> STT -> git memory -> delete-in-finally.

We use the whisper_cli STT backend (whisper.cpp, D1-proven on this Mac) because
faster-whisper needs the Orin's CUDA. So this proves: TLS hop + framing + codec
+ Orin decode + real transcription + git commit + audio destroyed. The only
untested-on-target piece is faster-whisper itself (D3 on the device).

Usage:
  python3 harness_twotier.py scratch/test_fr.wav [--seconds 30] [--codec pcm]
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common import earbox_core as core   # noqa: E402
from common import wire                  # noqa: E402
from common import codec as codeclib     # noqa: E402

SCRATCH = ROOT / "scratch" / "twotier"
MEM = ROOT / "scratch" / "twotier-memory"
PORT = 7317


def free_port(preferred):
    s = socket.socket();
    try:
        s.bind(("127.0.0.1", preferred)); s.close(); return preferred
    except OSError:
        s2 = socket.socket(); s2.bind(("127.0.0.1", 0))
        p = s2.getsockname()[1]; s2.close(); return p


def gen_certs(tls_dir):
    tls_dir.mkdir(parents=True, exist_ok=True)
    crt, key = tls_dir / "orin.crt", tls_dir / "orin.key"
    if crt.exists() and key.exists():
        return crt, key
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(crt), "-days", "3650",
         "-subj", "/CN=localhost",
         "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
        check=True, capture_output=True,
    )
    return crt, key


def write_orin_config(path, port, crt, key, model):
    path.write_text(f"""
mode = "lan"
stt_backend = "whisper_cli"
whisper_bin = "whisper-cli"
model_path = "{model}"
language = "fr"
whisper_threads = 4
denoise_enabled = false
memory_repo = "{MEM}"
scratch_dir = "{SCRATCH}"
auto_commit = true
listen_host = "127.0.0.1"
listen_port = {port}
tls_certfile = "{crt}"
tls_keyfile = "{key}"
mdns_advertise = false
""".lstrip())


def wait_listening(port, proc, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def loopback_satellite(source, seconds, rate, codec, crt, port, sat_id="kitchen-loopback"):
    """The Pi satellite, in-process: slice -> VAD -> encode -> stream over TLS."""
    chunks = core.slice_wav(source, seconds, rate, SCRATCH, prefix="loop")
    cfg = {"vad_rms_threshold": core.DEFAULTS["vad_rms_threshold"],
           "vad_min_voiced_ratio": core.DEFAULTS["vad_min_voiced_ratio"]}
    ctx = wire.client_tls_context(str(crt))
    conn = wire.connect("127.0.0.1", port, ctx)
    wire.send_header(conn, sat_id, codec, rate, seconds)
    sent = 0
    try:
        for ch in chunks:
            voiced = core.has_speech(cfg, ch)
            if voiced:
                payload = codeclib.encode(codec, ch)
                wire.send_frame(conn, payload)
                sent += 1
                print(f"[loopback-sat] chunk {ch.name}: voiced -> sent {len(payload)}B")
            else:
                print(f"[loopback-sat] chunk {ch.name}: silence -> skipped")
            # ZERO STORAGE on the "Pi": delete the sliced wav immediately.
            try:
                os.remove(ch)
            except FileNotFoundError:
                pass
        time.sleep(0.2)  # let last frame flush
    finally:
        try:
            conn.unwrap()  # clean TLS close_notify so the server sees EOF, not reset
        except OSError:
            pass
        conn.close()
    return len(chunks), sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--codec", default="pcm", choices=["pcm", "opus"])
    ap.add_argument("--model", default=os.path.expanduser("~/.whisper-models/ggml-base.bin"))
    args = ap.parse_args()

    # clean slate
    for d in (SCRATCH, MEM):
        if d.exists():
            shutil.rmtree(d)
    SCRATCH.mkdir(parents=True, exist_ok=True)

    port = free_port(PORT)
    tls_dir = ROOT / "scratch" / "twotier-tls"
    crt, key = gen_certs(tls_dir)
    cfg_path = ROOT / "scratch" / "twotier-orin.toml"
    write_orin_config(cfg_path, port, crt, key, args.model)

    print(f"[harness] starting REAL orind (lan mode, TLS) on 127.0.0.1:{port}")
    orind = subprocess.Popen(
        [sys.executable, str(ROOT / "orin" / "orind.py"),
         "--config", str(cfg_path), "--mode", "lan", "--stt", "whisper_cli"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    ok = wait_listening(port, orind)
    if not ok:
        print("[harness] orind failed to start:")
        print(orind.communicate()[0])
        return 1

    print(f"[harness] streaming loopback satellite ({args.codec}) ...")
    n_chunks, n_sent = loopback_satellite(args.source, args.seconds,
                                          core.DEFAULTS["sample_rate"],
                                          args.codec, crt, port)

    # give the Orin time to transcribe the frames it received
    time.sleep(max(3, n_sent * 4))
    orind.terminate()
    try:
        out = orind.communicate(timeout=10)[0]
    except subprocess.TimeoutExpired:
        orind.kill(); out = orind.communicate()[0]

    print("\n----- orind (Orin brain) log -----")
    print(out.strip())

    # ---- verify -------------------------------------------------------------
    stray = list(Path(SCRATCH).rglob("*.wav")) + list(Path(MEM).rglob("*.wav"))
    tdir = MEM / "transcripts"
    transcripts = sorted(tdir.glob("*.md")) if tdir.exists() else []
    total_lines = 0
    print("\n----- git memory on the Orin -----")
    if (MEM / ".git").exists():
        subprocess.run(["git", "-C", str(MEM), "log", "--oneline"])
    for md in transcripts:
        body = md.read_text()
        lines = [l for l in body.splitlines() if l.startswith("- ")]
        total_lines += len(lines)
        print(f"--- {md.name} ---\n{body}")

    print("\n----- VERDICT -----")
    print(f"chunks sliced           : {n_chunks}")
    print(f"segments streamed        : {n_sent}")
    print(f"transcript lines committed: {total_lines}")
    print(f"stray audio files        : {len(stray)} (MUST be 0)")
    worked = (n_sent > 0 and total_lines > 0 and len(stray) == 0)
    print(f"\nTWO-TIER PLUMBING: {'WORKED ✅' if worked else 'FAILED ❌'}")
    return 0 if worked else 1


if __name__ == "__main__":
    sys.exit(main())
