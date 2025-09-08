#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=/opt/momo
VENV_DIR=$REPO_DIR/.venv
BACKUP_DIR=${BACKUP_DIR:-/opt/momo_backups}

log() { echo "[firstboot] $(date -u +%F_%T) $*"; }

ensure_driver() {
  if command -v lsusb >/dev/null 2>&1 && lsusb | grep -qi "2357:0120"; then
    if command -v dkms >/dev/null 2>&1; then
      dkms build -m rtl8821au -v 20210708 || true
      dkms install -m rtl8821au -v 20210708 || true
      modprobe 8821au || true
    fi
  fi
}

persist_regdomain() {
  reg=${MOMO_REG:-TR}
  iw reg set "$reg" || true
  # rfkill/CRDA style configs differ; try modern location
  if [ -f /etc/default/crda ]; then
    sed -i "s/^REGDOMAIN=.*/REGDOMAIN=${reg}/" /etc/default/crda || true
  fi
}

ensure_paths() {
  mkdir -p "$BACKUP_DIR" "$REPO_DIR/logs/meta"
  chown -R root:root "$REPO_DIR" || true
}

interface_fallback() {
  if ! ip link show wlan1 >/dev/null 2>&1; then
    log "wlan1 missing, setting temporary interface.name=wlan0"
    sed -i "s/^\s*name:\s*.*/  name: wlan0/" "$REPO_DIR/configs/momo.yml" || true
  fi
}

emit_diag() {
  if [ -x "$VENV_DIR/bin/python" ]; then
    "$VENV_DIR/bin/python" -m momo.cli diag > "$REPO_DIR/logs/meta/firstboot_diag.txt" 2>&1 || true
  fi
}

main() {
  ensure_paths
  ensure_driver
  persist_regdomain
  interface_fallback
  emit_diag
  touch "$REPO_DIR/.firstboot_done"
  log "firstboot completed"
}

main "$@"


