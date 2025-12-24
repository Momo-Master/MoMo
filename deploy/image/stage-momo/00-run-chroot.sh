#!/bin/bash -e
# ==============================================================================
# MoMo Stage - Chroot Script (01-run-chroot.sh)
# ==============================================================================
# This runs inside the chroot environment during image build.
# Installs all MoMo dependencies and configures the system.
# ==============================================================================

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            🔥 Installing MoMo...                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ==============================================================================
# System Dependencies
# ==============================================================================
echo "[momo] Installing system dependencies..."

apt-get update

# Core packages (should always be available)
apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    wget \
    hostapd \
    dnsmasq \
    iptables \
    iw \
    wireless-tools \
    rfkill \
    gpsd \
    gpsd-clients \
    i2c-tools \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    avahi-daemon \
    avahi-utils \
    bc

# Optional packages - install if available
echo "[momo] Installing optional packages..."
apt-get install -y --no-install-recommends aircrack-ng || echo "aircrack-ng not available"
apt-get install -y --no-install-recommends hcxdumptool || echo "hcxdumptool not available"
apt-get install -y --no-install-recommends hcxtools || echo "hcxtools not available"

# ==============================================================================
# Enable I2C and SPI
# ==============================================================================
echo "[momo] Enabling I2C and SPI..."

# I2C
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi
if ! grep -q "^i2c-dev" /etc/modules; then
    echo "i2c-dev" >> /etc/modules
fi

# SPI (for some displays)
if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
    echo "dtparam=spi=on" >> /boot/config.txt
fi

# ==============================================================================
# Clone MoMo
# ==============================================================================
echo "[momo] Cloning MoMo repository..."

if [ -d /opt/momo/.git ]; then
    cd /opt/momo && git pull
else
    rm -rf /opt/momo
    git clone --depth 1 https://github.com/M0M0Sec/MoMo.git /opt/momo
fi

# ==============================================================================
# Python Virtual Environment
# ==============================================================================
echo "[momo] Setting up Python environment..."

python3 -m venv /opt/momo/.venv
source /opt/momo/.venv/bin/activate

pip install --upgrade pip setuptools wheel

# Install MoMo with all optional dependencies
pip install -e "/opt/momo[recommended,wardriving,ble,eviltwin,firstboot]"

deactivate

# ==============================================================================
# Create MoMo User
# ==============================================================================
echo "[momo] Creating momo user..."

if ! id -u momo &>/dev/null; then
    useradd -r -s /bin/false -d /opt/momo momo
fi

# Add to required groups
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

# Copy default config
if [ -f /opt/momo/configs/momo.yml ]; then
    install -m 0644 -o momo -g momo /opt/momo/configs/momo.yml /etc/momo/momo.yml
fi

# ==============================================================================
# Systemd Services
# ==============================================================================
echo "[momo] Installing systemd services..."

# Main MoMo service
install -m 0644 /opt/momo/deploy/systemd/momo.service /etc/systemd/system/
install -m 0644 /opt/momo/deploy/systemd/momo-web.service /etc/systemd/system/
install -m 0644 /opt/momo/deploy/systemd/momo-oled.service /etc/systemd/system/

# First Boot Wizard service
install -m 0644 /opt/momo/deploy/firstboot/momo-firstboot.service /etc/systemd/system/

# Enable services
systemctl enable momo-firstboot.service
# Don't enable main services yet - firstboot will do that
# systemctl enable momo.service momo-web.service momo-oled.service

# ==============================================================================
# Network Configuration
# ==============================================================================
echo "[momo] Configuring network..."

# Disable NetworkManager management of wlan1+ (attack interfaces)
cat > /etc/NetworkManager/conf.d/99-momo.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:wlan1;interface-name:wlan2;interface-name:wlan3
EOF

# hostapd config directory
install -d -m 0755 /etc/hostapd

# dnsmasq config directory
install -d -m 0755 /etc/dnsmasq.d

# ==============================================================================
# SSH Configuration
# ==============================================================================
echo "[momo] Enabling SSH..."

touch /boot/ssh
systemctl enable ssh

# ==============================================================================
# Welcome Message
# ==============================================================================
echo "[momo] Setting up welcome message..."

cat > /etc/motd <<'EOF'

  🔥 MoMo - Modular Offensive Mobile Operations
  ═══════════════════════════════════════════════

  First Boot:
    Connect to WiFi: MoMo-Setup (password: momosetup)
    Open browser: http://192.168.4.1

  After Setup:
    Dashboard: http://<IP>:8082
    CLI: momo --help

  Documentation: https://github.com/M0M0Sec/MoMo

EOF

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
