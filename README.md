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
| **Evil Twin** | Rogue AP with captive portal (6 templates) | ✅ |
| **Handshake Capture** | EAPOL 4-way handshake collection | ✅ |
| **Auto Cracking** | hashcat integration with wordlist management | ✅ |
| **BLE Scanner** | Bluetooth device & beacon detection | ✅ |

### 🛠️ Technical Highlights
- **Async-First Architecture** - Non-blocking I/O with `asyncio`
- **Clean Architecture** - 4-layer separation (Presentation → Application → Domain → Infrastructure)
- **Modern Plugin System** - Marauder-inspired with lifecycle hooks & event communication
- **Real-time Web UI** - Dark theme dashboard with SSE updates
- **Event-Driven** - Pub/Sub event bus for decoupled components
- **65+ Unit Tests** - Comprehensive test coverage with pytest-asyncio

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
│   ├── ble/                # Bluetooth scanner
│   ├── capture/            # Handshake capture
│   ├── eviltwin/           # Rogue AP, captive portal
│   ├── cracking/           # Hashcat integration
│   └── database/           # Async SQLite repository
├── plugins/                 # Modern plugins (new architecture)
├── apps/
│   ├── momo_core/          # Main service loop
│   ├── momo_plugins/       # Legacy plugins
│   └── momo_web/           # Flask API + Web UI
└── config.py               # Pydantic configuration
```

---

## 🔌 Plugin Development

MoMo features a modern, Marauder-inspired plugin architecture. Creating your own plugin is simple:

### Quick Start

Create a new file in `momo/plugins/`:

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
            priority=100,  # Lower = loads first
        )
    
    async def on_start(self) -> None:
        """Called when plugin starts."""
        self.log.info("My plugin started!")
        await self.emit("started", {"status": "ready"})
    
    async def on_stop(self) -> None:
        """Called when plugin stops."""
        self.log.info("My plugin stopped!")
    
    def on_tick(self, ctx: dict) -> None:
        """Called periodically (optional)."""
        self.increment_metric("ticks")
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

### Event Communication

Plugins can communicate via events:

```python
# Emit an event
await self.emit("scan_complete", {"aps_found": 42})

# Subscribe to events (in on_load)
def on_load(self):
    self.on("wifi_scanner.ap_discovered", self.handle_ap)
    self.on("system.tick", self.handle_tick)

def handle_ap(self, data: dict):
    ssid = data.get("ssid", "<hidden>")
    self.log.info(f"New AP: {ssid}")
```

### Accessing Other Plugins

```python
async def on_start(self):
    # Get another plugin
    scanner = self.get_plugin("wifi_scanner")
    if scanner:
        aps = scanner.get_aps()
    
    # Require a plugin (raises error if not found)
    gps = self.require_plugin("gps_tracker")
```

### Built-in Features

```python
# Logging (automatic per-plugin logger)
self.log.info("Message")
self.log.error("Error: %s", error)

# Metrics (Prometheus-compatible)
self.increment_metric("scans")
self.increment_metric("errors", 5)

# Access config
interval = self.config.get("interval", 10)

# Check state
if self.is_running:
    ...
```

### Plugin Types

| Type | Description |
|------|-------------|
| `CORE` | Essential system plugins |
| `SCANNER` | WiFi/BLE scanning |
| `ATTACK` | Active attacks (deauth, evil twin) |
| `CAPTURE` | Data capture (handshakes) |
| `ANALYSIS` | Data analysis, cracking |
| `UI` | User interface plugins |
| `UTIL` | Utilities |
| `CUSTOM` | Custom plugins (default) |

### Full Example

See `momo/plugins/example_plugin.py` for a complete template with:
- Background tasks
- Event handling
- Configuration access
- Metrics tracking
- Custom status

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
| `/handshakes` | Captured handshakes |
| `/captures` | Capture management |
| `/bluetooth` | BLE device scanner |
| `/eviltwin` | Evil Twin attack control |
| `/cracking` | Password cracking jobs |
| `/config` | Configuration view |
| `/api/status` | System status |
| `/api/wardriver/aps.geojson` | Access points as GeoJSON |
| `/api/ble/*` | BLE scanner API |
| `/api/eviltwin/*` | Evil Twin API |
| `/api/cracking/*` | Cracking API |
| `/sse/events` | Real-time event stream |
| `/metrics` | Prometheus metrics |

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
  enabled: true               # Enable BLE scanning
  scan_duration: 5.0
  detect_beacons: true

eviltwin:
  enabled: false              # Evil Twin attacks
  portal_template: generic    # generic, hotel, corporate, facebook, google, router

cracking:
  enabled: true
  auto_crack: false           # Auto-crack new handshakes
  workload_profile: 3         # 1-4 (hashcat -w)

plugins:
  enabled: 
    - wardriver
    - active_wifi
    - ble_scanner
    - hashcat_cracker
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
| [Plugin Development](#-plugin-development) | Create custom plugins |

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
| Handshake Capture | v0.4.0 | ✅ Complete |
| Bluetooth Scanner | v0.5.0 | ✅ Complete |
| Evil Twin | v0.6.0 | ✅ Complete |
| Cracking Integration | v0.7.0 | ✅ Complete |
| Plugin Architecture | v0.8.0 | ✅ Complete |

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built with 🔥 by the MoMo Team</strong><br>
  <sub>Inspired by Pwnagotchi, ESP32 Marauder, and WiFi Pineapple</sub>
</p>
