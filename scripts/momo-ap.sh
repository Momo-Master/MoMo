#!/bin/bash
# ==============================================================================
# MoMo Management AP Script
# ==============================================================================
# Starts/stops the management WiFi Access Point based on network.yml config.
#
# Usage:
#   ./momo-ap.sh start
#   ./momo-ap.sh stop
#   ./momo-ap.sh status
# ==============================================================================

set -e

# Config paths
NETWORK_CONFIG="/etc/momo/network.yml"
FALLBACK_CONFIG="/opt/momo/configs/network.yml"
HOSTAPD_CONF="/tmp/momo-management-ap.conf"
DNSMASQ_CONF="/tmp/momo-management-dnsmasq.conf"
PIDFILE_HOSTAPD="/var/run/momo-hostapd.pid"
PIDFILE_DNSMASQ="/var/run/momo-dnsmasq.pid"

# Default values
INTERFACE="wlan0"
SSID="MoMo-Management"
PASSWORD=""
CHANNEL=6
IP_ADDRESS="192.168.4.1"
DHCP_START="192.168.4.10"
DHCP_END="192.168.4.50"

# Parse YAML config (simple parsing)
parse_config() {
    local config_file=""
    
    if [ -f "$NETWORK_CONFIG" ]; then
        config_file="$NETWORK_CONFIG"
    elif [ -f "$FALLBACK_CONFIG" ]; then
        config_file="$FALLBACK_CONFIG"
    else
        echo "[momo-ap] No network config found, using defaults"
        return
    fi
    
    echo "[momo-ap] Reading config from $config_file"
    
    # Check mode - only start AP if mode is "ap"
    MODE=$(grep -E "^mode:" "$config_file" 2>/dev/null | awk '{print $2}' | tr -d '"' || echo "ap")
    if [ "$MODE" != "ap" ]; then
        echo "[momo-ap] Network mode is '$MODE', not 'ap'. Skipping AP setup."
        exit 0
    fi
    
    # Parse AP settings
    SSID=$(grep -A5 "^ap:" "$config_file" | grep "ssid:" | awk '{print $2}' | tr -d '"' || echo "$SSID")
    PASSWORD=$(grep -A5 "^ap:" "$config_file" | grep "password:" | awk '{print $2}' | tr -d '"' || echo "$PASSWORD")
    CHANNEL=$(grep -A5 "^ap:" "$config_file" | grep "channel:" | awk '{print $2}' | tr -d '"' || echo "$CHANNEL")
    IP_ADDRESS=$(grep -A5 "^ap:" "$config_file" | grep "ip_address:" | awk '{print $2}' | tr -d '"' || echo "$IP_ADDRESS")
    DHCP_START=$(grep -A5 "^ap:" "$config_file" | grep "dhcp_start:" | awk '{print $2}' | tr -d '"' || echo "$DHCP_START")
    DHCP_END=$(grep -A5 "^ap:" "$config_file" | grep "dhcp_end:" | awk '{print $2}' | tr -d '"' || echo "$DHCP_END")
    
    # Parse management interface
    INTERFACE=$(grep "management_interface:" "$config_file" | awk '{print $2}' | tr -d '"' || echo "$INTERFACE")
}

