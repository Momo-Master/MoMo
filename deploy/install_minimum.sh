#!/usr/bin/env bash
set -euo pipefail

# Minimal dependencies for MoMo
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  hcxdumptool hcxtools aircrack-ng tcpdump python3-pip python3-venv \
  logrotate

echo "Minimum dependencies installed."

