#!/usr/bin/env bash
set -euo pipefail

SRC_DIR=${1:-$(pwd)}
DEST_DIR=/opt/momo
ENABLE_OLED=${ENABLE_OLED:-0}
NO_START=${NO_START:-0}
FORCE_SYNC=${FORCE_SYNC:-1}

echo "[momo] Installing to ${DEST_DIR} from ${SRC_DIR}"

sudo mkdir -p "${DEST_DIR}"
if [[ ! -d "${DEST_DIR}/.git" || "${FORCE_SYNC}" == "1" ]]; then
  echo "[momo] Syncing repository contents..."
  sudo rsync -a --delete --exclude ".git" "${SRC_DIR}/" "${DEST_DIR}/"
fi

echo "[momo] Installing Python package (editable)"
sudo python3 -m pip install --upgrade pip >/dev/null
sudo pip3 install -e "${DEST_DIR}" >/dev/null

echo "[momo] Installing systemd unit files"
sudo cp -f "${DEST_DIR}/deploy/systemd/momo.service" /etc/systemd/system/momo.service
sudo cp -f "${DEST_DIR}/deploy/systemd/momo-oled.service" /etc/systemd/system/momo-oled.service
sudo systemctl daemon-reload
sudo systemctl enable momo.service
if [[ "${ENABLE_OLED}" == "1" ]]; then
  sudo systemctl enable momo-oled.service
fi

if [[ "${NO_START}" != "1" ]]; then
  echo "[momo] Starting services"
  sudo systemctl restart momo.service
  if [[ "${ENABLE_OLED}" == "1" ]]; then
    sudo systemctl restart momo-oled.service || true
  fi
fi

echo "[momo] Done. Use 'systemctl status momo' to verify."


