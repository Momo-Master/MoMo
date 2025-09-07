#!/usr/bin/env bash
set -euo pipefail

echo "[momo] Installing UFW and Fail2ban"
sudo apt-get update
sudo apt-get install -y --no-install-recommends ufw fail2ban

echo "[momo] Configuring UFW"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
yes | sudo ufw enable || true

echo "[momo] Fail2ban installed. Customize /etc/fail2ban/jail.local as needed."
systemctl enable --now fail2ban

echo "[momo] Security baseline applied."


