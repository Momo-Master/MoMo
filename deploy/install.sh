#!/usr/bin/env bash
set -euo pipefail

# MoMo Unified Installer (idempotent)
# Env flags:
# NONINTERACTIVE=1, MOMO_IFACE, MOMO_REG, ENABLE_OLED=0/1, ENABLE_SECURITY=0/1, NO_START=1, SKIP_DKMS=1

LOGFILE=${LOGFILE:-/var/log/momo_install.log}
REPO_DIR=${REPO_DIR:-/opt/momo}
VENV_DIR="$REPO_DIR/.venv"
BACKUP_DIR=${BACKUP_DIR:-/opt/momo_backups}

log() { echo "[$(date -u +%F_%T)] $*" | tee -a "$LOGFILE"; }
is_root() { [ "${EUID:-$(id -u)}" -eq 0 ]; }
require_root() { if ! is_root; then echo "[ERROR] Run as root" >&2; exit 1; fi }

apt_install() {
  local pkgs=("$@")
  DEBIAN_FRONTEND=noninteractive apt-get update -y || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
}

ensure_packages() {
  log "Installing base packages ..."
  apt_install git python3-venv python3-pip build-essential dkms libpcap-dev libssl-dev iw rfkill usbutils curl unzip logrotate shellcheck || true
  log "Installing capture tools ..."
  apt_install hcxdumptool hcxtools aircrack-ng || true
}

ensure_repo() {
  mkdir -p "$REPO_DIR"
  if [ ! -d "$REPO_DIR/.git" ]; then
    log "Cloning MoMo to $REPO_DIR"
    git clone --depth 1 "${REPO_URL:-https://github.com/Project-MoMo/MoMo}.git" "$REPO_DIR" || true
  else
    log "Updating repo"
    git -C "$REPO_DIR" fetch --depth 1 origin || true
    git -C "$REPO_DIR" reset --hard "${REPO_REF:-origin/main}" || true
  fi
}

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    log "Creating venv"
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  . "$VENV_DIR/bin/activate"
  pip install --upgrade pip setuptools wheel
  log "Installing MoMo (editable)"
  pip install -e "$REPO_DIR"[dev] || pip install -e "$REPO_DIR"
}

ensure_config() {
  mkdir -p "$BACKUP_DIR" "$REPO_DIR/logs" "$REPO_DIR/configs"
  chown -R root:root "$REPO_DIR" || true
  if [ ! -f "$REPO_DIR/configs/momo.yml" ]; then
    cp "$REPO_DIR/configs/momo.yml" "$REPO_DIR/configs/momo.yml" 2>/dev/null || true
  fi
  # apply patches
  iface=${MOMO_IFACE:-wlan1}
  reg=${MOMO_REG:-TR}
  sed -i "s/^\s*name:\s*.*/  name: ${iface}/" "$REPO_DIR/configs/momo.yml" || true
  sed -i "s/^\s*regulatory_domain:\s*.*/  regulatory_domain: ${reg}/" "$REPO_DIR/configs/momo.yml" || true
  # enable autobackup with path
  if ! grep -q "autobackup" "$REPO_DIR/configs/momo.yml"; then
    printf "\nplugins:\n  enabled:\n    - autobackup\n  options:\n    autobackup:\n      path: %s\n" "$BACKUP_DIR" >> "$REPO_DIR/configs/momo.yml"
  else
    sed -i "s#^\(\s*path:\s*\).*#\1${BACKUP_DIR//#/\\#}#" "$REPO_DIR/configs/momo.yml" || true
  fi
  # short rotation for first run demo
  if ! grep -q "rotate_secs" "$REPO_DIR/configs/momo.yml"; then
    printf "\n  rotate_secs: 60\n" >> "$REPO_DIR/configs/momo.yml"
  fi
}

ensure_driver() {
  if [ "${SKIP_DKMS:-0}" = "1" ]; then
    log "Skipping DKMS per flag"
    return 0
  fi
  if lsusb | grep -qi "2357:0120"; then
    log "Ensuring rtl8821au dkms ..."
    if [ ! -d /usr/src/rtl8821au-20210708 ]; then
      git clone --depth 1 https://github.com/morrownr/8821au-20210708 /usr/src/rtl8821au-20210708 || true
    fi
    dkms add -m rtl8821au -v 20210708 2>/dev/null || true
    dkms build -m rtl8821au -v 20210708 || true
    dkms install -m rtl8821au -v 20210708 || true
    modprobe 8821au || true
  else
    log "Target USB adapter not detected; skipping driver"
  fi
}

ensure_services() {
  install -m 0644 "$REPO_DIR/deploy/systemd/momo.service" /etc/systemd/system/momo.service
  if [ "${ENABLE_OLED:-0}" = "1" ]; then
    install -m 0644 "$REPO_DIR/deploy/systemd/momo-oled.service" /etc/systemd/system/momo-oled.service
  fi
  # Web UI (optional)
  install -m 0644 "$REPO_DIR/deploy/systemd/momo-web.service" /etc/systemd/system/momo-web.service || true
  systemctl daemon-reload
  if [ "${NO_START:-0}" != "1" ]; then
    systemctl enable --now momo.service || true
    if [ "${ENABLE_OLED:-0}" = "1" ]; then systemctl enable --now momo-oled.service || true; fi
    if [ "${ENABLE_WEB:-0}" = "1" ]; then systemctl enable --now momo-web.service || true; fi
  fi
}

ensure_systemd_setup() {
  bash "$REPO_DIR/deploy/setup_systemd.sh"
}

ensure_logrotate() {
  install -m 0644 "$REPO_DIR/deploy/logrotate.d/momo" /etc/logrotate.d/momo
}

ensure_security() {
  if [ "${ENABLE_SECURITY:-0}" != "1" ]; then return 0; fi
  log "Applying baseline security (UFW, fail2ban)"
  apt_install ufw fail2ban || true
  ufw allow 22/tcp || true
  ufw allow 8080/tcp || true
  ufw allow 9090/tcp || true
  ufw --force enable || true
  systemctl enable --now fail2ban || true
}

main() {
  require_root
  log "Starting MoMo installer"
  ensure_packages
  ensure_repo
  ensure_venv
  ensure_config
  ensure_driver
  ensure_logrotate
  ensure_systemd_setup
  ensure_services
  ensure_security
  log "Install complete. Summary:"
  log "  Repo: $REPO_DIR"
  log "  Venv: $VENV_DIR"
  log "  Config: $REPO_DIR/configs/momo.yml"
  log "  Backup dir: $BACKUP_DIR"
  systemctl is-active --quiet momo && log "  Service: active" || log "  Service: inactive"
}

main "$@"


