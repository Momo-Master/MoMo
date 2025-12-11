#!/usr/bin/env bash
set -euo pipefail

log(){ echo "[setup_systemd] $*"; }

UNIT_DIR=/etc/systemd/system
CONF_DIR=/etc/momo
DEFAULTS=/etc/default/momo
REPO_DIR=${REPO_DIR:-/opt/momo}

mkdir -p "$CONF_DIR"
mkdir -p "$REPO_DIR"
mkdir -p "$UNIT_DIR/momo.service.d"
touch "$UNIT_DIR/momo.service.d/env.conf"

# Ensure config exists once
if [ ! -f "$CONF_DIR/momo.yml" ]; then
  if [ -f "$REPO_DIR/configs/momo.yml" ]; then
    cp "$REPO_DIR/configs/momo.yml" "$CONF_DIR/momo.yml"
    log "Installed default config to $CONF_DIR/momo.yml"
  else
    log "WARN: No repo config found at $REPO_DIR/configs/momo.yml"
  fi
fi

# Create defaults env file if missing
if [ ! -f "$DEFAULTS" ]; then
  cat > "$DEFAULTS" <<EOF
# MoMo environment overrides
# MOMO_UI_TOKEN=
# MOMO_UI_PASSWORD=
EOF
  log "Created $DEFAULTS"
fi

# Choose unit based on venv presence
if [ -x "$REPO_DIR/.venv/bin/momo" ]; then
  install -m 0644 "$REPO_DIR/deploy/systemd/momo.service" "$UNIT_DIR/momo.service"
  USED_UNIT=momo.service
else
  install -m 0644 "$REPO_DIR/deploy/systemd/momo-global.service" "$UNIT_DIR/momo.service"
  USED_UNIT=momo.service
fi

# Ensure drop-in env directory exists
mkdir -p "$UNIT_DIR/momo.service.d"
touch "$UNIT_DIR/momo.service.d/env.conf"

systemctl daemon-reload
systemctl enable --now momo.service
log "Enabled momo.service using unit: $USED_UNIT"
log "ExecStart: $(systemctl show -p ExecStart momo | cut -d= -f2-)"
log "Config: $CONF_DIR/momo.yml"

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


