#!/usr/bin/env bash
# earbox ORIN provisioning: turn a Jetson Orin Nano Super (JetPack 6.x / L4T,
# Ubuntu 22.04) into the earbox brain. Founder unit = Orin + reSpeaker XVF3800
# USB mic, single box, no Pi satellite required.
#
# UNTESTED-ON-TARGET: there is no Orin in the dev environment. The faster-whisper
# / CUDA steps below are written to JetPack 6.x conventions but MUST be run and
# adjusted on the real device (D3). Run as a sudo-capable user:
#   sudo bash provision.sh
set -euo pipefail

EARBOX_USER=earbox
EARBOX_HOME=/home/$EARBOX_USER
PREFIX=/opt/earbox
REPO_SRC="$(cd "$(dirname "$0")/.." && pwd)"
MODE=${EARBOX_MODE:-direct}          # direct (XVF3800) | lan (satellite server)

# Persistent storage root. SPRINT: the Orin runs from the 128GB microSD ONLY;
# there is NO NVMe /data mount. Default the data root to the service user's home
# on the SD and use /data ONLY if a real filesystem is mounted there. Override
# with EARBOX_DATA=/path. Code paths (models, git memory) resolve from this.
STORAGE_ROOT="${EARBOX_DATA:-$(mountpoint -q /data 2>/dev/null && echo /data || echo "$EARBOX_HOME")}"
MEMORY_REPO="$STORAGE_ROOT/earbox-memory"
MODELS_DIR="$STORAGE_ROOT/earbox-models"
echo "[earbox] storage root: $STORAGE_ROOT (memory=$MEMORY_REPO models=$MODELS_DIR)"

echo "[earbox] apt deps"
apt-get update
apt-get install -y --no-install-recommends \
  git python3 python3-pip python3-venv alsa-utils ffmpeg openssl \
  ca-certificates curl avahi-daemon

echo "[earbox] service user"
id -u "$EARBOX_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$EARBOX_USER"
usermod -aG audio "$EARBOX_USER"

echo "[earbox] python venv + faster-whisper (CUDA)"
# faster-whisper rides CTranslate2. On JetPack 6.x CTranslate2 must be a CUDA
# build for the Jetson (aarch64 + CUDA 12). The plain PyPI wheel is often CPU or
# desktop-CUDA only; if `device=cuda` fails on-device, build CTranslate2 from
# source against the JetPack CUDA/cuDNN, or use a Jetson-specific wheel. VERIFY
# ON D3.
python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --upgrade pip
"$PREFIX/venv/bin/pip" install faster-whisper zeroconf || {
  echo "[earbox] WARN: faster-whisper install needs attention on-device (CTranslate2 CUDA)."
}

echo "[earbox] install code (orin + shared common + daemon egress)"
install -d "$PREFIX/orin" "$PREFIX/common" "$PREFIX/daemon"
install -Dm755 "$REPO_SRC"/orin/*.py     "$PREFIX/orin/"
install -Dm644 "$REPO_SRC"/common/*.py   "$PREFIX/common/"
install -Dm755 "$REPO_SRC"/daemon/summarize.py "$PREFIX/daemon/summarize.py"
install -Dm755 "$REPO_SRC"/daemon/query.py     "$PREFIX/daemon/query.py"

echo "[earbox] optional whisper.cpp fallback model (whisper_cli backend)"
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" "$STORAGE_ROOT" "$MODELS_DIR"
if [ "${EARBOX_FETCH_GGML:-0}" = "1" ] && [ ! -f "$MODELS_DIR/ggml-base.bin" ]; then
  curl -L -o "$MODELS_DIR/ggml-base.bin" \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
  chown "$EARBOX_USER:$EARBOX_USER" "$MODELS_DIR/ggml-base.bin"
fi

echo "[earbox] config"
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" "$EARBOX_HOME/.config/earbox"
if [ ! -f "$EARBOX_HOME/.config/earbox/orin.toml" ]; then
  sed -e "s/^mode = \"direct\"/mode = \"$MODE\"/" \
      -e "s#^memory_repo = .*#memory_repo = \"$MEMORY_REPO\"#" \
      -e "s#^model_path = .*#model_path = \"$MODELS_DIR/ggml-base.bin\"#" \
      "$REPO_SRC/orin/config.example.toml" \
      > "$EARBOX_HOME/.config/earbox/orin.toml"
  chown "$EARBOX_USER:$EARBOX_USER" "$EARBOX_HOME/.config/earbox/orin.toml"
fi

echo "[earbox] tmpfs scratch (raw audio never hits disk)"
grep -q '/dev/shm/earbox' /etc/fstab 2>/dev/null || \
  echo "tmpfs /dev/shm/earbox tmpfs defaults,noexec,nosuid,size=128M 0 0" >> /etc/fstab
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" /dev/shm/earbox

echo "[earbox] TLS certs for the LAN hop (only needed for mode=lan)"
if [ "$MODE" = "lan" ]; then
  bash "$REPO_SRC/orin/gen_certs.sh" "$PREFIX/tls"
  chown -R "$EARBOX_USER:$EARBOX_USER" "$PREFIX/tls"
  echo "[earbox] copy $PREFIX/tls/orin.crt to each satellite as tls_cafile."
fi

echo "[earbox] init memory repo"
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" "$MEMORY_REPO"
sudo -u "$EARBOX_USER" git init -q "$MEMORY_REPO" || true

echo "[earbox] systemd units"
# Run orind from the venv python so faster-whisper is importable.
sed -e "s#/usr/bin/python3#$PREFIX/venv/bin/python3#" \
    -e "s#/home/earbox/earbox-memory#$MEMORY_REPO#g" \
    "$REPO_SRC/orin/systemd/orind.service" > /etc/systemd/system/orind.service
sed "s#/home/earbox/earbox-memory#$MEMORY_REPO#g" \
    "$REPO_SRC/orin/systemd/earbox-summary.service" > /etc/systemd/system/earbox-summary.service
install -Dm644 "$REPO_SRC/orin/systemd/earbox-summary.timer"   /etc/systemd/system/earbox-summary.timer
systemctl daemon-reload
systemctl enable --now orind.service
systemctl enable --now earbox-summary.timer

echo "[earbox] done. status:"
systemctl --no-pager status orind.service || true
echo
echo "XVF3800 check:  arecord -l   (find the reSpeaker card, set usb_capture_device/usb_asr_channel)"
echo "Bench (D3):     time the faster-whisper small vs medium int8 RTF in real kitchen noise"
echo "Storage:        $STORAGE_ROOT (SD-only sprint; set EARBOX_DATA or mount /data to relocate)"
echo "Mute:           touch $EARBOX_HOME/.earbox-muted"
echo "Logs:           journalctl -u orind -f"
