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


