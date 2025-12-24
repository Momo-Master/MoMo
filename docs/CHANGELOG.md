# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2025-12-24 (First Boot Wizard) ✅

### Added
- **First Boot Wizard** - Web-based setup experience for new devices
  - Language selection (English, Turkish)
  - Admin password configuration with strength validation
  - Network setup (AP mode or client mode)
  - Operation profile selection (passive, balanced, aggressive)
  - Nexus integration with mDNS auto-discovery
  - Configuration summary and confirmation
- **Headless Configuration** - `/boot/momo-config.yml` for automated setup
- **OLED QR Code Display** - WiFi credentials QR code on OLED screen
- **Captive Portal** - Automatic redirect to wizard on first connection
- **mDNS Nexus Discovery** - Find Nexus devices on local network
- **Nexus Device Registration** - Auto-register with Nexus hub
- **New CLI Command** - `momo-firstboot` for wizard control
- **43 unit tests** for first boot system
- **React Frontend** - Modern wizard UI with Tailwind CSS

### Backend Modules
| Module | Description |
|--------|-------------|
| `detector.py` | Boot mode detection (normal/headless/wizard) |
| `network.py` | WiFi AP, DHCP, captive portal management |
| `server.py` | FastAPI wizard server with 15+ endpoints |
| `nexus.py` | mDNS discovery and Nexus registration |
| `config_generator.py` | Config file generation |
| `oled.py` | OLED display with QR code support |

### Frontend Pages
| Page | Description |
|------|-------------|
| `Welcome.tsx` | Language selection |
| `Password.tsx` | Admin password with strength meter |
| `Network.tsx` | WiFi AP/client configuration |
| `Profile.tsx` | Operation profile selection |
| `Nexus.tsx` | Nexus connection with discovery |
| `Summary.tsx` | Configuration review |
| `Complete.tsx` | Success screen with redirect |

### Configuration
```yaml
# /boot/momo-config.yml (headless setup)
setup:
  skip_wizard: true
  language: en

security:
  admin_password: "YourSecurePassword123!"

network:
  mode: ap
  ap:
    ssid: MoMo-Management
    password: MoMoAdmin2024!

profile: balanced

nexus:
  enabled: true
  url: "http://192.168.1.100:8080"
```

### Installation
```bash
# Install with firstboot dependencies
pip install -e ".[firstboot]"

# Enable systemd service
sudo systemctl enable momo-firstboot
```

---

## [1.6.0] - 2025-12-19 (Cloud Migration) ✅

### Changed - BREAKING
- **Hashcat moved to Cloud** - GPU cracking now via Nexus → Cloud VPS
- **Evilginx moved to VPS** - AiTM proxy requires dedicated VPS infrastructure
- **Cracking config restructured** - New cloud_enabled, nexus_api_url options

### Removed
- `momo/infrastructure/cracking/hashcat_manager.py` - Moved to Cloud
- `momo/infrastructure/evilginx/` - Entire module moved to VPS
- `momo/apps/momo_plugins/hashcat_cracker.py` - Use Nexus API instead
- `momo/apps/momo_plugins/evilginx_aitm.py` - Use VPS evilginx3
- `momo/apps/momo_web/evilginx_api.py` - Endpoints removed
- `tests/unit/test_evilginx.py` - Tests removed

### Added
- `/api/cracking/cloud/status` - Cloud cracking status endpoint
- `/api/cracking/cloud/submit` - Submit jobs to Cloud (via Nexus)
- Cloud migration notes in CRACKING.md and EVILGINX.md

### Why This Change?
1. **Pi 5 thermal limits** - Hashcat generates too much heat
2. **Battery efficiency** - GPU cracking drains power banks
3. **Performance** - Cloud GPU is 1000x faster than Pi 5
4. **Evilginx requirements** - Needs public IP, ports 80/443, SSL

### Migration Guide
- For cracking: Configure Nexus API URL, submit via `/api/cracking/cloud/submit`
- For Evilginx: Deploy evilginx3 on VPS, use Evil Twin to redirect victims

---

## [1.5.2] - 2025-12-17 (Management Network) ✅

### Added
- **ManagementNetworkManager** - Headless operation support
- **AP Mode** - Creates MoMo-Management hotspot via hostapd
- **Client Mode** - Connects to known WiFi network via nmcli
- **Auto-whitelist** - Management network protected from self-attack
- **Interface isolation** - wlan0 for management, wlan1+ for attacks
- **DHCP server** - dnsmasq integration for AP mode
- **Web binding** - Optional bind to management interface only
- **REST API** - 8 endpoints for management network control
- **26 unit tests** for management network system

