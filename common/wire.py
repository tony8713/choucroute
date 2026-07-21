#!/usr/bin/env python3
"""
wire - the LAN hop protocol between a Pi satellite and the Orin brain.

This is the OPTIONAL multi-room path. The founder unit (Orin + reSpeaker
XVF3800 USB mic) captures locally with no network at all; this module only
matters when a Pi 4 satellite streams a remote room to the Orin.

Framing (over a single TLS/TCP connection, LAN-only):
  - one JSON header line, newline-terminated:
        {"satellite_id": "kitchen", "codec": "pcm"|"opus",
         "sample_rate": 16000, "segment_seconds": 30, "v": 1}
  - then a sequence of length-prefixed frames, each = one VAD-passed segment:
        4-byte big-endian unsigned length  ||  payload bytes
    payload is a WAV blob ("pcm") or an Ogg/Opus blob ("opus").

Encryption: TLS with a self-signed cert the satellite pins (cafile = the Orin's
cert). Simple and adequate for a trusted LAN. PRODUCTION HARDENING TODO: run the
hop inside WireGuard and/or mutual-TLS with per-satellite client certs, and pin
the satellite identity. Do not ship the self-signed-only path to untrusted LANs.
"""

import json
import socket
import ssl
import struct

PROTOCOL_VERSION = 1
_LEN = struct.Struct(">I")
MAX_FRAME = 32 * 1024 * 1024   # 32MB guard; a 30s 16k mono wav is ~1MB


# ---- header -----------------------------------------------------------------

def send_header(sock, satellite_id, codec, sample_rate, segment_seconds):
    hdr = {
        "v": PROTOCOL_VERSION,
        "satellite_id": satellite_id,
        "codec": codec,
        "sample_rate": sample_rate,
        "segment_seconds": segment_seconds,
    }
    line = (json.dumps(hdr) + "\n").encode("utf-8")
    sock.sendall(line)


def recv_header(rfile):
    line = rfile.readline()
    if not line:
        return None
    hdr = json.loads(line.decode("utf-8"))
    if hdr.get("v") != PROTOCOL_VERSION:
        raise ValueError(f"unsupported protocol version {hdr.get('v')}")
    return hdr


# ---- frames -----------------------------------------------------------------

def send_frame(sock, payload):
    if len(payload) > MAX_FRAME:
        raise ValueError("frame too large")
    sock.sendall(_LEN.pack(len(payload)))
    sock.sendall(payload)


def recv_frame(rfile):
    head = _read_exactly(rfile, 4)
    if head is None:
        return None
    (n,) = _LEN.unpack(head)
    if n > MAX_FRAME:
        raise ValueError("frame too large")
    if n == 0:
        return b""
    body = _read_exactly(rfile, n)
    if body is None:
        raise ConnectionError("truncated frame")
    return body


def _read_exactly(rfile, n):
    buf = rfile.read(n)
    if not buf:
        return None
    while len(buf) < n:
        more = rfile.read(n - len(buf))
        if not more:
            return None
        buf += more
    return buf


# ---- TLS --------------------------------------------------------------------

def server_tls_context(certfile, keyfile):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def client_tls_context(cafile, server_hostname_check=False):
    # Self-signed: verify against the pinned Orin cert (cafile). We disable
    # hostname checking because the LAN address/mDNS name won't match the CN;
    # trust is pinned to the cert itself. PRODUCTION: issue certs with a proper
    # SAN and enable hostname verification, or move to mutual-TLS/WireGuard.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cafile=cafile)
    ctx.check_hostname = server_hostname_check
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def connect(host, port, ctx, timeout=10):
    raw = socket.create_connection((host, port), timeout=timeout)
    return ctx.wrap_socket(raw, server_hostname=host if ctx.check_hostname else None)
