# 🚀 First Boot Wizard

Complete guide to the MoMo First Boot Wizard - your gateway to a seamless setup experience.

---

## 📖 Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Web Wizard](#web-wizard)
- [Headless Setup](#headless-setup)
- [Nexus Integration](#nexus-integration)
- [OLED Display](#oled-display)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

---

## Overview

The First Boot Wizard provides a user-friendly setup experience for new MoMo devices. It supports three modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Web Wizard** | Browser-based guided setup | Most users |
| **Headless** | Config file on SD card | Fleet deployment |
| **CLI** | Terminal-based wizard | SSH-only access |

### Features

- 🌐 **Web-based UI** - Modern React interface
- 📱 **Mobile-friendly** - Works on phones and tablets
- 🔐 **Secure** - Password strength validation, HTTPS ready
- 🔍 **Auto-discovery** - Find Nexus via mDNS
- 📺 **OLED QR Code** - Scan to connect WiFi
- ⚡ **Fast** - Complete setup in under 2 minutes

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    FIRST BOOT DETECTION                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  /etc/momo/.setup_complete exists?                          │
│         │                                                    │
│         ├── YES ──► Normal boot (skip wizard)               │
│         │                                                    │
│         └── NO                                               │
│              │                                               │
│              ▼                                               │
│  /boot/momo-config.yml exists?                              │
│         │                                                    │
│         ├── YES ──► Apply headless config ──► Normal boot   │
│         │                                                    │
│         └── NO                                               │
│              │                                               │
│              ▼                                               │
│  Start WiFi AP ──► Launch Web Wizard ──► Wait for user     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Web Wizard

### Step 1: Connect to MoMo

1. Power on your MoMo device
2. Wait for OLED to show QR code (or look for `MoMo-Setup` WiFi)
3. Connect to `MoMo-Setup` network
   - Password: `momosetup`
4. Browser opens automatically (or go to `http://192.168.4.1`)

### Step 2: Language Selection

Choose your preferred language:
- 🇬🇧 English
- 🇹🇷 Türkçe

### Step 3: Admin Password

Set a secure admin password for:
- Web dashboard access
- API authentication
- SSH login (optional)

**Requirements:**
- Minimum 8 characters
- Mix of letters, numbers, symbols recommended

### Step 4: Network Configuration

Choose how MoMo connects to your network:

| Mode | Description |
|------|-------------|
| **Access Point** | MoMo creates its own WiFi network |
| **Client** | MoMo joins your existing WiFi |

**AP Mode Settings:**
- SSID: Network name (e.g., `MoMo-Management`)
- Password: WiFi password
- Channel: 1-11 (auto-select recommended)

**Client Mode Settings:**
- Select from scanned networks
- Enter WiFi password

### Step 5: Operation Profile

Select your operational profile:

| Profile | Description | Best For |
|---------|-------------|----------|
| 🔇 **Passive** | Scan only, no active attacks | Reconnaissance |
| ⚖️ **Balanced** | Moderate scanning + opportunistic attacks | Daily use |
| 🔥 **Aggressive** | Maximum attack rate | Authorized pentests |

### Step 6: Nexus Connection (Optional)

Connect to a MoMo-Nexus hub for:
- Centralized monitoring
- Cloud GPU cracking
- Remote control
- Data synchronization

**Options:**
- **Auto-discover** - Find Nexus on local network via mDNS
- **Manual entry** - Enter Nexus URL directly
- **Skip** - Configure later

### Step 7: Summary & Complete

Review your settings and click **Complete Setup**.

MoMo will:
1. Generate configuration files
2. Restart network services
3. Mark setup as complete
4. Redirect to dashboard

---

## Headless Setup

For automated deployments, create `/boot/momo-config.yml`:

```yaml
# ══════════════════════════════════════════════════════════════
# MoMo Headless Configuration
# ══════════════════════════════════════════════════════════════

setup:
  skip_wizard: true
  language: en

security:
  admin_password: "YourSecurePassword123!"

network:
  mode: ap
  ap:
    ssid: MoMo-Field-01
    password: SecurePass2024!
    channel: 6
    hidden: false

profile: balanced

interface:
  name: auto                    # First USB WiFi adapter

whitelist:
  ssids:
    - "Home_WiFi"
    - "Office_Network"

nexus:
  enabled: true
  url: "http://192.168.1.100:8080"
  registration_token: "XXXX-XXXX"
  device_name: "MoMo-Field-01"
  sync:
    handshakes: true
    credentials: true
    wardriving: true
```

### Deployment Steps

1. Flash MoMo image to SD card
2. Mount boot partition
3. Copy `momo-config.yml` to `/boot/`
4. Insert SD card and power on
5. MoMo auto-configures and starts

---

## Nexus Integration

### mDNS Discovery

MoMo discovers Nexus devices advertising via mDNS:

```
Service Type: _nexus._tcp.local.
```

**Discovered Information:**
- IP address and port
- Nexus name
- Version
- Connected device count

### Registration Flow

```
MoMo                              Nexus
  │                                 │
  │  POST /api/devices/register     │
  │  { device_id, type, name }      │
  │ ───────────────────────────────►│
  │                                 │
  │  { success, api_key, config }   │
  │ ◄─────────────────────────────  │
  │                                 │
  │  Store API key locally          │
  │  Start sync with Nexus          │
  │                                 │
```

### Sync Configuration

```yaml
nexus:
  sync:
    enabled: true
    interval: 30              # seconds
    handshakes: true          # Captured handshakes
    credentials: true         # Harvested creds
    wardriving: true          # GPS data
    stats: true               # Device stats
  
  cloud_crack:
    enabled: true             # Use Nexus GPU
    auto_submit: true         # Auto-submit hashes
    notify_on_crack: true     # Get notifications
```

---

## OLED Display

On devices with OLED screens, the wizard shows:

### Setup Screen
```
┌──────────────────────┐
│ 🔥 MoMo Setup        │
│ WiFi: MoMo-Setup     │
│ Pass: momosetup      │
│ 192.168.4.1          │
└──────────────────────┘
```

### QR Code Screen
```
┌──────────────────────┐
│ Scan QR   ┌───────┐  │
│ to connect│ ▄▄▄▄▄ │  │
│ MoMo-Se.. │ █ ▀ █ │  │
│           │ ▀▀▀▀▀ │  │
└───────────└───────┘──┘
```

### Complete Screen
```
┌──────────────────────┐
│ ✓ Setup Complete!    │
│ ──────────────────── │
│ WiFi: MoMo-Mgmt      │
│ Dashboard:           │
│ http://192.168.4.1   │
└──────────────────────┘
```

---

## Troubleshooting

### Can't see MoMo-Setup WiFi

1. Wait 60 seconds after power on
2. Check if internal WiFi is working (`dmesg | grep wlan`)
3. Try restarting: `sudo systemctl restart momo-firstboot`

### Browser doesn't open automatically

1. Go to `http://192.168.4.1` manually
2. If DNS fails, check DHCP: `ip addr`
3. Clear browser cache

### Wizard stuck on loading

1. Check backend: `sudo journalctl -u momo-firstboot -f`
2. Restart service: `sudo systemctl restart momo-firstboot`

### Nexus not discovered

1. Ensure Nexus is on same network
2. Check Nexus is advertising mDNS
3. Try manual URL entry
4. Check firewall rules

### Reset wizard for testing

```bash
sudo rm /etc/momo/.setup_complete
sudo systemctl restart momo-firstboot
```

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Wizard status |
| GET | `/api/step/{n}` | Get step data |
| POST | `/api/step/language` | Set language |
| POST | `/api/step/password` | Set password |
| POST | `/api/step/network` | Configure network |
| POST | `/api/step/profile` | Set profile |
| POST | `/api/step/nexus` | Configure Nexus |
| GET | `/api/summary` | Get config summary |
| POST | `/api/complete` | Complete setup |
| GET | `/api/wifi/scan` | Scan WiFi networks |
| GET | `/api/nexus/discover` | Discover Nexus devices |
| POST | `/api/nexus/test` | Test Nexus connection |
| POST | `/api/nexus/register` | Register with Nexus |

### Status Response

```json
{
  "wizard_active": true,
  "current_step": "language",
  "steps_completed": [],
  "network_ready": true,
  "captive_portal": true
}
```

### Complete Request

```json
{
  "confirm": true
}
```

---

## CLI Usage

```bash
# Check status
momo-firstboot --status

# Force web wizard
momo-firstboot --wizard

# CLI-only wizard
momo-firstboot --cli

# Reset for testing
momo-firstboot --reset
```

---

<p align="center">
  <strong>🔥 MoMo Ecosystem</strong><br>
  <sub>First Boot Wizard Documentation</sub>
</p>

