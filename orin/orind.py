#!/usr/bin/env python3
"""
orind - the earbox BRAIN daemon (Jetson Orin Nano Super).

Two input modes feed ONE pipeline (denoise -> STT -> git memory -> delete):

  direct  (PRIMARY, founder unit): capture the local reSpeaker XVF3800 USB mic
          on the Orin itself. No network, no LAN hop. This is the v1 product.

  lan     (OPTIONAL, multi-room): run a TLS server; Pi 4 satellites stream
          VAD-passed, encrypted segments in over the LAN. Audio is decoded in
          tmpfs and destroyed after transcription, same as the direct path.

Both modes end in common.earbox_core.process_segment: VAD (already applied on
the satellite for the lan path; re-checked here) -> optional denoise (BYPASS by
default; XVF3800 does DSP on-chip) -> faster-whisper (CUDA int8) -> day-keyed
markdown git memory -> raw audio deleted in a `finally`.

NOTE: the faster-whisper CUDA path is UNTESTED-ON-TARGET (no Orin in dev). Run
with `--stt whisper_cli` to exercise the whole daemon on a Mac.
"""

import argparse
import os
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root on path

from common import earbox_core as core       # noqa: E402
from common import wire                       # noqa: E402
from common import codec as codeclib          # noqa: E402
import denoise as denoise_mod                 # noqa: E402  (orin/denoise.py)
import stt as stt_mod                         # noqa: E402  (orin/stt.py)

ORIN_DEFAULTS = dict(core.DEFAULTS)
ORIN_DEFAULTS.update({
    "stt_backend": "faster_whisper",
    "fw_model_size": "small",
    "fw_device": "cuda",
    "fw_compute_type": "int8",
    "language": "fr",
    "whisper_bin": "whisper-cli",              # only for the whisper_cli fallback
    "model_path": os.path.expanduser("~/.whisper-models/ggml-base.bin"),
    "denoise_enabled": False,                  # XVF3800 does DSP on-chip
    # direct (local USB XVF3800)
    "usb_capture_device": "default",
    "usb_channels": 1,
    "usb_asr_channel": 0,
    # lan (satellite server)
    "listen_host": "0.0.0.0",
    "listen_port": 7217,
    "tls_certfile": "/opt/earbox/tls/orin.crt",
    "tls_keyfile": "/opt/earbox/tls/orin.key",
    # discovery
    "mdns_advertise": True,
    "mdns_instance": "earbox-orin",
})


# ---- the shared segment pipeline -------------------------------------------

def handle_segment(cfg, repo, transcribe, wav_path, when=None, source=None):
    wav_path = denoise_mod.denoise(cfg, wav_path)
    return core.process_segment(cfg, repo, wav_path, transcribe, when=when, source=source)


# ---- direct mode (local USB XVF3800) ---------------------------------------

def run_direct(cfg, repo, transcribe):
    from capture import capture_segment, capture_segment_ffmpeg_mac
    grab = capture_segment_ffmpeg_mac if cfg.get("_mac_direct") else capture_segment
    scratch = Path(cfg["scratch_dir"]); scratch.mkdir(parents=True, exist_ok=True)
    src = cfg.get("source_label", "orin")
    core.log("orind", f"direct capture: device={cfg['usb_capture_device']} "
                      f"stt={cfg['stt_backend']} memory={cfg['memory_repo']}")
    seg = 0
    while True:
        if core.is_muted(cfg):
            core.sleep(1); continue
        wav = scratch / f"orin_{seg:06d}.wav"
        try:
            grab(cfg, wav)
        except Exception as e:  # noqa: BLE001
            core.log("orind", f"capture failed: {e}"); core.sleep(2); continue
        text = handle_segment(cfg, repo, transcribe, wav, source=src)
        if text:
            core.log("orind", f"+{len(text)} chars committed")
        seg += 1


# ---- lan mode (satellite TLS server) ---------------------------------------

def run_lan(cfg, repo, transcribe):
    ctx = wire.server_tls_context(cfg["tls_certfile"], cfg["tls_keyfile"])
    if cfg.get("mdns_advertise", True):
        _advertise_mdns(cfg)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((cfg["listen_host"], int(cfg["listen_port"])))
    srv.listen(8)
    core.log("orind", f"lan server on {cfg['listen_host']}:{cfg['listen_port']} "
                      f"stt={cfg['stt_backend']} (TLS, LAN-only)")
    while True:
        raw, addr = srv.accept()
        threading.Thread(target=_serve_satellite, args=(cfg, repo, transcribe, ctx, raw, addr),
                         daemon=True).start()


