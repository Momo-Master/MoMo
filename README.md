<p align="center">
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%205-c51a4a?style=for-the-badge&logo=raspberry-pi" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Mode-Aggressive-ff0000?style=for-the-badge" alt="Mode">
</p>

<h1 align="center">🔥 MoMo</h1>
<h3 align="center">Modular Offensive Mobile Operations</h3>

<p align="center">
  <strong>The Open-Source WiFi Pineapple Alternative</strong><br>
  Combining Pwnagotchi + ESP32 Marauder + WiFi Pineapple in one powerful platform
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

MoMo is a **Raspberry Pi 5** based wireless security audit platform designed for penetration testers and security researchers. It provides a comprehensive toolkit for WiFi reconnaissance, handshake capture, and network analysis.

```
┌─────────────────────────────────────────────────────────────────┐
│                         MoMo Platform                            │
├─────────────────────────────────────────────────────────────────┤
│  📡 Multi-Radio      │  🗺️ GPS Wardriving   │  🔐 PMKID Capture  │
│  ⚡ Deauth Attacks    │  👿 Evil Twin        │  📊 Real-time UI   │
│  🔌 Plugin System    │  📈 Prometheus       │  🐍 Async Python   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### 🔥 Offensive Capabilities
| Feature | Description | Status |
|---------|-------------|--------|
| **Wardriving** | GPS-correlated AP scanning with SQLite persistence | ✅ |
| **Multi-Radio** | Manage multiple WiFi adapters simultaneously | ✅ |
| **PMKID Capture** | Clientless WPA2 attack via hcxdumptool | ✅ |
| **Deauth Attacks** | Targeted client disconnection | ✅ |
| **Evil Twin** | Rogue AP with captive portal | 🔜 |
| **Handshake Capture** | EAPOL 4-way handshake collection | ✅ |
| **Auto Cracking** | hashcat/john integration | ✅ |

### 🛠️ Technical Highlights
- **Async-First Architecture** - Non-blocking I/O with `asyncio`
- **Clean Architecture** - 4-layer separation (Presentation → Application → Domain → Infrastructure)
- **Plugin System** - Drop-in extensibility
- **Real-time Web UI** - Leaflet.js maps with SSE updates
- **Event-Driven** - Pub/Sub event bus for decoupled components
- **104+ Unit Tests** - Comprehensive test coverage

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
├── core/                    # Event bus, security utilities
│   ├── events.py           # Pub/Sub event system
│   └── security.py         # Input sanitization
├── domain/                  # Pydantic models
│   └── models.py           # AccessPoint, GPSPosition, etc.
├── infrastructure/          # Hardware abstraction
│   ├── wifi/               # Scanner, RadioManager
│   ├── gps/                # GPS client, distance tracker
│   └── database/           # Async SQLite repository
├── apps/
│   ├── momo_core/          # Main service loop
│   ├── momo_plugins/       # Extensible plugins
│   └── momo_web/           # Flask API + Web UI
└── config.py               # Pydantic configuration
```

---

## 📡 Supported Hardware

### WiFi Adapters (Tested)
| Adapter | Chipset | Monitor | Injection | 5GHz |
|---------|---------|---------|-----------|------|
| TP-Link Archer T2U Plus | RTL8821AU | ✅ | ✅ | ✅ |
| Alfa AWUS036ACH | RTL8812AU | ✅ | ✅ | ✅ |
| Alfa AWUS036ACM | MT7612U | ✅ | ✅ | ✅ |
| Panda PAU09 | RT5572 | ✅ | ✅ | ❌ |

### GPS Modules
| Module | Interface | Notes |
|--------|-----------|-------|
| u-blox NEO-6M | USB/UART | Budget friendly |
| u-blox NEO-M8N | USB/UART | Better accuracy |
| GlobalSat BU-353S4 | USB | Plug-and-play |

---

## 🌐 Web Interface

Access the real-time dashboard:

```bash
# Get URL and token
momo web-url --show-token

# Access API
curl -H "Authorization: Bearer <token>" http://<ip>:8082/api/status
```

### Endpoints
| Endpoint | Description |
|----------|-------------|
| `/` | Dashboard |
| `/map` | Wardriving map (Leaflet.js) |
| `/api/status` | System status |
| `/api/wardriver/aps.geojson` | Access points as GeoJSON |
| `/sse/events` | Real-time event stream |
| `/metrics` | Prometheus metrics |
| `/healthz` | Health check |

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
  deauth:
    max_per_minute: 0         # Unlimited
  ssid_blacklist: []          # Your networks (protected)
  ssid_whitelist: []          # Target focus (optional)

plugins:
  enabled: 
    - wardriver
    - active_wifi
    - instattack
    - cracker
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [OPERATIONS.md](docs/OPERATIONS.md) | Operations guide |
| [SECURITY.md](docs/SECURITY.md) | Security hardening |
| [HARDWARE.md](docs/HARDWARE.md) | Hardware setup |
| [ONERILER.md](docs/ONERILER.md) | Technical roadmap |
| [ACTIVE_WIFI.md](docs/ACTIVE_WIFI.md) | Deauth/beacon attacks |
| [CRACKING.md](docs/CRACKING.md) | Password cracking |

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

## 📊 Project Status

| Phase | Version | Status |
|-------|---------|--------|
| Core Infrastructure | v0.1.0 | ✅ Complete |
| Wardriving & GPS | v0.2.0 | ✅ Complete |
| Multi-Radio | v0.3.0 | ✅ Complete |
| Handshake Capture | v0.4.0 | 🔜 In Progress |
| Bluetooth | v0.5.0 | 📅 Planned |
| Evil Twin | v0.6.0 | 📅 Planned |

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details..

---

<p align="center">
  <strong>Built with 🔥 by the MoMo Team</strong><br>
  <sub>Inspired by Pwnagotchi, ESP32 Marauder, and WiFi Pineapple</sub>
</p>
