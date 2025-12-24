#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# MoMo Quickstart Installer
# ==============================================================================
# One-shot installer for MoMo on Raspberry Pi 5 / Debian Bookworm
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/M0M0Sec/MoMo/main/deploy/momo-quickstart.sh | sudo bash
#
# Options (environment variables):
#   ENABLE_WEB=1          Enable web UI (default: 1)
#   ENABLE_ACTIVE_WIFI=1  Install aircrack-ng, mdk4 (default: 0)
#   ENABLE_CRACKING=1     Install hashcat, john (default: 0)
#   ENABLE_FIRSTBOOT=1    Enable first boot wizard (default: 1)
# ==============================================================================

# Configuration
REPO_URL=${REPO_URL:-https://github.com/M0M0Sec/MoMo.git}
DEST=/opt/momo
ETC=/etc/momo
UNIT=/etc/systemd/system/momo.service
DROPIN_DIR=/etc/systemd/system/momo.service.d

# Feature flags
ENABLE_WEB=${ENABLE_WEB:-1}
ENABLE_ACTIVE_WIFI=${ENABLE_ACTIVE_WIFI:-0}
ENABLE_CRACKING=${ENABLE_CRACKING:-0}
ENABLE_FIRSTBOOT=${ENABLE_FIRSTBOOT:-1}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[momo]${NC} $*"; }
warn() { echo -e "${YELLOW}[momo]${NC} WARNING: $*"; }
error() { echo -e "${RED}[momo]${NC} ERROR: $*" >&2; }

require_root() {
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        error "This script must be run as root. Use: sudo bash"
        exit 1
    fi
}

pkg_install() {
    DEBIAN_FRONTEND=noninteractive apt-get update -y >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" 2>/dev/null || {
        warn "Some packages may not be available: $*"
    }
}

main() {
    require_root
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            🔥 MoMo Quickstart Installer                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Base dependencies
    log "Installing base dependencies..."
    pkg_install git python3-venv python3-pip python3-dev build-essential \
                curl ca-certificates ufw
    
    # Capture tools
    log "Installing capture tools..."
    pkg_install hostapd dnsmasq iptables iw wireless-tools rfkill \
                gpsd gpsd-clients i2c-tools avahi-daemon
    
    # hcxdumptool and hcxtools (may have different names)
    pkg_install hcxdumptool || warn "hcxdumptool not available"
    pkg_install hcxtools || pkg_install hcxpcapngtool || warn "hcxtools not available"
    
    # Optional: Active WiFi tools
    if [ "$ENABLE_ACTIVE_WIFI" = "1" ]; then
        log "Installing active WiFi tools..."
        pkg_install aircrack-ng mdk4 || true
    fi
    
    # Optional: Cracking tools
    if [ "$ENABLE_CRACKING" = "1" ]; then
        log "Installing cracking tools..."
        pkg_install hashcat john || true
    fi
    
    # Clone MoMo
    log "Cloning MoMo to ${DEST}..."
    if [ -d "$DEST/.git" ]; then
        log "Updating existing installation..."
        git -C "$DEST" fetch --depth 1 origin || true
        git -C "$DEST" reset --hard origin/main || true
    else
        rm -rf "$DEST"
        git clone --depth 1 "$REPO_URL" "$DEST"
    fi
    
    # Create virtual environment
    log "Creating Python virtual environment..."
    python3 -m venv "$DEST/.venv"
    source "$DEST/.venv/bin/activate"
    
    # Install MoMo
    log "Installing MoMo..."
    pip install --upgrade pip setuptools wheel >/dev/null
    pip install -e "$DEST[recommended,wardriving,ble,eviltwin]" 2>/dev/null || \
    pip install -e "$DEST" || {
        error "Failed to install MoMo"
        exit 1
    }
    
    # Create config directory
    log "Setting up configuration..."
    install -d -m 0755 "$ETC"
    if [ ! -f "$ETC/momo.yml" ] && [ -f "$DEST/configs/momo.yml" ]; then
        cp "$DEST/configs/momo.yml" "$ETC/momo.yml"
    fi
    
    # Generate Web UI token
    if [ "$ENABLE_WEB" = "1" ]; then
        install -d "$DROPIN_DIR"
        if ! grep -q '^Environment=MOMO_UI_TOKEN=' "$DROPIN_DIR/env.conf" 2>/dev/null; then
            TOKEN=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
            printf "[Service]\nEnvironment=MOMO_UI_TOKEN=%s\n" "$TOKEN" > "$DROPIN_DIR/env.conf"
            log "Generated Web UI token"
        fi
    fi
    
    # Install systemd service
    log "Installing systemd service..."
    cat > "$UNIT" <<EOF
[Unit]
Description=MoMo Wireless Security Platform
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DEST
ExecStart=$DEST/.venv/bin/momo run -c /etc/momo/momo.yml
EnvironmentFile=-/etc/default/momo
EnvironmentFile=-$DROPIN_DIR/env.conf
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
    
    # Install firstboot service if enabled
    if [ "$ENABLE_FIRSTBOOT" = "1" ] && [ -f "$DEST/deploy/firstboot/momo-firstboot.service" ]; then
        log "Installing first boot wizard..."
        cp "$DEST/deploy/firstboot/momo-firstboot.service" /etc/systemd/system/
        # Don't enable main momo service yet - firstboot will do it
    else
        systemctl enable momo || true
    fi
    
    systemctl daemon-reload
    
    # Firewall
    if command -v ufw >/dev/null 2>&1; then
        log "Configuring firewall..."
        ufw allow 22/tcp >/dev/null 2>&1 || true   # SSH
        ufw allow 8082/tcp >/dev/null 2>&1 || true # Web UI
        ufw allow 9091/tcp >/dev/null 2>&1 || true # Metrics
    fi
    
    # Enable I2C for OLED
    if [ -f /boot/config.txt ] || [ -f /boot/firmware/config.txt ]; then
        log "Enabling I2C for OLED display..."
        CONFIG_FILE="/boot/firmware/config.txt"
        [ -f "/boot/config.txt" ] && CONFIG_FILE="/boot/config.txt"
        grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE" || echo "dtparam=i2c_arm=on" >> "$CONFIG_FILE"
    fi
    
    # Done!
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            ✅ MoMo Installation Complete!                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    log "Installation directory: $DEST"
    log "Configuration: $ETC/momo.yml"
    echo ""
    
    if [ "$ENABLE_FIRSTBOOT" = "1" ]; then
        echo "📱 First Boot Wizard:"
        echo "   1. Reboot the device"
        echo "   2. Connect to WiFi: MoMo-Setup (password: momosetup)"
        echo "   3. Open browser: http://192.168.4.1"
        echo ""
        echo "Or start manually:"
        echo "   sudo systemctl start momo"
    else
        echo "🚀 Start MoMo:"
        echo "   sudo systemctl start momo"
        echo ""
        echo "📊 Access:"
        echo "   Web UI:  http://$(hostname -I | awk '{print $1}'):8082"
        echo "   Health:  http://127.0.0.1:8082/healthz"
    fi
    echo ""
}

main "$@"