# Generate hostapd config
generate_hostapd_config() {
    cat > "$HOSTAPD_CONF" << EOF
interface=$INTERFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

    # If no password, create open network
    if [ -z "$PASSWORD" ] || [ ${#PASSWORD} -lt 8 ]; then
        cat > "$HOSTAPD_CONF" << EOF
interface=$INTERFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
EOF
        echo "[momo-ap] Warning: No password set, creating open network"
    fi
}

# Generate dnsmasq config
generate_dnsmasq_config() {
    cat > "$DNSMASQ_CONF" << EOF
interface=$INTERFACE
bind-interfaces
dhcp-range=$DHCP_START,$DHCP_END,255.255.255.0,24h
dhcp-option=3,$IP_ADDRESS
dhcp-option=6,$IP_ADDRESS
EOF
}

# Configure interface
configure_interface() {
    echo "[momo-ap] Configuring interface $INTERFACE..."
    
    # Stop NetworkManager management
    nmcli dev set "$INTERFACE" managed no 2>/dev/null || true
    
    # Kill any existing wpa_supplicant
    pkill -f "wpa_supplicant.*$INTERFACE" 2>/dev/null || true
    sleep 0.5
    
    # Bring down interface
    ip link set "$INTERFACE" down 2>/dev/null || true
    
    # Flush IP
    ip addr flush dev "$INTERFACE" 2>/dev/null || true
    
    # Set IP address
    ip addr add "$IP_ADDRESS/24" dev "$INTERFACE" 2>/dev/null || true
    
    # Bring up interface
    ip link set "$INTERFACE" up
    
    echo "[momo-ap] Interface $INTERFACE configured with IP $IP_ADDRESS"
}

# Reset interface to default
reset_interface() {
    echo "[momo-ap] Resetting interface $INTERFACE..."
    
    # Flush IP
    ip addr flush dev "$INTERFACE" 2>/dev/null || true
    
    # Re-enable NetworkManager
    nmcli dev set "$INTERFACE" managed yes 2>/dev/null || true
    
    echo "[momo-ap] Interface $INTERFACE returned to NetworkManager"
}

# Start AP
start_ap() {
    echo "[momo-ap] Starting Management AP..."
    
    # Parse config
    parse_config
    
    # If parse_config exited (client mode), don't continue
    if [ "$MODE" = "client" ]; then
        exit 0
    fi
    
    # Stop any existing instances
    stop_ap 2>/dev/null || true
    
    # Configure interface
    configure_interface
    
    # Generate configs
    generate_hostapd_config
    generate_dnsmasq_config
    
    # Start hostapd
    echo "[momo-ap] Starting hostapd..."
    hostapd -B -P "$PIDFILE_HOSTAPD" "$HOSTAPD_CONF"
    sleep 1
    
    # Start dnsmasq
    echo "[momo-ap] Starting dnsmasq..."
    dnsmasq -C "$DNSMASQ_CONF" --pid-file="$PIDFILE_DNSMASQ"
    
    echo "[momo-ap] ✅ Management AP started: SSID=$SSID, IP=$IP_ADDRESS"
}

# Stop AP
stop_ap() {
    echo "[momo-ap] Stopping Management AP..."
    
    # Kill hostapd
    if [ -f "$PIDFILE_HOSTAPD" ]; then
        kill $(cat "$PIDFILE_HOSTAPD") 2>/dev/null || true
        rm -f "$PIDFILE_HOSTAPD"
    fi
    pkill -f "hostapd.*momo-management" 2>/dev/null || true
    
    # Kill dnsmasq
    if [ -f "$PIDFILE_DNSMASQ" ]; then
        kill $(cat "$PIDFILE_DNSMASQ") 2>/dev/null || true
        rm -f "$PIDFILE_DNSMASQ"
    fi
    
    # Reset interface
    reset_interface
    
    # Cleanup
    rm -f "$HOSTAPD_CONF" "$DNSMASQ_CONF"
    
    echo "[momo-ap] Management AP stopped"
}

# Status
status_ap() {
    echo "[momo-ap] Status:"
    
    if [ -f "$PIDFILE_HOSTAPD" ] && kill -0 $(cat "$PIDFILE_HOSTAPD") 2>/dev/null; then
        echo "  hostapd: running (PID $(cat $PIDFILE_HOSTAPD))"
    else
        echo "  hostapd: stopped"
    fi
    
    if [ -f "$PIDFILE_DNSMASQ" ] && kill -0 $(cat "$PIDFILE_DNSMASQ") 2>/dev/null; then
        echo "  dnsmasq: running (PID $(cat $PIDFILE_DNSMASQ))"
    else
        echo "  dnsmasq: stopped"
    fi
    
    echo "  Interface: $INTERFACE"
    ip addr show "$INTERFACE" 2>/dev/null | grep inet || echo "  No IP configured"
}

# Main
case "$1" in
    start)
        start_ap
        ;;
    stop)
        stop_ap
        ;;
    restart)
        stop_ap
        sleep 1
        start_ap
        ;;
    status)
        status_ap
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

