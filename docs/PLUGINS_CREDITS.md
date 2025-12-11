# Plugin Credits & Acknowledgments

MoMo includes adapted plugins from the following open-source projects:

## Sources

### SHUR1K-N/Project-Pwnag0dchi

- **Repository:** [github.com/SHUR1K-N/Project-Pwnag0dchi](https://github.com/SHUR1K-N/Project-Pwnag0dchi)
- **License:** MIT
- **Plugins Adapted:**
  - `auto-tune.py`
  - `bt-tether.py`
  - `gdrivesync.py`
  - `gpio_buttons.py`
  - `memtemp.py`
  - `pisugarx.py`
  - `ups_lite.py`
  - `wigle.py`
  - `wpa-sec.py`

### jayofelony/pwnagotchi (2.9.x)

- **Repository:** [github.com/jayofelony/pwnagotchi](https://github.com/jayofelony/pwnagotchi)
- **License:** GPL-3.0
- **References:** Core architecture patterns, plugin interface design

### evilsocket/pwnagotchi (Original)

- **Repository:** [github.com/evilsocket/pwnagotchi](https://github.com/evilsocket/pwnagotchi)
- **License:** GPL-3.0
- **References:** Original concept and bettercap integration

## MoMo-Native Plugins

The following plugins were developed specifically for MoMo:

| Plugin | Author | Description | Version |
|--------|--------|-------------|---------|
| `wardriver.py` | MoMo Team | GPS-correlated wardriving | 0.2.0 |
| `cracker.py` | MoMo Team | Hashcat/John integration | 0.1.0 |
| `active_wifi.py` | MoMo Team | mdk4/aireplay attacks | 0.1.0 |
| `bettercap.py` | MoMo Team | Bettercap REST integration | 0.1.0 |
| `webcfg.py` | MoMo Team | Web configuration panel | 0.1.0 |

## MoMo Infrastructure Modules

Core infrastructure modules developed for MoMo:

| Module | Author | Description | Version |
|--------|--------|-------------|---------|
| `RadioManager` | MoMo Team | Multi-radio management & task allocation | 0.3.0 |
| `WiFiScanner` | MoMo Team | Async WiFi scanning via iw | 0.2.0 |
| `AsyncGPSClient` | MoMo Team | gpsd async client | 0.2.0 |
| `AsyncWardrivingRepository` | MoMo Team | aiosqlite database | 0.2.0 |
| `EventBus` | MoMo Team | Async pub/sub system | 0.2.0 |
| `DistanceTracker` | MoMo Team | Haversine GPS distance | 0.2.0 |

## License Compliance

Each adapted plugin file retains its original author and license headers. New plugins are released under the MIT license unless otherwise specified.

When contributing plugins:

1. Preserve original copyright/license headers
2. Add your modifications below the original header
3. Document the source in this file

---

*Last updated: December 2025*
