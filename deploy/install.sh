#!/usr/bin/env bash
set -euo pipefail

# MoMo Unified Installer (idempotent)
# Env flags:
# NONINTERACTIVE=1, MOMO_IFACE, MOMO_REG, ENABLE_OLED=0/1, ENABLE_SECURITY=0/1, ENABLE_WEB=0/1, NO_START=1, SKIP_DKMS=1, ROTATE_TOKEN=1,
# ENABLE_ACTIVE_WIFI=0/1, ENABLE_BETTERCAP=0/1, ENABLE_CRACKING=0/1, WEB_BIND=0.0.0.0

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
  if [ "${ENABLE_ACTIVE_WIFI:-0}" = "1" ]; then
    apt_install mdk4 aircrack-ng || true
  fi
  if [ "${ENABLE_BETTERCAP:-0}" = "1" ]; then
    apt_install bettercap || true
  fi
  if [ "${ENABLE_CRACKING:-0}" = "1" ]; then
    apt_install hashcat john || true
  fi
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
  # copy defaults to /etc/momo/defaults.yml if missing
  mkdir -p /etc/momo
  if [ ! -f /etc/momo/defaults.yml ] && [ -f "$REPO_DIR/configs/momo.yml" ]; then
    cp "$REPO_DIR/configs/momo.yml" /etc/momo/defaults.yml || true
  fi
  # apply patches
  iface=${MOMO_IFACE:-wlan1}
  reg=${MOMO_REG:-TR}
  sed -i "s/^\s*name:\s*.*/  name: ${iface}/" "$REPO_DIR/configs/momo.yml" || true
  sed -i "s/^\s*regulatory_domain:\s*.*/  regulatory_domain: ${reg}/" "$REPO_DIR/configs/momo.yml" || true
  # web defaults (fill only if missing)
  if [ "${ENABLE_WEB:-1}" = "1" ]; then
    if [ -z "${MOMO_UI_TOKEN:-}" ]; then
      MOMO_UI_TOKEN=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
      export MOMO_UI_TOKEN
    fi
    # ensure drop-in
    mkdir -p /etc/systemd/system/momo.service.d
    cat > /etc/systemd/system/momo.service.d/env.conf <<EOF
[Service]
Environment=MOMO_UI_TOKEN=${MOMO_UI_TOKEN}
EOF
    # web bind fill
    wb=${WEB_BIND:-0.0.0.0}
    grep -q '^web:' "$REPO_DIR/configs/momo.yml" || printf '\nweb:\n  enabled: true\n  bind_host: %s\n  bind_port: 8082\n  token_env_var: MOMO_UI_TOKEN\n' "$wb" >> "$REPO_DIR/configs/momo.yml"
    # health/metrics fill
    grep -q '^health:' "$REPO_DIR/configs/momo.yml" || printf '\nhealth:\n  bind_host: 0.0.0.0\n  port: 8081\n' >> "$REPO_DIR/configs/momo.yml"
    grep -q '^metrics:' "$REPO_DIR/configs/momo.yml" || printf '\nmetrics:\n  bind_host: 0.0.0.0\n  port: 9091\n' >> "$REPO_DIR/configs/momo.yml"
  fi
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
  # optional plugins enablement
  if [ "${ENABLE_ACTIVE_WIFI:-0}" = "1" ]; then
    sed -i 's/^\(\s*enabled: \[.*\)\]/\1, "active_wifi"]/' "$REPO_DIR/configs/momo.yml" || true
    sed -i 's/^\(\s*active_wifi:\)/\1\n      enabled: true/' "$REPO_DIR/configs/momo.yml" || true
  fi
  if [ "${ENABLE_BETTERCAP:-0}" = "1" ]; then
    # no direct config; plugin reads options.plugins.bettercap if added later
    true
  fi
  if [ "${ENABLE_CRACKING:-0}" = "1" ]; then
    # enable cracker by plugin list
    sed -i 's/^\(\s*enabled: \[.*\)\]/\1, "cracker"]/' "$REPO_DIR/configs/momo.yml" || true
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
    if [ "${ENABLE_WEB:-1}" = "1" ]; then systemctl enable --now momo-web.service || true; fi
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
  ufw allow 8081/tcp || true
  ufw allow 9091/tcp || true
  ufw allow 8082/tcp || true
  ufw --force enable || true
  systemctl enable --now fail2ban || true
}

first_non_loopback_ip() {
  hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++){if($i!~"^127\.") {print $i; exit}}}'
}

ensure_token() {
  local dropin_dir=/etc/systemd/system/momo.service.d
  local env_file="$dropin_dir/env.conf"
  local token_file="$REPO_DIR/.momo_ui_token"
  mkdir -p "$dropin_dir"
  local current_token=""
  if [ -f "$env_file" ]; then
    current_token=$(grep -E "^Environment=MOMO_UI_TOKEN=" "$env_file" | sed 's/^Environment=MOMO_UI_TOKEN=//') || true
  fi
  if [ "${ROTATE_TOKEN:-0}" = "1" ]; then current_token=""; fi
  if [ -z "$current_token" ]; then
    # generate 32-char base64url without padding
    local token
    token=$(openssl rand -base64 48 | tr '+/' '-_' | tr -d '=\n' | cut -c1-32)
    echo "[Service]" > "$env_file"
    echo "Environment=MOMO_UI_TOKEN=$token" >> "$env_file"
    echo -n "$token" > "$token_file"
    chmod 600 "$token_file"
    log "Generated MOMO_UI_TOKEN and wrote to $env_file and $token_file"
    systemctl daemon-reload || true
  else
    if [ ! -f "$token_file" ]; then
      echo -n "$current_token" > "$token_file" && chmod 600 "$token_file"
    fi
  fi
}

main() {
  require_root
  log "Starting MoMo installer"
  ensure_packages
  ensure_repo
  ensure_venv
  ensure_config
  ensure_token
  ensure_driver
  ensure_logrotate
  ensure_systemd_setup
  ensure_services
  ensure_security
  # UFW rule for Web if enabled
  if command -v ufw >/dev/null 2>&1 && [ "${ENABLE_WEB:-1}" = "1" ]; then
    ufw allow 8082/tcp || true
  fi
  # Print URLs and token
  local ip
  ip=$(first_non_loopback_ip)
  local token
  if [ -f "$REPO_DIR/.momo_ui_token" ]; then token=$(cat "$REPO_DIR/.momo_ui_token"); else token=""; fi
  log "Health:  http://$ip:8081/healthz"
  log "Metrics: http://$ip:9091/metrics"
  log "Web UI:  http://$ip:8082/"
  if [ -n "$token" ]; then
    log "Token file: $REPO_DIR/.momo_ui_token"
    log "API sample: curl -H \"Authorization: Bearer $token\" http://$ip:8082/api/status"
  fi
  log "Run setup wizard: sudo momo wizard"
  log "Install systemd unit: sudo momo systemd install"
  log "Install complete. Summary:"
  log "  Repo: $REPO_DIR"
  log "  Venv: $VENV_DIR"
  log "  Config: $REPO_DIR/configs/momo.yml"
  log "  Backup dir: $BACKUP_DIR"
  systemctl is-active --quiet momo && log "  Service: active" || log "  Service: inactive"
}

main "$@"


