# MoMo Development Roadmap

> **Version:** 1.3.0 | **Last Updated:** 2025-12-12

## 🎯 Vision

MoMo - The ultimate open-source wireless security audit platform combining the best of Pwnagotchi, ESP32 Marauder, and WiFi Pineapple.

---

## ✅ Completed Phases

### Phase 0.1.0 - Core Infrastructure ✅
- [x] Clean Architecture (4-layer separation)
- [x] Async-first design with asyncio
- [x] Pydantic configuration system
- [x] Event-driven pub/sub system
- [x] CLI with Typer
- [x] Logging with rotation

### Phase 0.2.0 - Wardriving & GPS ✅
- [x] GPS client (gpsd integration)
- [x] Async SQLite repository
- [x] AP/Client models with Pydantic
- [x] GeoJSON export
- [x] Distance tracking
- [x] Wardriver plugin

### Phase 0.3.0 - Multi-Radio Management ✅
- [x] RadioManager for multiple adapters
- [x] Channel hopping (2.4GHz + 5GHz)
- [x] Monitor mode management
- [x] Interface capability detection
- [x] Task-based allocation

### Phase 0.4.0 - Handshake Capture ✅
- [x] CaptureManager with hcxdumptool
- [x] PMKID capture (clientless)
- [x] EAPOL 4-way handshake
- [x] hcxpcapngtool integration (.22000 format)
- [x] Capture repository (SQLite)
- [x] Capture plugin

### Phase 0.5.0 - Bluetooth Scanner ✅
- [x] BLE scanner with bleak
- [x] iBeacon detection & parsing
- [x] Eddystone (UID, URL, TLM) support
- [x] Distance estimation
- [x] BLE plugin with GPS tagging
- [x] BLE API endpoints
- [x] Bluetooth Web UI page

### Phase 0.6.0 - Evil Twin ✅
- [x] APManager with hostapd
- [x] dnsmasq DHCP/DNS
- [x] Captive portal (aiohttp)
- [x] 6 portal templates (generic, hotel, corporate, facebook, google, router)
- [x] Credential harvesting
- [x] iptables redirect
- [x] Evil Twin plugin
- [x] Evil Twin API & Web UI

### Phase 0.7.0 - Cracking Integration ✅
- [x] HashcatManager
- [x] WordlistManager with auto-discovery
- [x] Dictionary attack (mode 0)
- [x] Brute-force attack (mode 3)
- [x] Progress monitoring
- [x] Potfile management
- [x] Cracker plugin with auto-crack
- [x] Cracking API & Web UI

### Phase 0.8.0 - Plugin Architecture ✅
- [x] BasePlugin abstract class
- [x] PluginMetadata (version, dependencies)
- [x] PluginManager singleton
- [x] Lifecycle hooks (on_load, on_start, on_stop)
- [x] Event-driven communication
- [x] Dependency injection
- [x] Example plugins (wifi_scanner, ble_scanner)
- [x] Comprehensive documentation

### Phase 0.9.0 - Evilginx AiTM Integration ✅
- [x] EvilginxManager (binary wrapper)
- [x] PhishletManager (5 built-in: M365, Google, Okta, LinkedIn, GitHub)
- [x] SessionManager (cookie storage & export)
- [x] Lure generation (phishing URLs)
- [x] Multiple export formats (JSON, curl, Netscape)
- [x] MockEvilginxManager for testing
- [x] Evilginx plugin
- [x] Evilginx API & Web integration
- [x] 22 unit tests

---

### Phase 0.10.0 - WPA3/SAE Attack Support ✅
- [x] WPA3 detection (SAE, Transition Mode, OWE)
- [x] PMF (Protected Management Frames) status detection
- [x] Transition mode downgrade attack (WPA3 → WPA2)
- [x] SAE flood attack (DoS)
- [x] Attack recommendation engine
- [x] WPA3 plugin and REST API
- [x] Unit tests (18 tests)
- [x] Documentation

---

## 📅 Planned Phases

### Phase 1.0.0 - Real Hardware & Production
- [ ] Raspberry Pi 5 deployment
- [ ] Multi-adapter stress testing
- [ ] GPS accuracy validation
- [ ] Thermal management tuning
- [ ] Stability testing (72h+ continuous)
- [ ] Performance optimization
- [ ] Full documentation review