### Configuration
```yaml
management:
  enabled: true
  interface: wlan0           # Pi5 internal WiFi
  mode: ap                   # ap or client
  ap_ssid: MoMo-Management
  ap_password: MoMoAdmin2024!
  auto_whitelist: true       # Protect from attacks
  bind_web_to_management: true
```

### Use Case
- Tablet/phone connects to MoMo-Management (192.168.4.x)
- Web UI accessible at 192.168.4.1:8082
- External USB adapters (wlan1+) available for attacks
- Management network automatically whitelisted

---

## [1.5.1] - 2025-12-16 (Hardware Auto-Detection) ✅

### Added
- **DeviceRegistry** - 30+ known USB device database
- **HardwareDetector** - USB scanning via lsusb and /sys/bus/usb
- **Auto-configuration** for WiFi, SDR, Bluetooth, GPS devices
- **Hotplug event system** for device add/remove notifications
- **REST API** - 8 endpoints for hardware management
- **21 unit tests** for hardware detection

### Supported Devices
- **WiFi**: Alfa AWUS036ACH/ACM/ACS/AXML, TP-Link, Panda
- **SDR**: RTL-SDR V3/V4, HackRF One, YARD Stick One
- **Bluetooth**: Sena UD100, ASUS USB-BT500, Plugable
- **GPS**: u-blox NEO-6M/M8N/M9N, GlobalSat BU-353S4

---

## [1.5.0] - 2025-12-15 (SDR Integration) ✅

### Added
- **SDRManager** - RTL-SDR and HackRF device management
- **RTL-SDR V4 support** - HF direct sampling, bias tee
- **SpectrumAnalyzer** - Frequency scanning, peak detection
- **SignalDecoder** - 433/868 MHz IoT signal capture
- **REST API** - SDR control and spectrum endpoints
- **25 unit tests** for SDR functionality

### Features
- RTL-SDR V3/V4 and HackRF One support
- Direct sampling mode for HF reception (V4)
- Bias tee control for active antennas
- Frequency sweep and peak detection
- OOK/FSK signal decoding

---

## [1.3.0] - 2025-12-14 (Advanced Cracking) ✅

### Added
- **JohnManager** - John the Ripper integration
- **Format converter** - hccapx to John format
- **Attack modes** - Wordlist, incremental, mask, rules
- **Potfile management** - Cracked password retrieval
- **REST API** - John the Ripper endpoints
- **15 unit tests** for John manager

---

## [1.2.0] - 2025-12-14 (Bluetooth Expansion) ✅

### Added
- **GATTExplorer** - BLE service/characteristic discovery
- **GATT read/write** - Characteristic value manipulation
- **BeaconSpoofer** - iBeacon and Eddystone frame injection
- **HIDInjector** - Bluetooth keyboard emulation
- **Keystroke injection** - Automated typing attacks
- **DeviceProfiler** - Vulnerability assessment
- **REST API** - GATT, beacon, HID endpoints
- **26 unit tests** for BLE expansion

---

## [1.1.0] - 2025-12-13 (Karma/MANA Attacks) ✅

### Added
- **ProbeMonitor** - Client probe request capture
- **PNL extraction** - Preferred Network List analysis
- **KarmaAttack** - Auto respond to probe requests
- **MANAAttack** - Enhanced with EAP credential capture
- **EAP capture** - PEAP, TTLS, TLS credential harvesting
- **Certificate generation** - Self-signed certs for EAP
- **ClientProfiler** - Device behavior analysis
- **REST API** - Karma/MANA endpoints
- **24 unit tests** for Karma/MANA

---

## [0.10.0] - 2025-12-12 (WPA3/SAE Attack Support) ✅

### Added
- **WPA3Detector** - SAE, Transition Mode, OWE detection
- **PMF detection** - Protected Management Frames status
- **DowngradeAttack** - WPA3 → WPA2 forced downgrade
- **SAEFloodAttack** - DoS via commit frame flooding
- **Attack Recommender** - Optimal attack suggestion
- **REST API** - WPA3 attack endpoints
- **18 unit tests** for WPA3 attacks
- **docs/WPA3.md** - Full documentation

---

## [0.9.0] - 2025-12-12 (Evilginx AiTM) ✅

### Added
- **EvilginxManager** - Binary wrapper for evilginx3
- **PhishletManager** - 5 built-in (M365, Google, Okta, LinkedIn, GitHub)
- **SessionManager** - Cookie capture and multi-format export
- **Lure generation** - Phishing URL creation with tracking
- **Export formats** - JSON, curl, Netscape, raw cookies
- **MockEvilginxManager** - Testing without binary
- **REST API** - Evilginx control endpoints
- **22 unit tests** for Evilginx
- **docs/EVILGINX.md** - Full documentation

---

## [0.8.0] - 2025-12-12 (Plugin Architecture) ✅

