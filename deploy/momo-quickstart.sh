#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for MoMo on Raspberry Pi / Debian
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Project-MoMo/MoMo/main/deploy/momo-quickstart.sh | sudo bash

ENABLE_WEB=${ENABLE_WEB:-1}
ENABLE_ACTIVE_WIFI=${ENABLE_ACTIVE_WIFI:-0}
ENABLE_BETTERCAP=${ENABLE_BETTERCAP:-0}
ENABLE_CRACKING=${ENABLE_CRACKING:-0}

REPO_URL=${REPO_URL:-https://github.com/Project-MoMo/MoMo}
DEST=/opt/momo
ETC=/etc/momo
UNIT=/etc/systemd/system/momo.service
DROPIN_DIR=/etc/systemd/system/momo.service.d

log(){ echo "[momo-quickstart] $*"; }

require_root(){ if [ "${EUID:-$(id -u)}" -ne 0 ]; then echo "Run as root" >&2; exit 1; fi; }

pkg_install(){
  DEBIAN_FRONTEND=noninteractive apt-get update -y || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" || true
}

main(){
  require_root
  log "Installing base dependencies..."
  pkg_install git python3-venv python3-pip build-essential ufw curl ca-certificates
  log "Installing capture tools..."
  pkg_install hcxdumptool hcxpcapngtool || true
  [ "$ENABLE_BETTERCAP" = "1" ] && pkg_install bettercap || true
  [ "$ENABLE_CRACKING" = "1" ] && pkg_install hashcat john || true
  [ "$ENABLE_ACTIVE_WIFI" = "1" ] && pkg_install mdk4 aircrack-ng || true

  log "Cloning MoMo to ${DEST}..."
  mkdir -p "$DEST"
  if [ ! -d "$DEST/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$DEST"
  else
    git -C "$DEST" fetch --depth 1 origin || true
    git -C "$DEST" reset --hard origin/main || true
  fi

  log "Creating venv and installing..."
  python3 -m venv "$DEST/.venv"
  . "$DEST/.venv/bin/activate"
  pip install --upgrade pip setuptools wheel
  pip install -e "$DEST" || pip install "$DEST"

  log "Writing default config..."
  install -d "$ETC"
  [ ! -f "$ETC/defaults.yml" ] && cp "$DEST/configs/momo.yml" "$ETC/defaults.yml" || true
  if [ ! -f "$ETC/momo.yml" ]; then
    cp "$DEST/configs/momo.yml" "$ETC/momo.yml" || true
  fi

  # Token & drop-in
  if [ "$ENABLE_WEB" = "1" ]; then
    install -d "$DROPIN_DIR"
    if ! grep -q '^Environment=MOMO_UI_TOKEN=' "$DROPIN_DIR/env.conf" 2>/dev/null; then
      TOKEN=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
      printf "[Service]\nEnvironment=MOMO_UI_TOKEN=%s\n" "$TOKEN" > "$DROPIN_DIR/env.conf"
      log "Generated Web UI token (saved in env.conf)"
    fi
  fi

  log "Installing systemd unit..."
  MOMO_BIN="$DEST/.venv/bin/momo"
  cat > "$UNIT" <<EOF
[Unit]
Description=MoMo core service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DEST
ExecStart=$MOMO_BIN run -c /etc/momo/momo.yml
EnvironmentFile=-/etc/default/momo
EnvironmentFile=-/etc/systemd/system/momo.service.d/env.conf
Restart=always
RestartSec=2
LimitNOFILE=65535
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=true
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now momo || true

  # UFW
  if command -v ufw >/dev/null 2>&1; then
    ufw allow 22/tcp || true
    ufw allow 8081/tcp || true
    ufw allow 9091/tcp || true
    ufw allow 8083/tcp || true
  fi

  log "Done. Quick check:"
  echo "  Health:  http://127.0.0.1:8081/healthz"
  echo "  Metrics: http://127.0.0.1:9091/metrics"
  echo "  Web UI:  http://127.0.0.1:8083/"
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail

# MoMo Quickstart (cURL-able)
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/deploy/momo-quickstart.sh | bash

LOGFILE="/var/log/momo_install.log"

is_root() { [ "${EUID:-$(id -u)}" -eq 0 ]; }

require_root() {
  if ! is_root; then
    echo "[ERROR] This script must run as root. Re-run with sudo." >&2
    exit 1
  fi
}

detect_platform() {
  local model arch os codename
  arch=$(uname -m || true)
  if [ -r /proc/device-tree/model ]; then
    model=$(tr -d '\0' </proc/device-tree/model)
  else
    model="unknown"
  fi
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    os=$ID
    codename=${VERSION_CODENAME:-}
  else
    os="unknown"; codename=""
  fi
  echo "$model|$arch|$os|$codename"
}

main() {
  require_root
  local info model arch os codename
  info=$(detect_platform)
  IFS='|' read -r model arch os codename <<<"$info"

  if ! command -v curl >/dev/null 2>&1; then
    apt-get update -y || true
    apt-get install -y curl || true
  fi

  echo "[INFO] Detected: model=$model arch=$arch os=$os codename=$codename"
  if ! echo "$model" | grep -qi "Raspberry Pi 5"; then
    echo "[ERROR] Unsupported device. This quickstart targets Raspberry Pi 5." >&2
    echo "Model string: $model" >&2
    exit 1
  fi
  if [ "$arch" != "aarch64" ] && [ "$arch" != "arm64" ]; then
    echo "[ERROR] Unsupported arch: $arch (need aarch64)." >&2
    exit 1
  fi
  if [ "$os" != "debian" ] || [ "$codename" != "bookworm" ]; then
    echo "[ERROR] OS must be Debian Bookworm." >&2
    exit 1
  fi

  : "${REPO_RAW:-https://raw.githubusercontent.com/Project-MoMo/MoMo/main}"
  INSTALL_URL="${REPO_RAW}/deploy/install.sh"

  echo "[INFO] Fetching unified installer ..."
  tmpfile=$(mktemp)
  trap 'rm -f "$tmpfile"' EXIT
  if ! curl -fsSL "$INSTALL_URL" -o "$tmpfile"; then
    echo "[ERROR] Failed to download installer from $INSTALL_URL" >&2
    exit 1
  fi
  chmod +x "$tmpfile"

  export NONINTERACTIVE=1
  export MOMO_IFACE=${MOMO_IFACE:-wlan1}
  export MOMO_REG=${MOMO_REG:-TR}
  export ENABLE_OLED=${ENABLE_OLED:-0}
  export ENABLE_SECURITY=${ENABLE_SECURITY:-0}
  export LOGFILE

  echo "[INFO] Running installer (logging to $LOGFILE) ..."
  "$tmpfile" | tee -a "$LOGFILE"
}

main "$@"


