#!/bin/bash -e
# ==============================================================================
# MoMo Installation Script (runs in chroot)
# ==============================================================================

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            🔥 Installing MoMo...                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Optional packages - install if available (not in all repos)
echo "[momo] Installing optional packages..."
apt-get install -y --no-install-recommends aircrack-ng || echo "aircrack-ng not available"
apt-get install -y --no-install-recommends hcxdumptool || echo "hcxdumptool not available"
apt-get install -y --no-install-recommends hcxtools || echo "hcxtools not available"

# ==============================================================================
# Enable I2C and SPI
# ==============================================================================
echo "[momo] Enabling I2C and SPI..."

# Create boot config if not exists
mkdir -p /boot/firmware
touch /boot/firmware/config.txt

# I2C
if [ -f /boot/firmware/config.txt ]; then
    grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt || echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
elif [ -f /boot/config.txt ]; then
    grep -q "^dtparam=i2c_arm=on" /boot/config.txt || echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi

if ! grep -q "^i2c-dev" /etc/modules 2>/dev/null; then
    echo "i2c-dev" >> /etc/modules
fi

# SPI
if [ -f /boot/firmware/config.txt ]; then
    grep -q "^dtparam=spi=on" /boot/firmware/config.txt || echo "dtparam=spi=on" >> /boot/firmware/config.txt
elif [ -f /boot/config.txt ]; then
    grep -q "^dtparam=spi=on" /boot/config.txt || echo "dtparam=spi=on" >> /boot/config.txt
fi

# ==============================================================================
# Clone MoMo
# ==============================================================================
echo "[momo] Cloning MoMo repository..."

rm -rf /opt/momo
git clone --depth 1 https://github.com/M0M0Sec/MoMo.git /opt/momo

# ==============================================================================
# Python Virtual Environment
# ==============================================================================
echo "[momo] Setting up Python environment..."

python3 -m venv /opt/momo/.venv
/opt/momo/.venv/bin/pip install --upgrade pip setuptools wheel

# Install MoMo with all optional dependencies
/opt/momo/.venv/bin/pip install -e "/opt/momo[recommended,wardriving,ble,eviltwin,firstboot]"

# ==============================================================================
# Create MoMo User
# ==============================================================================
echo "[momo] Creating momo user..."

if ! id -u momo &>/dev/null; then
    useradd -r -s /bin/false -d /opt/momo momo
fi

# Add to required groups (create groups if they don't exist)
for grp in gpio i2c spi dialout netdev; do
    getent group $grp >/dev/null || groupadd -r $grp 2>/dev/null || true
done
usermod -aG gpio,i2c,spi,dialout,netdev momo 2>/dev/null || true

# Set ownership
chown -R momo:momo /opt/momo

# ==============================================================================
# Configuration Directories
# ==============================================================================
echo "[momo] Creating config directories..."

install -d -m 0755 -o momo -g momo /etc/momo
install -d -m 0755 -o momo -g momo /var/log/momo
install -d -m 0755 -o momo -g momo /var/lib/momo

# DO NOT copy default config - First Boot Wizard will create it!

# ==============================================================================
# Systemd Services
# ==============================================================================
echo "[momo] Installing systemd services..."

# Main MoMo service
install -m 0644 /opt/momo/deploy/systemd/momo.service /etc/systemd/system/
install -m 0644 /opt/momo/deploy/systemd/momo-web.service /etc/systemd/system/ 2>/dev/null || true
install -m 0644 /opt/momo/deploy/systemd/momo-oled.service /etc/systemd/system/ 2>/dev/null || true

# Management AP service
install -m 0644 /opt/momo/deploy/systemd/momo-ap.service /etc/systemd/system/

# First Boot Wizard service
install -m 0644 /opt/momo/deploy/firstboot/momo-firstboot.service /etc/systemd/system/

# Install AP management script
install -m 0755 /opt/momo/scripts/momo-ap.sh /opt/momo/scripts/ 2>/dev/null || true

# Enable firstboot service (runs on first boot)
systemctl enable momo-firstboot.service

# ==============================================================================
# Network Configuration
# ==============================================================================
echo "[momo] Configuring network..."

# Disable NetworkManager management of wlan1+ (attack interfaces)
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/99-momo.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:wlan1;interface-name:wlan2;interface-name:wlan3
EOF

# hostapd/dnsmasq config directories
install -d -m 0755 /etc/hostapd
install -d -m 0755 /etc/dnsmasq.d

# Disable system hostapd and dnsmasq (MoMo manages its own)
systemctl disable hostapd 2>/dev/null || true
systemctl disable dnsmasq 2>/dev/null || true

# ==============================================================================
# SSH Configuration
# ==============================================================================
echo "[momo] Enabling SSH..."

# For Pi 5 with bookworm, SSH file goes in /boot/firmware
mkdir -p /boot/firmware
touch /boot/firmware/ssh
touch /boot/ssh 2>/dev/null || true

systemctl enable ssh 2>/dev/null || systemctl enable sshd 2>/dev/null || true

# ==============================================================================
# Welcome Message
# ==============================================================================
echo "[momo] Setting up welcome message..."

cat > /etc/motd <<'MOTD'

  🔥 MoMo - Modular Offensive Mobile Operations
  ═══════════════════════════════════════════════

  First Boot:
    Connect to WiFi: MoMo-Setup (password: momosetup)
    Open browser: http://192.168.4.1

  After Setup:
    Dashboard: http://<IP>:8082
    CLI: momo --help

  Documentation: https://github.com/M0M0Sec/MoMo

MOTD

# ==============================================================================
# Cleanup
# ==============================================================================
echo "[momo] Cleaning up..."

apt-get clean
rm -rf /var/lib/apt/lists/*
rm -rf /tmp/*
rm -rf /var/tmp/*

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            ✅ MoMo installation complete!                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"

