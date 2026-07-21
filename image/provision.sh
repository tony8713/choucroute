#!/usr/bin/env bash
# earbox provisioning: turn a fresh Raspberry Pi OS Lite (64-bit) into an earbox.
# Target: Raspberry Pi 5 (see docs/architecture.md for why NOT the Zero 2W).
# Run on the Pi as a sudo-capable user:  sudo bash provision.sh
set -euo pipefail

EARBOX_USER=earbox
EARBOX_HOME=/home/$EARBOX_USER
PREFIX=/opt/earbox
MODEL=${EARBOX_MODEL:-base}          # tiny|base ; base recommended on Pi 5
REPO_SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "[earbox] apt deps"
apt-get update
apt-get install -y --no-install-recommends \
  git build-essential cmake python3 alsa-utils libopenblas-dev ca-certificates curl

echo "[earbox] service user"
id -u "$EARBOX_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$EARBOX_USER"
usermod -aG audio "$EARBOX_USER"

echo "[earbox] build whisper.cpp (ARM64 NEON + OpenBLAS)"
mkdir -p "$PREFIX"
if [ ! -x "$PREFIX/bin/whisper-cli" ]; then
  tmp=$(mktemp -d)
  git clone --depth 1 https://github.com/ggml-org/whisper.cpp "$tmp/whisper.cpp"
  cmake -S "$tmp/whisper.cpp" -B "$tmp/whisper.cpp/build" \
        -DGGML_BLAS=1 -DGGML_NATIVE=1 -DCMAKE_BUILD_TYPE=Release
  cmake --build "$tmp/whisper.cpp/build" -j"$(nproc)" --config Release
  install -Dm755 "$tmp/whisper.cpp/build/bin/whisper-cli" "$PREFIX/bin/whisper-cli"
  ln -sf "$PREFIX/bin/whisper-cli" /usr/local/bin/whisper-cli
  rm -rf "$tmp"
fi

echo "[earbox] fetch model: $MODEL"
mkdir -p "$PREFIX/models"
MODEL_FILE="$PREFIX/models/ggml-$MODEL.bin"
if [ ! -f "$MODEL_FILE" ]; then
  curl -L -o "$MODEL_FILE" \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$MODEL.bin"
fi

echo "[earbox] install daemon"
mkdir -p "$PREFIX/daemon"
install -Dm755 "$REPO_SRC/daemon/earboxd.py"   "$PREFIX/daemon/earboxd.py"
install -Dm755 "$REPO_SRC/daemon/summarize.py" "$PREFIX/daemon/summarize.py"
install -Dm755 "$REPO_SRC/daemon/query.py"     "$PREFIX/daemon/query.py"

echo "[earbox] config"
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" "$EARBOX_HOME/.config/earbox"
if [ ! -f "$EARBOX_HOME/.config/earbox/config.toml" ]; then
  sed "s#/opt/earbox/models/ggml-base.bin#$MODEL_FILE#" \
      "$REPO_SRC/daemon/config.example.toml" \
      > "$EARBOX_HOME/.config/earbox/config.toml"
  chown "$EARBOX_USER:$EARBOX_USER" "$EARBOX_HOME/.config/earbox/config.toml"
fi

echo "[earbox] tmpfs scratch (raw audio never hits the SD card)"
grep -q '/dev/shm/earbox' /etc/fstab 2>/dev/null || \
  echo "tmpfs /dev/shm/earbox tmpfs defaults,noexec,nosuid,size=64M 0 0" >> /etc/fstab
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" /dev/shm/earbox

echo "[earbox] init memory repo"
sudo -u "$EARBOX_USER" git init -q "$EARBOX_HOME/earbox-memory" || true

echo "[earbox] systemd units"
install -Dm644 "$REPO_SRC/image/earboxd.service"        /etc/systemd/system/earboxd.service
install -Dm644 "$REPO_SRC/image/earbox-summary.service" /etc/systemd/system/earbox-summary.service
install -Dm644 "$REPO_SRC/image/earbox-summary.timer"   /etc/systemd/system/earbox-summary.timer
systemctl daemon-reload
systemctl enable --now earboxd.service
systemctl enable --now earbox-summary.timer

echo "[earbox] done. status:"
systemctl --no-pager status earboxd.service || true
echo
echo "Mute:   touch $EARBOX_HOME/.earbox-muted   (or wire the GPIO switch, set gpio_mute_pin)"
echo "Verify: arecord -l   &&   journalctl -u earboxd -f"