### Phase 1.1.0 - Advanced Attacks ✅
- [x] WPA3 support (SAE) ← Moved to 0.10.0
- [x] Enterprise attack (EAP) - MANA PEAP/TTLS/TLS capture
- [x] Karma attack - Auto respond to probe requests
- [x] MANA attack - Enhanced with EAP support
- [x] Client probing analysis - PNL extraction
- [x] Certificate generation for EAP
- [x] 24 unit tests

### Phase 1.2.0 - Bluetooth Expansion ✅
- [x] BLE GATT exploration - Service/Characteristic discovery
- [x] GATT Read/Write support
- [x] HID injection - Bluetooth keyboard emulation
- [x] BLE replay attacks - Characteristic writing
- [x] Beacon spoofing - iBeacon/Eddystone
- [x] 26 unit tests

### Phase 1.3.0 - Advanced Cracking ✅
- [x] John the Ripper integration
- [x] hccapx to John format converter
- [x] Multiple attack modes (wordlist, incremental, mask, rules)
- [x] Show cracked passwords from potfile
- [x] 15 unit tests
- [ ] Cloud cracking (AWS/GCP) - Future
- [ ] Distributed cracking - Future

### Phase 1.4.0 - OLED & Display
- [ ] SSD1306/SH1106 support
- [ ] Custom faces/animations
- [ ] Status display modes
- [ ] Touch button support
- [ ] e-Paper display option

### Phase 1.5.0 - SDR Integration ✅
- [x] RTL-SDR and HackRF device management
- [x] Spectrum analyzer (frequency scanning)
- [x] Signal decoder (433/868 MHz IoT)
- [x] REST API endpoints
- [x] 22 unit tests

### Phase 1.6.0 - Mobile App
- [ ] React Native app
- [ ] Real-time sync
- [ ] Push notifications
- [ ] Remote control
- [ ] Offline mode

### Phase 2.0.0 - Mesh Networking
- [ ] Multi-device coordination
- [ ] Distributed scanning
- [ ] Result aggregation
- [ ] Leader election
- [ ] Secure communication

---

## 🔮 Future Ideas

### Hardware Support
- [ ] ESP32 co-processor
- [ ] SDR integration (HackRF)
- [ ] LoRa communication
- [ ] Cellular modem (4G/5G)
- [ ] Custom PCB design

### Analysis & AI
- [ ] ML-based AP classification
- [ ] Anomaly detection
- [ ] Client behavior analysis
- [ ] Predictive targeting
- [ ] Auto-optimization

### Integration
- [ ] Wigle.net upload
- [ ] WPA-sec integration
- [ ] Hashcat.net cloud
- [ ] Slack/Discord alerts
- [ ] SIEM integration

### Security Research
- [ ] 802.11ax (WiFi 6) attacks
- [ ] WPA3 research
- [ ] IoT protocol analysis
- [ ] Zigbee/Z-Wave scanning
- [ ] RFID/NFC support

---

## 📊 Metrics & Goals

### Performance Targets
| Metric | Current | Target |
|--------|---------|--------|
| Startup time | ~3s | <2s |
| Memory usage | ~150MB | <100MB |
| CPU idle | ~5% | <3% |
| Scan interval | 5s | 2s |
| Handshake capture | 90% | 99% |

### Test Coverage
| Component | Current | Target |
|-----------|---------|--------|
| Unit tests | 65+ | 100+ |
| Integration | 10+ | 30+ |
| E2E tests | 0 | 10+ |
| Coverage | ~60% | 80%+ |

---

## 🤝 Contributing

Want to help? Check:
1. [GitHub Issues](https://github.com/Momo-Master/MoMo/issues)
2. [PLUGINS.md](PLUGINS.md) - Create plugins
3. [OPERATIONS.md](OPERATIONS.md) - Improve docs

Priority areas:
- Real hardware testing
- Plugin development
- Documentation
- Bug fixes

---

## 📜 Changelog Summary

| Version | Date | Highlights |
|---------|------|------------|
| 0.8.0 | 2025-12-12 | Plugin architecture, docs update |
| 0.7.0 | 2025-12-12 | Hashcat cracking integration |
| 0.6.0 | 2025-12-12 | Evil Twin with captive portal |
| 0.5.0 | 2025-12-12 | BLE scanner with beacon detection |
| 0.4.0 | 2025-12-11 | Handshake capture system |
| 0.3.0 | 2025-12-10 | Multi-radio management |
| 0.2.0 | 2025-12-09 | Wardriving & GPS |
| 0.1.0 | 2025-12-08 | Core infrastructure |
