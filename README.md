<p align="center">
  <img src="docs/assets/momo-logo.png" alt="MoMo Logo" width="200">
</p>

<h1 align="center">🔥 MoMo</h1>
<h3 align="center">Modular Offensive Mobile Operations</h3>

<p align="center">
  <strong>Next-Generation Wireless Security Audit Platform</strong><br>
  <sub>Built for Red Teams, Pentesters & Security Researchers</sub>
</p>

<p align="center">
  <a href="https://github.com/Momo-Master/MoMo/releases"><img src="https://img.shields.io/badge/Version-1.7.0-blue?style=for-the-badge" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%205-c51a4a?style=for-the-badge&logo=raspberry-pi" alt="Platform"></a>
  <a href="#"><img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Tests-484%20Passing-success?style=flat-square" alt="Tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/Coverage-87%25-brightgreen?style=flat-square" alt="Coverage"></a>
  <a href="#"><img src="https://img.shields.io/badge/Build-Passing-success?style=flat-square" alt="Build"></a>
  <a href="#"><img src="https://img.shields.io/badge/Code%20Style-Black-000000?style=flat-square" alt="Code Style"></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-hardware">Hardware</a> •
  <a href="#-ecosystem">Ecosystem</a> •
  <a href="#-documentation">Docs</a>
</p>

---

## 📖 Table of Contents

