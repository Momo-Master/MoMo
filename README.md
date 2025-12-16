<p align="center">
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%205-c51a4a?style=for-the-badge&logo=raspberry-pi" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Tests-419%20Passing-success?style=for-the-badge" alt="Tests">
</p>

<h1 align="center">🔥 MoMo</h1>
<h3 align="center">Modular Offensive Mobile Operations</h3>

<p align="center">
  <strong>Raspberry Pi 5 Wardriving & Wireless Pentest Platform</strong><br>
  WiFi • BLE • SDR | WPA3 Downgrade • Karma/MANA • Evil Twin • Evilginx AiTM
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-documentation">Docs</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 🎯 What is MoMo?

MoMo is a **Raspberry Pi 5** based wireless security audit platform designed for penetration testers and security researchers. It combines the best features of Pwnagotchi, ESP32 Marauder, and WiFi Pineapple into one powerful, modular platform.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            MoMo Platform                                  │
├──────────────────────────────────────────────────────────────────────────┤
│  📡 Multi-Radio      │  🗺️ GPS Wardriving    │  🔐 WPA2/WPA3 Attacks    │
│  👿 Evil Twin        │  🎭 Karma/MANA        │  🔓 Evilginx AiTM        │
│  📻 SDR Integration  │  🦷 BLE Attacks       │  💥 Hashcat + John       │
│  🔌 Plugin System    │  📊 Real-time UI      │  🔧 Hardware Auto-Detect │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### 🔥 WiFi Attacks
| Feature | Description | Status |
|---------|-------------|--------|
| **Wardriving** | GPS-correlated AP scanning with SQLite persistence | ✅ |
| **Multi-Radio** | Manage multiple WiFi adapters simultaneously | ✅ |
| **PMKID Capture** | Clientless WPA2 attack via hcxdumptool | ✅ |
| **Deauth Attacks** | Targeted client disconnection | ✅ |
| **Handshake Capture** | EAPOL 4-way handshake collection | ✅ |
| **WPA3 Attacks** | SAE detection, downgrade attacks, PMF handling | ✅ |
| **Evil Twin** | Rogue AP with captive portal (6 templates) | ✅ |
| **Karma/MANA** | Auto-respond to probe requests, EAP credential capture | ✅ |
| **Evilginx AiTM** | MFA bypass via session cookie capture | ✅ |

### 🦷 Bluetooth Attacks
| Feature | Description | Status |
|---------|-------------|--------|
| **BLE Scanner** | Bluetooth device & beacon detection | ✅ |
| **GATT Explorer** | Service/characteristic discovery & read/write | ✅ |
| **Beacon Spoofing** | iBeacon & Eddystone frame injection | ✅ |
| **HID Injection** | Bluetooth keyboard emulation & keystroke injection | ✅ |

### 📻 SDR Integration
| Feature | Description | Status |
|---------|-------------|--------|
| **RTL-SDR Support** | V3 & V4 (HF direct sampling, bias tee) | ✅ |
| **HackRF Support** | TX/RX capable SDR | ✅ |
| **Spectrum Analyzer** | Frequency scanning & peak detection | ✅ |
| **Signal Decoder** | 433/868 MHz IoT signal capture | ✅ |

### 💥 Cracking & Analysis
| Feature | Description | Status |
|---------|-------------|--------|
| **Hashcat Integration** | GPU-accelerated password cracking | ✅ |
| **John the Ripper** | CPU-based cracking alternative | ✅ |
| **Auto Cracking** | Automatic crack on handshake capture | ✅ |
| **Wordlist Management** | Custom wordlist support | ✅ |

### 🛠️ Technical Highlights
- **Async-First Architecture** - Non-blocking I/O with `asyncio`
- **Clean Architecture** - 4-layer separation (Presentation → Application → Domain → Infrastructure)
- **Modern Plugin System** - Marauder-inspired with lifecycle hooks & event communication
- **Real-time Web UI** - Dark theme dashboard with SSE updates
- **Event-Driven** - Pub/Sub event bus for decoupled components
- **Hardware Auto-Detection** - Automatic USB device identification & configuration
- **419 Unit Tests** - Comprehensive test coverage with pytest-asyncio

