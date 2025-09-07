#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

"$SCRIPT_DIR/install_minimum.sh"

sudo apt-get install -y --no-install-recommends \
  bettercap kismet gpsd i2c-tools python3-pil python3-flask \
  ufw fail2ban

echo "Recommended dependencies installed."

