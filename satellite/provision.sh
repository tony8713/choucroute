#!/usr/bin/env bash
# earbox SATELLITE provisioning: turn a fresh Raspberry Pi OS Lite (64-bit) on a
# Pi 4 into a mic satellite that streams a room to the Orin over the LAN.
# OPTIONAL multi-room tier. The founder unit does not need this.
# Run on the Pi:  sudo bash provision.sh
set -euo pipefail

EARBOX_USER=earbox
EARBOX_HOME=/home/$EARBOX_USER
PREFIX=/opt/earbox
REPO_SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "[earbox] apt deps"
apt-get update
apt-get install -y --no-install-recommends \
  git python3 python3-pip alsa-utils opus-tools ca-certificates \
  python3-zeroconf avahi-utils

echo "[earbox] service user"
id -u "$EARBOX_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$EARBOX_USER"
usermod -aG audio "$EARBOX_USER"

echo "[earbox] install code (satellite + shared common)"
install -d "$PREFIX/satellite" "$PREFIX/common" "$PREFIX/tls"
install -Dm755 "$REPO_SRC"/satellite/satellited.py "$PREFIX/satellite/satellited.py"
install -Dm644 "$REPO_SRC"/common/*.py "$PREFIX/common/"

echo "[earbox] config"
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" "$EARBOX_HOME/.config/earbox"
if [ ! -f "$EARBOX_HOME/.config/earbox/satellite.toml" ]; then
  install -m644 "$REPO_SRC/satellite/config.example.toml" \
      "$EARBOX_HOME/.config/earbox/satellite.toml"
  chown "$EARBOX_USER:$EARBOX_USER" "$EARBOX_HOME/.config/earbox/satellite.toml"
fi

echo "[earbox] tmpfs scratch (zero storage on the Pi)"
grep -q '/dev/shm/earbox' /etc/fstab 2>/dev/null || \
  echo "tmpfs /dev/shm/earbox tmpfs defaults,noexec,nosuid,size=64M 0 0" >> /etc/fstab
install -d -o "$EARBOX_USER" -g "$EARBOX_USER" /dev/shm/earbox

echo "[earbox] TLS trust: copy the Orin's cert here as $PREFIX/tls/orin.crt"
echo "  scp earbox@<orin>:/opt/earbox/tls/orin.crt $PREFIX/tls/orin.crt"
echo "  then set satellite_id, orin_host (or leave empty for mDNS) in satellite.toml"

echo "[earbox] systemd unit"
install -Dm644 "$REPO_SRC/satellite/systemd/earbox-satellite.service" \
    /etc/systemd/system/earbox-satellite.service
systemctl daemon-reload
echo "[earbox] enable once the Orin cert + config are in place:"
echo "  sudo systemctl enable --now earbox-satellite.service"
echo
echo "Mic check: arecord -l   (set alsa_device in satellite.toml)"
echo "Logs:      journalctl -u earbox-satellite -f"