---

## 🚀 Quick Start

### Option 1: One-Line Install (Raspberry Pi 5)

```bash
curl -fsSL https://raw.githubusercontent.com/Momo-Master/MoMo/main/deploy/momo-quickstart.sh | sudo bash
```

### Option 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/Momo-Master/MoMo.git
cd MoMo

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Verify installation
momo version
momo doctor
```

### Option 3: Development Mode

```bash
# Install with dev dependencies
pip install -e ".[dev]"
pre-commit install

# Run tests
pytest tests/ -v

# Run with dry-run (no hardware needed)
momo run -c configs/momo.yml --dry-run
```

---

## 🏗️ Architecture

```
momo/
├── core/                    # Event bus, plugin system, utilities
│   ├── events.py           # Pub/Sub event system
│   ├── plugin.py           # Modern plugin architecture
│   └── security.py         # Input sanitization
├── domain/                  # Pydantic models
│   └── models.py           # AccessPoint, GPSPosition, etc.
├── infrastructure/          # Hardware abstraction
│   ├── wifi/               # Scanner, RadioManager
│   ├── gps/                # GPS client, distance tracker
│   ├── ble/                # BLE scanner, GATT, HID, Beacon
│   ├── capture/            # Handshake capture
│   ├── eviltwin/           # Rogue AP, captive portal
│   ├── evilginx/           # AiTM proxy, phishlets
│   ├── wpa3/               # WPA3 detection & attacks
│   ├── karma/              # Karma/MANA attacks
│   ├── cracking/           # Hashcat & John integration
│   ├── sdr/                # RTL-SDR, HackRF, spectrum
│   ├── hardware/           # Device registry, auto-detection
│   └── database/           # Async SQLite repository
├── plugins/                 # Modern plugins (new architecture)
├── apps/
│   ├── momo_core/          # Main service loop
│   ├── momo_plugins/       # Legacy plugins
│   └── momo_web/           # Flask API + Web UI
└── config.py               # Pydantic configuration
```

---

## 📡 Supported Hardware

### WiFi Adapters
| Adapter | Chipset | Monitor | Injection | 5GHz | WiFi 6/6E |
|---------|---------|---------|-----------|------|-----------|
| Alfa AWUS036AXML | MT7921AUN | ✅ | ✅ | ✅ | ✅ WiFi 6E |
| Alfa AWUS036ACH | RTL8812AU | ✅ | ✅ | ✅ | ❌ |
| Alfa AWUS036ACM | MT7612U | ✅ | ✅ | ✅ | ❌ |
| Alfa AWUS036ACS | RTL8811AU | ✅ | ✅ | ✅ | ❌ |
| TP-Link Archer T2U Plus | RTL8821AU | ✅ | ✅ | ✅ | ❌ |
| Panda PAU09 | RT5572 | ✅ | ✅ | ❌ | ❌ |

### SDR Devices
| Device | Frequency Range | TX | Notes |
|--------|-----------------|-----|-------|
| RTL-SDR V4 | 500 kHz - 1.7 GHz | ❌ | HF direct sampling, bias tee |
| RTL-SDR V3 | 24 MHz - 1.7 GHz | ❌ | Bias tee support |
| HackRF One | 1 MHz - 6 GHz | ✅ | Full duplex capable |
| YARD Stick One | Sub-1 GHz | ✅ | 300-928 MHz specialist |

### Bluetooth Adapters
| Adapter | Chipset | BLE | Classic | Notes |
|---------|---------|-----|---------|-------|
| Sena UD100 | CSR8510 | ✅ | ✅ | Long range |
| Plugable USB-BT4LE | BCM20702 | ✅ | ✅ | Reliable |
| ASUS USB-BT500 | RTL8761B | ✅ | ✅ | BT 5.0 |

### GPS Modules
| Module | Interface | Chipset | Notes |
|--------|-----------|---------|-------|
| u-blox NEO-6M | USB/UART | u-blox 6 | Budget friendly |
| u-blox NEO-M8N | USB/UART | u-blox M8 | Better accuracy |
| u-blox NEO-M9N | USB/UART | u-blox M9 | Multi-GNSS |
| GlobalSat BU-353S4 | USB | SiRF Star IV | Plug-and-play |

---

## 🌐 Web Interface

Access the real-time dashboard:

```bash
# Get URL and token
momo web-url --show-token

