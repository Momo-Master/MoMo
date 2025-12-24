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
    
    # Copy default config if not exists
    if [ ! -f "$ETC/momo.yml" ]; then
        if [ -f "$DEST/configs/momo.yml" ]; then
            cp "$DEST/configs/momo.yml" "$ETC/momo.yml"
            log "Copied default config to $ETC/momo.yml"
        elif [ -f "$DEST/configs/momo-config.example.yml" ]; then
            cp "$DEST/configs/momo-config.example.yml" "$ETC/momo.yml"
            log "Copied example config to $ETC/momo.yml"
        else
            # Create minimal config
            cat > "$ETC/momo.yml" <<'EOFCFG'
# MoMo Configuration
mode: aggressive
interface:
  name: wlan0
  channel_hop: true
  channels: [1, 6, 11]
web:
  enabled: true
  bind_host: 0.0.0.0
  bind_port: 8082
  allow_query_token: true
  allow_local_unauth: true
logging:
  base_dir: /opt/momo/logs
plugins:
  enabled: ["autobackup", "wardriver", "webcfg"]
EOFCFG
            log "Created minimal config at $ETC/momo.yml"
        fi
    fi
    
    # Generate Web UI token (both in env and file)
    if [ "$ENABLE_WEB" = "1" ]; then
        install -d "$DROPIN_DIR"
        
        # Generate token if not exists
        if [ ! -f "$DEST/.momo_ui_token" ]; then
            TOKEN=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
            echo "$TOKEN" > "$DEST/.momo_ui_token"
            chmod 600 "$DEST/.momo_ui_token"
            log "Generated Web UI token"
        else
            TOKEN=$(cat "$DEST/.momo_ui_token")
        fi
        
        # Also set in systemd environment
        printf "[Service]\nEnvironment=MOMO_UI_TOKEN=%s\n" "$TOKEN" > "$DROPIN_DIR/env.conf"
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
        
        # Create firstboot entry script
        cat > /usr/local/bin/momo-firstboot << 'EOFENTRY'
#!/bin/bash
cd /opt/momo
exec /opt/momo/.venv/bin/python -m momo.firstboot.entry "$@"
EOFENTRY
        chmod +x /usr/local/bin/momo-firstboot
        
        # Install hostapd and dnsmasq for AP mode
        log "Installing AP mode dependencies..."
        pkg_install hostapd dnsmasq
        
        # Disable hostapd/dnsmasq system services (we manage them manually)
        systemctl disable hostapd 2>/dev/null || true
        systemctl stop hostapd 2>/dev/null || true
        systemctl disable dnsmasq 2>/dev/null || true
        systemctl stop dnsmasq 2>/dev/null || true
        
        # Enable firstboot service
        systemctl enable momo-firstboot || true
    fi
    
    # Always enable main momo service (firstboot will start it after setup)
    systemctl enable momo || true
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
    
    # Start service
    log "Starting MoMo service..."
    systemctl enable momo >/dev/null 2>&1 || true
    systemctl start momo >/dev/null 2>&1 || true
    
    # Get IP address
    IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
    [ -z "$IP_ADDR" ] && IP_ADDR="<your-pi-ip>"
    
    # Done!
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            ✅ MoMo Installation Complete!                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    log "Installation directory: $DEST"
    log "Configuration: $ETC/momo.yml"
    echo ""
    
    echo "🌐 Web UI Access:"
    echo "   URL:     http://${IP_ADDR}:8082"
    if [ -f "$DEST/.momo_ui_token" ]; then
        echo "   Token:   $(cat "$DEST/.momo_ui_token")"
        echo ""
        echo "   Note: Token auth is DISABLED for local network (192.168.x.x)"
        echo "   For remote access, use: http://${IP_ADDR}:8082?token=<token>"
    fi
    echo ""
    
    echo "🔧 Service Commands:"
    echo "   sudo systemctl status momo    # Check status"
    echo "   sudo systemctl restart momo   # Restart"
    echo "   sudo journalctl -u momo -f    # View logs"
    echo ""
    
    if [ "$ENABLE_FIRSTBOOT" = "1" ]; then
        echo "📱 First Boot Wizard (optional):"
        echo "   sudo systemctl start momo-firstboot"
        echo "   Connect to WiFi: MoMo-Setup (password: momosetup)"
        echo "   Open browser: http://192.168.4.1"
        echo ""
    fi
    
    # Check service status
    if systemctl is-active --quiet momo 2>/dev/null; then
        log "✅ MoMo is running!"
    else
        warn "MoMo service not started. Run: sudo systemctl start momo"
    fi
    echo ""
}

main "$@"
