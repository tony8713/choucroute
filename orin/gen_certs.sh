#!/usr/bin/env bash
# Generate a self-signed TLS cert+key for the Orin's LAN satellite server.
# Simple LAN trust: satellites pin this cert (tls_cafile). PRODUCTION HARDENING
# TODO: move to WireGuard and/or mutual-TLS with per-satellite client certs.
set -euo pipefail
OUT_DIR=${1:-/opt/earbox/tls}
CN=${EARBOX_ORIN_CN:-earbox-orin.local}
mkdir -p "$OUT_DIR"
if [ -f "$OUT_DIR/orin.crt" ] && [ -f "$OUT_DIR/orin.key" ]; then
  echo "[earbox] certs already present in $OUT_DIR"; exit 0
fi
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$OUT_DIR/orin.key" -out "$OUT_DIR/orin.crt" \
  -days 3650 -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1"
chmod 600 "$OUT_DIR/orin.key"
echo "[earbox] wrote $OUT_DIR/orin.crt (+ orin.key). Copy orin.crt to each satellite as tls_cafile."