def _serve_satellite(cfg, repo, transcribe, ctx, raw, addr):
    scratch = Path(cfg["scratch_dir"]); scratch.mkdir(parents=True, exist_ok=True)
    try:
        conn = ctx.wrap_socket(raw, server_side=True)
    except Exception as e:  # noqa: BLE001
        core.log("orind", f"TLS handshake from {addr} failed: {e}")
        raw.close(); return
    rfile = conn.makefile("rb")
    try:
        hdr = wire.recv_header(rfile)
        if not hdr:
            return
        sat = hdr.get("satellite_id", "satellite")
        codec = hdr.get("codec", "pcm")
        core.log("orind", f"satellite '{sat}' connected from {addr[0]} (codec={codec})")
        seg = 0
        while True:
            try:
                payload = wire.recv_frame(rfile)
            except (ConnectionError, OSError):
                payload = None  # satellite dropped the link; treat as disconnect
            if payload is None:
                break
            wav = scratch / f"lan_{sat}_{seg:06d}.wav"
            try:
                codeclib.decode_to_wav(codec, payload, wav)
                text = handle_segment(cfg, repo, transcribe, wav, source=sat)
                if text:
                    core.log("orind", f"[{sat}] +{len(text)} chars committed")
            finally:
                # belt-and-braces: if decode/handle threw before the pipeline's
                # own finally deleted it, delete here too.
                if not cfg.get("keep_debug_audio", False) and wav.exists():
                    try:
                        os.remove(wav)
                    except FileNotFoundError:
                        pass
            seg += 1
        core.log("orind", f"satellite '{sat}' disconnected")
    finally:
        try:
            rfile.close(); conn.close()
        except Exception:  # noqa: BLE001
            pass


def _advertise_mdns(cfg):
    """Advertise _earbox._tcp so satellites can auto-discover the Orin.
    Best-effort: uses python zeroconf if present, else logs the avahi service
    file to drop in. Never fatal."""
    try:
        from zeroconf import Zeroconf, ServiceInfo
        import socket as _s
        ip = _s.gethostbyname(_s.gethostname())
        info = ServiceInfo(
            "_earbox._tcp.local.",
            f"{cfg.get('mdns_instance', 'earbox-orin')}._earbox._tcp.local.",
            addresses=[_s.inet_aton(ip)],
            port=int(cfg["listen_port"]),
            properties={"codec": "opus", "v": "1"},
        )
        zc = Zeroconf()
        zc.register_service(info)
        core.log("orind", f"mDNS advertising _earbox._tcp on {ip}:{cfg['listen_port']}")
        cfg["_zc"] = zc  # keep a ref alive
    except Exception as e:  # noqa: BLE001
        core.log("orind", f"mDNS advertise unavailable ({e}); "
                          "satellites must use a static orin_host. "
                          "See satellite/README for the avahi service file.")


# ---- main -------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="earbox Orin brain daemon")
    p.add_argument("--config", default=os.path.expanduser("~/.config/earbox/orin.toml"))
    p.add_argument("--mode", choices=["direct", "lan"], default=None,
                   help="direct = local XVF3800 USB; lan = satellite TLS server")
    p.add_argument("--stt", choices=["faster_whisper", "whisper_cli", "echo"],
                   default=None, help="override stt_backend")
    p.add_argument("--mac-direct", action="store_true",
                   help="dev only: use avfoundation instead of ALSA for direct mode")
    args = p.parse_args(argv)

    cfg = core.load_config(args.config, defaults=ORIN_DEFAULTS)
    if args.stt:
        cfg["stt_backend"] = args.stt
    if args.mac_direct:
        cfg["_mac_direct"] = True
    mode = args.mode or cfg.get("mode", "direct")

    repo = core.ensure_repo(cfg)
    transcribe = stt_mod.get_transcriber(cfg)
    if mode == "direct":
        run_direct(cfg, repo, transcribe)
    else:
        run_lan(cfg, repo, transcribe)


if __name__ == "__main__":
    main()