- [What is MoMo?](#-what-is-momo)
- [Key Features](#-key-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Architecture](#-architecture)
- [Supported Hardware](#-supported-hardware)
- [Web Interface & API](#-web-interface--api)
- [Plugin Development](#-plugin-development)
- [Configuration](#-configuration)
- [CLI Reference](#-cli-reference)
- [MoMo Ecosystem](#-momo-ecosystem)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 What is MoMo?

**MoMo** is a comprehensive wireless security audit platform designed for the **Raspberry Pi 5**. It combines the best features of industry-standard tools like Pwnagotchi, ESP32 Marauder, and WiFi Pineapple into one powerful, extensible, and professional-grade platform.

### Why MoMo?

| Challenge | MoMo Solution |
|-----------|---------------|
| 🔌 Multiple disconnected tools | ✅ Unified platform with modular architecture |
| 📱 Limited headless operation | ✅ Management network + OLED display + Web UI |
| 🔄 Manual data synchronization | ✅ Real-time sync with Nexus central hub |
| 💻 Requires laptop in field | ✅ Fully autonomous operation with Auto-Pwn |
| 🔐 WPA3 bypasses existing tools | ✅ Native WPA3/SAE detection and downgrade |
| 🎭 Limited social engineering | ✅ Evil Twin, Karma/MANA, Evilginx AiTM |

### Feature Highlights

<table>
<tr>
<td width="33%" valign="top">

### 📡 Wireless Attacks
- Multi-Radio Management
- WPA2/WPA3 Attacks  
- PMKID Capture
- Evil Twin (6 templates)
- Karma/MANA
- Evilginx MFA Bypass

</td>
<td width="33%" valign="top">

### 🔑 Credential Harvesting
- LLMNR/NBT-NS Poisoning
- NTLM Hash Capture
- HTTP Auth Sniffing
- Kerberoast
- AS-REP Roasting
- LDAP Enumeration

</td>
<td width="33%" valign="top">

### 🤖 Automation
- Auto-Pwn Mode
- GPS Wardriving
- Cloud Cracking
- Session Persistence
- Real-time Sync
- Event-driven Alerts

</td>
</tr>
</table>

---

## ✨ Key Features

### 🔥 Wireless Security Testing

<details>
<summary><b>WiFi Attacks</b> - Click to expand</summary>

| Feature | Description | Status |
|---------|-------------|:------:|
| **Wardriving** | GPS-correlated AP scanning with SQLite persistence | ✅ |
| **Multi-Radio** | Manage multiple WiFi adapters simultaneously | ✅ |
| **PMKID Capture** | Clientless WPA2 attack via hcxdumptool | ✅ |
| **Deauth Attacks** | Targeted client disconnection | ✅ |
| **Handshake Capture** | EAPOL 4-way handshake collection | ✅ |
| **WPA3/SAE** | Detection, downgrade attacks, PMF handling | ✅ |
| **Evil Twin** | Rogue AP with captive portal (6 templates) | ✅ |
| **Karma/MANA** | Auto-respond to probes, EAP credential capture | ✅ |
| **Evilginx AiTM** | MFA bypass via session cookie capture | ☁️ VPS |

</details>

<details>
<summary><b>Bluetooth Attacks</b> - Click to expand</summary>

| Feature | Description | Status |
|---------|-------------|:------:|
| **BLE Scanner** | Device & beacon detection with RSSI tracking | ✅ |
| **GATT Explorer** | Service/characteristic discovery & read/write | ✅ |
| **Beacon Spoofing** | iBeacon & Eddystone frame injection | ✅ |
| **HID Injection** | Bluetooth keyboard emulation | ✅ |

</details>

<details>
<summary><b>SDR Integration</b> - Click to expand</summary>

| Feature | Description | Status |
|---------|-------------|:------:|
| **RTL-SDR Support** | V3 & V4 with HF direct sampling, bias tee | ✅ |
| **HackRF Support** | TX/RX capable for replay attacks | ✅ |
| **Spectrum Analyzer** | Frequency scanning & peak detection | ✅ |
| **Signal Decoder** | 433/868 MHz IoT signal capture | ✅ |

</details>

### 🔑 Credential Harvesting (NEW in v1.6.0)

<details>
<summary><b>MoMo-Creds Module</b> - Click to expand</summary>

| Feature | Description | Status |
|---------|-------------|:------:|
| **Responder** | LLMNR/NBT-NS/mDNS poisoning | ✅ |
| **NTLM Capture** | NTLMv1/v2 hash capture via SMB/HTTP | ✅ |
| **NTLM Relay** | Hash relay to target systems | ✅ |
| **HTTP Sniffer** | Basic/Digest/Form/Bearer credential capture | ✅ |
| **Kerberoast** | Service ticket extraction for offline cracking | ✅ |
| **AS-REP Roast** | Target accounts without pre-authentication | ✅ |
| **LDAP Enum** | AD user/group/computer enumeration | ✅ |
| **Auto Export** | Hashcat/John format export | ✅ |

**Export Formats:**
- Hashcat: 5500 (NTLMv1), 5600 (NTLMv2), 13100 (Kerberos RC4), 18200 (AS-REP)
- John the Ripper: NETLM, NETNTLMv2, krb5tgs

</details>

### 🤖 Autonomous Operation

<details>
<summary><b>Auto-Pwn Mode</b> - Click to expand</summary>

| Feature | Description |
|---------|-------------|
| **Target Discovery** | Automatic network scanning and prioritization |
| **Attack Chaining** | PMKID → Deauth → Evil Twin fallback sequence |
| **Session Persistence** | Resume after reboot, save progress |
| **Safety Features** | Battery monitoring, max duration limits |
| **Cloud Integration** | Auto-sync captures to Nexus for cracking |

**Modes:**
- `passive` - Scan only, no attacks
- `balanced` - Smart targeting, avoid detection
- `aggressive` - Maximum speed, all techniques

</details>

### 🖥️ Headless Operation

| Feature | Description |
|---------|-------------|
| **Management Network** | Dedicated wlan0 for tablet/phone control |
| **OLED Display** | 128x64 interactive menu with GPIO buttons |
| **Web Dashboard** | Real-time dark-theme UI with SSE updates |
| **Auto-Whitelist** | Management network protected from attacks |

### 🚀 First Boot Wizard

| Feature | Description |
|---------|-------------|
| **Web-based Setup** | Modern React UI, mobile-friendly |
| **Auto WiFi AP** | Connect to `MoMo-Setup` network |
| **QR Code Display** | Scan OLED QR to connect |
| **Nexus Discovery** | Auto-find Nexus via mDNS |
| **Headless Mode** | `/boot/momo-config.yml` for fleet deploy |

---

## 🚀 Quick Start

### First Boot (New Device)

1. Flash MoMo image to SD card
2. Power on Raspberry Pi
3. Connect to `MoMo-Setup` WiFi (password: `momosetup`)
4. Browser opens wizard automatically
5. Complete 6-step setup in ~2 minutes

> **Headless?** Copy `configs/momo-config.example.yml` to `/boot/momo-config.yml`

### One-Line Install (Raspberry Pi 5)

```bash
curl -fsSL https://raw.githubusercontent.com/Momo-Master/MoMo/main/deploy/momo-quickstart.sh | sudo bash
```

### Verify Installation

```bash
momo version        # Show version info
momo doctor         # Run system diagnostics
momo run --dry-run  # Test without hardware
```

### Access Dashboard

```bash
momo web-url --show-token
# Output: http://192.168.4.1:8082?token=xxxxx
```

---

## 📦 Installation

### Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Hardware** | Raspberry Pi 4 | Raspberry Pi 5 |
| **OS** | Raspberry Pi OS Lite 64-bit | Raspberry Pi OS Lite 64-bit |
| **Python** | 3.11 | 3.12+ |
| **Storage** | 16GB SD | 64GB+ SD |
| **WiFi Adapter** | 1x Monitor Mode | 2x (Attack + Management) |

### Method 1: Automated Install

```bash
# Download and run installer
curl -fsSL https://raw.githubusercontent.com/Momo-Master/MoMo/main/deploy/install.sh | sudo bash

# Configure
sudo nano /etc/momo/momo.yml

# Enable service
sudo systemctl enable --now momo
```

### Method 2: Manual Install

```bash
# Clone repository
git clone https://github.com/Momo-Master/MoMo.git
cd MoMo

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[full]"

# Install system dependencies
sudo apt install -y hcxdumptool hcxtools aircrack-ng gpsd gpsd-clients

# Run
momo run -c configs/momo.yml
```

### Method 3: Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v --cov=momo

# Run linting
ruff check momo/
mypy momo/
```

---

## 🏗️ Architecture

### Clean Architecture Design

MoMo follows **Clean Architecture** principles with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Web UI    │  │  REST API   │  │    CLI      │              │
│  │  (Flask)    │  │  (FastAPI)  │  │   (Click)   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
├─────────┴────────────────┴────────────────┴─────────────────────┤
│                        APPLICATION                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Plugin Manager                        │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │
│  │  │Wardriver│ │Evil Twin│ │  Karma  │ │  Creds  │ ...   │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                          DOMAIN                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ AccessPoint │  │ GPSPosition │  │  Handshake  │  ...         │
│  │   (Model)   │  │   (Model)   │  │   (Model)   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                      INFRASTRUCTURE                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │  WiFi  │ │  BLE   │ │  GPS   │ │  SDR   │ │ Creds  │  ...   │
│  │Scanner │ │Scanner │ │ Client │ │Manager │ │Manager │        │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
momo/
├── core/                          # Core utilities
│   ├── events.py                  # Pub/Sub event bus
│   ├── plugin.py                  # Plugin system
│   ├── capability.py              # Feature gates
│   └── security.py                # Input sanitization
│
├── domain/                        # Business models
│   └── models.py                  # Pydantic models
│
├── infrastructure/                # Hardware abstraction
│   ├── wifi/                      # WiFi scanner, radio manager
│   ├── ble/                       # BLE scanner, GATT, HID
│   ├── gps/                       # GPS client, distance tracking
│   ├── sdr/                       # RTL-SDR, HackRF, spectrum
│   ├── capture/                   # Handshake capture
│   ├── eviltwin/                  # Rogue AP, captive portal
│   ├── karma/                     # Karma/MANA attacks
│   ├── wpa3/                      # WPA3 detection & attacks
│   ├── creds/                     # Credential harvesting (NEW)
│   │   ├── responder.py           # LLMNR/NBT-NS poisoning
│   │   ├── ntlm.py                # NTLM capture & relay
│   │   ├── http_sniffer.py        # HTTP auth sniffing
│   │   ├── kerberos.py            # Kerberoast, AS-REP
│   │   ├── ldap_enum.py           # AD enumeration
│   │   └── manager.py             # Central orchestrator
│   ├── autopwn/                   # Autonomous attack engine
│   ├── display/                   # OLED menu system
│   ├── cracking/                  # John + Cloud proxy
│   ├── hardware/                  # Device auto-detection
│   ├── management/                # Headless network
│   ├── nexus/                     # Nexus sync client
│   └── database/                  # Async SQLite
│
├── apps/
│   ├── momo_core/                 # Main service loop
│   ├── momo_plugins/              # Plugin collection
│   │   ├── wardriver.py
│   │   ├── evil_twin.py
│   │   ├── karma_mana.py
│   │   ├── creds_harvester.py     # NEW
│   │   └── ...
│   └── momo_web/                  # Flask API + Web UI
│
├── plugins/                       # Modern plugin architecture
├── configs/                       # Configuration files
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (484 tests)
│   ├── integration/               # Integration tests
│   └── e2e/                       # End-to-end tests
└── docs/                          # Documentation
```

### Event-Driven Architecture

```
┌─────────────┐    publish     ┌─────────────┐    subscribe    ┌─────────────┐
│   Plugin A  │ ───────────▶   │  Event Bus  │  ◀───────────── │   Plugin B  │
│  (Scanner)  │                │             │                 │  (Display)  │
└─────────────┘                └──────┬──────┘                 └─────────────┘
                                      │
                               ┌──────▼──────┐
                               │   Plugin C  │
                               │   (Logger)  │
                               └─────────────┘
```

---

## 📡 Supported Hardware

### WiFi Adapters

| Adapter | Chipset | Monitor | Injection | 5GHz | WiFi 6/6E | Recommended |
|---------|---------|:-------:|:---------:|:----:|:---------:|:-----------:|
| Alfa AWUS036AXML | MT7921AUN | ✅ | ✅ | ✅ | ✅ 6E | ⭐⭐⭐ |
| Alfa AWUS036ACH | RTL8812AU | ✅ | ✅ | ✅ | ❌ | ⭐⭐⭐ |
| Alfa AWUS036ACM | MT7612U | ✅ | ✅ | ✅ | ❌ | ⭐⭐ |
| Alfa AWUS036ACS | RTL8811AU | ✅ | ✅ | ✅ | ❌ | ⭐⭐ |
| TP-Link Archer T2U+ | RTL8821AU | ✅ | ✅ | ✅ | ❌ | ⭐ |
| Panda PAU09 | RT5572 | ✅ | ✅ | ❌ | ❌ | ⭐ |

### SDR Devices

| Device | Frequency | TX | Use Case |
|--------|-----------|:--:|----------|
| RTL-SDR V4 | 500kHz - 1.7GHz | ❌ | IoT sniffing, ADS-B |
| RTL-SDR V3 | 24MHz - 1.7GHz | ❌ | General purpose |
| HackRF One | 1MHz - 6GHz | ✅ | Replay attacks |
| YARD Stick One | 300-928MHz | ✅ | Sub-GHz specialist |

### Other Hardware

| Category | Recommended Device | Notes |
|----------|-------------------|-------|
| **GPS** | u-blox NEO-M8N | USB, high accuracy |
| **Bluetooth** | Sena UD100 | Long range, BT5.0 |
| **OLED Display** | SSD1306 128x64 | I2C, 0.96" |
| **Power** | PiSugar 3 | 5000mAh, UPS |

---

## 🌐 Web Interface & API

### Dashboard

Access the real-time dashboard:

```bash
momo web-url --show-token
# → http://192.168.4.1:8082?token=xxxxx
```

**Features:**
- 🗺️ Real-time wardriving map (Leaflet.js)
- 📊 Live statistics with SSE updates
- 📁 Handshake management
- ⚙️ Configuration editor
- 🔔 Alert notifications

### REST API Endpoints

<details>
<summary><b>Core Endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | System status |
| GET | `/api/stats` | Runtime statistics |
| GET | `/api/config` | Current configuration |
| GET | `/sse/events` | Real-time event stream |
| GET | `/metrics` | Prometheus metrics |

</details>

<details>
<summary><b>WiFi Endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/wardriver/aps` | Discovered access points |
| POST | `/api/eviltwin/start` | Start Evil Twin attack |
| POST | `/api/karma/start` | Start Karma/MANA |
| GET | `/api/wpa3/networks` | WPA3 network list |
| POST | `/api/capture/start` | Start handshake capture |

</details>

<details>
<summary><b>Credential Endpoints (NEW)</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/creds/status` | Harvesting statistics |
| POST | `/api/creds/start` | Start credential harvesting |
| POST | `/api/creds/stop` | Stop harvesting |
| GET | `/api/creds/ntlm` | Captured NTLM hashes |
| GET | `/api/creds/http` | HTTP credentials |
| GET | `/api/creds/kerberos` | Kerberos tickets |
| POST | `/api/creds/export` | Export to file |

</details>

<details>
<summary><b>Hardware Endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/hardware/devices` | Connected devices |
| GET | `/api/ble/devices` | BLE scan results |
| GET | `/api/sdr/spectrum` | Spectrum data |
| GET | `/api/gps/position` | Current GPS position |

</details>

### Authentication

```bash
# Using environment variable
export MOMO_UI_TOKEN="your-secure-token"

# Using header
curl -H "Authorization: Bearer $MOMO_UI_TOKEN" http://localhost:8082/api/status

# Using query parameter (for browsers)
http://localhost:8082/?token=your-secure-token
```

---

## 🔌 Plugin Development

MoMo features a modern, Marauder-inspired plugin architecture with full lifecycle management.

### Creating a Plugin

```python
"""Example MoMo Plugin."""

from momo.core.plugin import Plugin, PluginMetadata, PluginType

class MyAwesomePlugin(Plugin):
    """My custom attack plugin."""
    
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_awesome_plugin",
            version="1.0.0",
            author="Your Name",
            description="Does awesome things",
            plugin_type=PluginType.ATTACK,
            priority=100,
            requires=["wifi"],
        )
    
    async def on_load(self) -> None:
        """Called when plugin is registered."""
        self.log.info("Plugin loaded")
        
        # Subscribe to events
        await self.subscribe("ap_discovered", self.on_ap_found)
    
    async def on_start(self) -> None:
        """Called when plugin is activated."""
        self.log.info("Plugin started")
        
        # Start background task
        self._task = asyncio.create_task(self._worker())
    
    async def on_stop(self) -> None:
        """Called when plugin is deactivated."""
        if self._task:
            self._task.cancel()
        self.log.info("Plugin stopped")
    
    async def on_ap_found(self, event: dict) -> None:
        """Handle discovered access point."""
        ap = event['data']
        self.log.info(f"Found AP: {ap['ssid']}")
        
        # Publish event
        await self.emit("my_event", {"status": "processing"})
    
    async def _worker(self) -> None:
        """Background worker loop."""
        while True:
            await asyncio.sleep(10)
            # Do periodic work


# Entry point
def create_plugin() -> Plugin:
    return MyAwesomePlugin()
```

### Plugin Lifecycle

```
┌──────────┐   load    ┌──────────┐   start   ┌──────────┐
│ UNLOADED │ ────────▶ │  LOADED  │ ────────▶ │ RUNNING  │
└──────────┘           └──────────┘           └────┬─────┘
                                                   │
                                              stop │
                                                   ▼
                                             ┌──────────┐
                                             │ STOPPED  │
                                             └──────────┘
```

| Hook | Async | Use For |
|------|:-----:|---------|
| `on_load()` | ✅ | Event subscriptions, lightweight init |
| `on_start()` | ✅ | Start background tasks, connect to hardware |
| `on_tick(ctx)` | ❌ | Periodic sync operations |
| `on_stop()` | ✅ | Cleanup, stop tasks |
| `on_unload()` | ✅ | Final cleanup |

### Plugin Types

| Type | Priority | Description |
|------|:--------:|-------------|
| `CORE` | 0 | Essential system plugins |
| `SCANNER` | 10 | WiFi/BLE scanning |
| `CAPTURE` | 20 | Data capture |
| `ATTACK` | 30 | Active attacks |
| `ANALYSIS` | 40 | Data analysis |
| `UI` | 50 | User interface |
| `CUSTOM` | 100 | Custom plugins |

---

## ⚙️ Configuration

### Main Configuration File

```yaml
# /etc/momo/momo.yml

# ═══════════════════════════════════════════════════════════════════
# General Settings
# ═══════════════════════════════════════════════════════════════════
mode: aggressive                    # passive, balanced, aggressive

interface:
  name: wlan1                       # Primary attack interface
  mac_randomization: true
  channel_hop: true
  channels: [1, 6, 11]              # 2.4GHz channels
  channels_5ghz: [36, 40, 44, 48]   # 5GHz non-DFS channels

# ═══════════════════════════════════════════════════════════════════
# Headless Operation
# ═══════════════════════════════════════════════════════════════════
management:
  enabled: true
  interface: wlan0                  # Pi5 internal WiFi
  mode: ap                          # ap or client
  ap_ssid: MoMo-Management
  ap_password: YourSecurePassword   # ⚠️ CHANGE THIS
  auto_whitelist: true              # Protect from self-attack
  bind_web_to_management: true

oled:
  enabled: true
  i2c_address: "0x3C"
  menu:
    enabled: true
    idle_timeout: 30.0

# ═══════════════════════════════════════════════════════════════════
# Attack Modules
# ═══════════════════════════════════════════════════════════════════
aggressive:
  enabled: true
  deauth:
    enabled: true
    max_per_minute: 0               # 0 = unlimited
  evil_twin:
    enabled: true
  pmkid:
    enabled: true
  ssid_blacklist: []                # Your networks (protected)

eviltwin:
  enabled: false
  portal_template: generic          # generic, hotel, corporate, facebook, google, router

karma:
  enabled: false
  respond_to_all: true
  capture_eap: true

wpa3:
  enabled: true
  auto_downgrade: false

# ═══════════════════════════════════════════════════════════════════
# Credential Harvesting
# ═══════════════════════════════════════════════════════════════════
creds:
  enabled: false
  interface: eth0
  output_dir: logs/creds
  
  responder:
    enabled: true
    llmnr: true
    nbns: true
  
  ntlm:
    enabled: true
    smb_port: 445
    http_port: 80
  
  http:
    enabled: true
    ports: [80, 8080, 8000]
  
  kerberos:
    enabled: false
    dc_ip: ""
    domain: ""

# ═══════════════════════════════════════════════════════════════════
# Auto-Pwn Mode
# ═══════════════════════════════════════════════════════════════════
autopwn:
  enabled: false
  mode: balanced                    # passive, balanced, aggressive
  min_signal_dbm: -80
  max_concurrent_attacks: 1
  enable_pmkid: true
  enable_deauth: true
  enable_eviltwin: false

# ═══════════════════════════════════════════════════════════════════
# Hardware
# ═══════════════════════════════════════════════════════════════════
ble:
  enabled: false
  scan_duration: 5.0

sdr:
  enabled: false
  device_type: rtlsdr

hardware:
  auto_detect: true
  auto_configure: true

# ═══════════════════════════════════════════════════════════════════
# Cracking & Sync
# ═══════════════════════════════════════════════════════════════════
cracking:
  enabled: true
  use_john: true
  cloud_enabled: false
  nexus_api_url: ""

plugins:
  enabled:
    - wardriver
    - active_wifi
    - creds_harvester
```

---

## 🔧 CLI Reference

```bash
# ═══════════════════════════════════════════════════════════════════
# General Commands
# ═══════════════════════════════════════════════════════════════════
momo version                    # Show version and build info
momo doctor                     # Run system diagnostics
momo status                     # Show runtime status

# ═══════════════════════════════════════════════════════════════════
# Running MoMo
# ═══════════════════════════════════════════════════════════════════
momo run                        # Start with default config
momo run -c /path/to/momo.yml   # Start with custom config
momo run --dry-run              # Simulate without hardware
momo run --debug                # Enable debug logging

# ═══════════════════════════════════════════════════════════════════
# Web Interface
# ═══════════════════════════════════════════════════════════════════
momo web-url                    # Show Web UI URL
momo web-url --show-token       # Include auth token

# ═══════════════════════════════════════════════════════════════════
# Maintenance
# ═══════════════════════════════════════════════════════════════════
momo rotate-now                 # Force log rotation
momo export --format hashcat    # Export captured data
momo backup                     # Backup configuration
```

---

## 🌐 MoMo Ecosystem

MoMo is part of an integrated offensive security ecosystem. Each project is designed for seamless collaboration.

```
                              ☁️ CLOUD LAYER
                    ┌─────────────────────────────────┐
                    │  GPU Cracking  │  Evilginx VPS  │
                    └────────────────┬────────────────┘
                                     │
                              ┌──────▼──────┐
                              │             │
                              │ 🟢 NEXUS    │
                              │ Central Hub │
                              │             │
                              └──────┬──────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
    ┌──────▼──────┐          ┌───────▼───────┐         ┌──────▼──────┐
    │             │          │               │         │             │
    │  🔵 MOMO    │◀────────▶│ 👻 GHOSTBRIDGE│◀───────▶│  🎭 MIMIC   │
    │   WiFi/BLE  │          │    Network    │         │  USB Attack │
    │    Pi 5     │          │    Implant    │         │  Pi Zero    │
    │             │          │               │         │             │
    └─────────────┘          └───────────────┘         └─────────────┘
```

### Ecosystem Components

| Project | Description | Platform | Links |
|---------|-------------|----------|-------|
| **🔵 MoMo** | WiFi/BLE/SDR Audit Platform | Pi 5 | [GitHub](https://github.com/Momo-Master/MoMo) |
| **🟢 Nexus** | Central C2 Hub | Pi 4 | [GitHub](https://github.com/Momo-Master/MoMo-Nexus) |
| **👻 GhostBridge** | Transparent Network Implant | NanoPi R2S | [GitHub](https://github.com/Momo-Master/Momo-GhostBridge) |
| **🎭 Mimic** | USB Attack Platform | Pi Zero 2W | [GitHub](https://github.com/Momo-Master/MoMo-Mimic) |

### Nexus Integration

```yaml
# Enable Nexus sync in momo.yml
nexus:
  enabled: true
  api_url: "http://nexus.local:8080"
  device_id: "momo-field-01"
  sync_interval: 30
  
  sync:
    handshakes: true
    credentials: true
    wardriving: true
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [📖 OPERATIONS.md](docs/OPERATIONS.md) | Operations guide & best practices |
| [🔐 SECURITY.md](docs/SECURITY.md) | Security hardening & OPSEC |
| [🔧 HARDWARE.md](docs/HARDWARE.md) | Hardware setup & recommendations |
| [📡 WIFI_ATTACKS.md](docs/WIFI_ATTACKS.md) | WiFi attack techniques |
| [🔑 CREDENTIALS.md](docs/CREDENTIALS.md) | Credential harvesting guide |
| [🤖 AUTOPWN.md](docs/AUTOPWN.md) | Auto-Pwn mode documentation |
| [🚀 FIRST_BOOT.md](docs/FIRST_BOOT.md) | First Boot Wizard guide |
| [🔌 PLUGINS.md](docs/PLUGINS.md) | Plugin development guide |
| [🗺️ ROADMAP.md](docs/ROADMAP.md) | Development roadmap |
| [📝 CHANGELOG.md](docs/CHANGELOG.md) | Version history |

---

## 📊 Project Status

| Version | Phase | Status |
|---------|-------|:------:|
| v0.1.0 | Core Infrastructure | ✅ |
| v0.5.0 | Bluetooth Scanner | ✅ |
| v0.7.0 | Cracking Integration | ✅ |
| v1.0.0 | WPA3/SAE Attacks | ✅ |
| v1.2.0 | Bluetooth Expansion | ✅ |
| v1.5.0 | SDR Integration | ✅ |
| v1.5.2 | Management Network | ✅ |
| v1.6.0 | Credential Harvesting | ✅ |
| **v1.7.0** | **First Boot Wizard** | ✅ **NEW** |

**Statistics:**
- 📝 **527 Tests** passing
- 📊 **87% Coverage**
- 🔌 **52 Plugins** available
- 📡 **6 Attack Modules**

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing`)
3. **Commit** changes (`git commit -m 'feat: add amazing feature'`)
4. **Push** to branch (`git push origin feature/amazing`)
5. **Open** a Pull Request

### Commit Convention

```
type(scope): description

Types: feat, fix, docs, style, refactor, test, chore
```

### Development Workflow

```bash
# Setup
git clone https://github.com/Momo-Master/MoMo.git
cd MoMo
pip install -e ".[dev]"
pre-commit install

# Test
pytest tests/ -v --cov=momo

# Lint
ruff check momo/
mypy momo/

# Format
black momo/
```

---

## ⚠️ Legal Disclaimer

> **MoMo is designed for authorized security testing and educational purposes only.**

- ✅ Only use on networks you own or have explicit written permission to test
- ✅ Respect local laws and regulations regarding wireless security testing
- ✅ Follow responsible disclosure practices
- ❌ The developers are not responsible for misuse of this tool
- ❌ Unauthorized access to computer systems is illegal

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <img src="docs/assets/ecosystem-banner.png" alt="MoMo Ecosystem" width="600">
</p>

<p align="center">
  <strong>Part of the 🔥 MoMo Ecosystem</strong><br>
  <sub>Inspired by Pwnagotchi • ESP32 Marauder • WiFi Pineapple</sub>
</p>

<p align="center">
  <a href="https://github.com/Momo-Master/MoMo">🔵 MoMo</a> •
  <a href="https://github.com/Momo-Master/MoMo-Nexus">🟢 Nexus</a> •
  <a href="https://github.com/Momo-Master/Momo-GhostBridge">👻 GhostBridge</a> •
  <a href="https://github.com/Momo-Master/MoMo-Mimic">🎭 Mimic</a>
</p>

<p align="center">
  <sub>Made with ❤️ by the MoMo Team</sub>
</p>