### Added
- **BasePlugin** - Abstract plugin base class
- **PluginMetadata** - Version, author, dependencies
- **PluginManager** - Singleton plugin orchestrator
- **Lifecycle hooks** - on_load, on_start, on_tick, on_stop
- **Event-driven** - Inter-plugin communication
- **Example plugins** - wifi_scanner, ble_scanner
- **docs/PLUGINS.md** - Plugin development guide

---

## [0.7.0] - 2025-12-12 (Cracking Integration) ✅

### Added
- **HashcatManager** - GPU-accelerated cracking
- **WordlistManager** - Auto-discovery wordlists
- **Dictionary attack** - Mode 0 with wordlists
- **Brute-force attack** - Mode 3 with masks
- **Progress monitoring** - Real-time status
- **Potfile management** - Cracked password storage
- **REST API** - Cracking control endpoints
- **docs/CRACKING.md** - Full documentation

---

## [0.6.0] - 2025-12-12 (Evil Twin) ✅

### Added
- **APManager** - Rogue AP with hostapd
- **dnsmasq** - DHCP/DNS configuration
- **Captive portal** - aiohttp-based portal
- **6 templates** - generic, hotel, corporate, facebook, google, router
- **Credential harvesting** - POST capture
- **iptables redirect** - Traffic interception
- **REST API** - Evil Twin control endpoints

---

## [0.5.0] - 2025-12-12 (Bluetooth Scanner) ✅

### Added
- **BLEScanner** - Async scanner with bleak
- **iBeacon detection** - UUID, major, minor parsing
- **Eddystone support** - UID, URL, TLM frames
- **Distance estimation** - RSSI-based calculation
- **GPS tagging** - Location correlation
- **REST API** - BLE scanner endpoints
- **Web UI** - Bluetooth device page

---

## [0.4.0] - 2025-12-11 (Handshake Capture) ✅

### Added
- **CaptureManager** - hcxdumptool wrapper
- **PMKID capture** - Clientless WPA2 attack
- **EAPOL capture** - 4-way handshake
- **hcxpcapngtool** - .22000 format conversion
- **CaptureRepository** - SQLite storage
- **REST API** - Capture control endpoints

---

## [0.3.0] - 2025-12-11 (Multi-Radio) ✅

### Added
- **RadioManager** - Multi-interface WiFi management
- **InterfacePool** - Task-based acquire/release
- **5GHz/DFS support** - Full 5GHz band (5170-5825 MHz)
- **Capability detection** - via `iw phy info`
- **Task types** - SCAN, CAPTURE, DEAUTH, MONITOR, INJECT
- **Auto mode switching** - managed ↔ monitor
- **DFS helpers** - `is_dfs_channel()`, `get_non_dfs_5ghz_channels()`
- **Best channel selection** - DFS avoidance algorithm
- **MockRadioManager** - Full mock for testing
- **26 unit tests** for RadioManager

### Fixed
- **WiFiScanner channel hopping** - Now single `iw scan` call
- **Freq parsing** - Handles float frequencies (Debian 12)
- **Device busy handling** - Graceful retry on conflicts

### Tested
- **E2E Wardriving** - 31 APs on Debian VM
- **TP-Link Archer T2U Plus** - RTL8821AU working
- **VirtualBox USB passthrough** - Verified

---

## [0.2.0] - 2025-12-11 (Wardriving & GPS) ✅

### Added
- **AsyncGPSClient** - gpsd integration with auto-reconnect
- **AsyncWardrivingRepository** - aiosqlite non-blocking DB
- **Domain models** - Pydantic validation
- **Event Bus** - Pub/Sub system
- **WiFiScanner** - Async scanning
- **Wardriver plugin** - GPS correlation
- **Wigle.net export** - CSV format
- **GPX export** - Track format
- **SSE endpoint** - `/sse/events` real-time
- **Web UI map** - Leaflet.js `/map`
- **GeoJSON API** - AP and track endpoints
- **DistanceTracker** - Haversine calculation
- **86 async unit tests**

### Changed
- Repository pattern → async-first (aiosqlite)
- `datetime.utcnow()` → `datetime.now(UTC)` (Python 3.12+)

---

## [0.1.0] - 2025-09-07 (Initial Release)

### Added
- Initial scaffold with CLI, config schema, core loop
- Plugin system with priority-based loading
- Pydantic configuration validation
- Flask Web API with token auth and rate limiting
- hcxdumptool integration for capture
- Prometheus metrics endpoint (`/metrics`)
- Health endpoint (`/healthz`)
- Supervisor with auto-restart and backoff
- Storage manager with quota enforcement
- Installers, systemd units, docs, CI, tests

### Security
- Passive mode by default (changed to aggressive in later versions)
- Token-based Web UI authentication
- Rate limiting on all endpoints