# Access API
curl -H "Authorization: Bearer <token>" http://<ip>:8082/api/status
```

### API Endpoints

#### Core
| Endpoint | Description |
|----------|-------------|
| `/` | Dashboard |
| `/map` | Wardriving map (Leaflet.js) |
| `/handshakes` | Captured handshakes |
| `/captures` | Capture management |
| `/config` | Configuration view |
| `/api/status` | System status |
| `/sse/events` | Real-time event stream |
| `/metrics` | Prometheus metrics |

#### WiFi Attacks
| Endpoint | Description |
|----------|-------------|
| `/api/wardriver/*` | Wardriving API |
| `/api/eviltwin/*` | Evil Twin API |
| `/api/evilginx/*` | Evilginx AiTM API |
| `/api/wpa3/*` | WPA3/SAE Attack API |
| `/api/karma/*` | Karma/MANA Attack API |

#### Bluetooth
| Endpoint | Description |
|----------|-------------|
| `/bluetooth` | BLE device scanner UI |
| `/api/ble/*` | BLE Scanner API |
| `/api/ble/gatt/*` | GATT Explorer API |
| `/api/ble/beacon/*` | Beacon Spoofing API |
| `/api/ble/hid/*` | HID Injection API |

#### SDR & Hardware
| Endpoint | Description |
|----------|-------------|
| `/api/sdr/*` | SDR Management API |
| `/api/sdr/spectrum/*` | Spectrum Analyzer API |
| `/api/sdr/decoder/*` | Signal Decoder API |
| `/api/hardware/*` | Hardware Detection API |

#### Cracking
| Endpoint | Description |
|----------|-------------|
| `/cracking` | Cracking jobs UI |
| `/api/cracking/*` | Hashcat API |
| `/api/cracking/john/*` | John the Ripper API |

---

## 🔌 Plugin Development

MoMo features a modern, Marauder-inspired plugin architecture:

```python
from momo.core import BasePlugin, PluginMetadata, PluginType

class MyPlugin(BasePlugin):
    """My awesome plugin."""
    
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            author="Your Name",
            description="What my plugin does",
            plugin_type=PluginType.CUSTOM,
            priority=100,
        )
    
    async def on_start(self) -> None:
        self.log.info("My plugin started!")
        await self.emit("started", {"status": "ready"})
    
    async def on_stop(self) -> None:
        self.log.info("My plugin stopped!")
```

### Plugin Lifecycle

```
UNLOADED → LOADING → LOADED → STARTING → RUNNING → STOPPING → STOPPED
                ↓                                        ↓
              ERROR ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←← ERROR
```

| Hook | When Called | Use For |
|------|-------------|---------|
| `on_load()` | Plugin registered | Lightweight init, event subscriptions |
| `on_start()` | Plugin activated | Async init, start background tasks |
| `on_tick(ctx)` | Periodically | Sync operations (optional) |
| `on_stop()` | Plugin deactivated | Cleanup, stop tasks |
| `on_unload()` | Plugin removed | Final cleanup |

### Plugin Types

| Type | Description |
|------|-------------|
| `CORE` | Essential system plugins |
| `SCANNER` | WiFi/BLE scanning |
| `ATTACK` | Active attacks (deauth, evil twin, karma) |
| `CAPTURE` | Data capture (handshakes) |
| `ANALYSIS` | Data analysis, cracking |
| `UI` | User interface plugins |
| `UTIL` | Utilities |
| `CUSTOM` | Custom plugins (default) |

See `momo/plugins/example_plugin.py` for a complete template.

---

## ⚙️ Configuration

Edit `configs/momo.yml`:

```yaml
mode: aggressive              # Full offensive mode

interface:
  name: wlan1
  regulatory_domain: "00"     # Global (unrestricted)

aggressive:
  enabled: true
  max_deauth_per_min: 0       # Unlimited
  ssid_blacklist: []          # Your networks (protected)
  ssid_whitelist: []          # Target focus (optional)

ble:
  enabled: true
  scan_duration: 5.0
  detect_beacons: true

eviltwin:
  enabled: false
  portal_template: generic    # generic, hotel, corporate, facebook, google, router

karma:
  enabled: false
  respond_to_all: true        # Respond to all probe requests
  capture_eap: true           # Capture EAP credentials

wpa3:
  enabled: true
  auto_downgrade: false       # Auto-attempt WPA3→WPA2 downgrade

sdr:
  enabled: false
  device_type: rtlsdr         # rtlsdr, hackrf
  bias_tee: false             # Enable bias tee (RTL-SDR V3/V4)

hardware:
  auto_detect: true           # Auto-detect USB devices
  auto_configure: true        # Auto-configure detected devices

cracking:
  enabled: true
  auto_crack: false           # Auto-crack new handshakes
  engine: hashcat             # hashcat, john
  workload_profile: 3         # 1-4 (hashcat -w)

plugins:
  enabled: 
    - wardriver
    - active_wifi
    - ble_scanner
    - hashcat_cracker
```

---

## 🔧 CLI Reference

```bash
momo version                  # Show version
momo doctor                   # System diagnostics
momo run -c momo.yml          # Start capture loop
momo run --dry-run            # Simulate without hardware
momo status                   # Show runtime status
momo rotate-now               # Force log rotation
momo web-url --show-token     # Show Web UI credentials
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [OPERATIONS.md](docs/OPERATIONS.md) | Operations guide |
| [SECURITY.md](docs/SECURITY.md) | Security hardening |
| [HARDWARE.md](docs/HARDWARE.md) | Hardware setup |
| [ACTIVE_WIFI.md](docs/ACTIVE_WIFI.md) | Deauth/beacon attacks |
| [CRACKING.md](docs/CRACKING.md) | Password cracking |
| [EVILGINX.md](docs/EVILGINX.md) | MFA bypass (AiTM) |
| [PLUGINS.md](docs/PLUGINS.md) | Plugin documentation |
| [ROADMAP.md](docs/ROADMAP.md) | Development roadmap |
| [DEVLOG.md](docs/DEVLOG.md) | Development changelog |

---

## 📊 Project Status

| Phase | Version | Status |
|-------|---------|--------|
| Core Infrastructure | v0.1.0 | ✅ Complete |
| Wardriving & GPS | v0.2.0 | ✅ Complete |
| Multi-Radio | v0.3.0 | ✅ Complete |
| Handshake Capture | v0.4.0 | ✅ Complete |
| Bluetooth Scanner | v0.5.0 | ✅ Complete |
| Evil Twin | v0.6.0 | ✅ Complete |
| Cracking Integration | v0.7.0 | ✅ Complete |
| Plugin Architecture | v0.8.0 | ✅ Complete |
| Evilginx AiTM | v0.9.0 | ✅ Complete |
| WPA3/SAE Attacks | v0.10.0 | ✅ Complete |
| Karma/MANA Attacks | v1.1.0 | ✅ Complete |
| Bluetooth Expansion | v1.2.0 | ✅ Complete |
| Advanced Cracking | v1.3.0 | ✅ Complete |
| SDR Integration | v1.5.0 | ✅ Complete |
| Hardware Auto-Detection | v1.5.1 | ✅ Complete |

**Total: 419 Tests Passing** ✅

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

### Development Setup

```bash
pip install -e ".[dev]"
pre-commit install
pytest tests/ -v --cov=momo
```

---

## ⚠️ Legal Disclaimer

**MoMo is designed for authorized security testing and educational purposes only.**

- Only use on networks you own or have explicit written permission to test
- Respect local laws and regulations regarding wireless security testing
- The developers are not responsible for misuse of this tool

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built with 🔥 by the MoMo Team</strong><br>
  <sub>Inspired by Pwnagotchi, ESP32 Marauder, and WiFi Pineapple</sub>
</p>
