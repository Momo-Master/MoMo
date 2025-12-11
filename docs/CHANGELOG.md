# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-12-11 (Multi-Radio) ✅

### Added
- **RadioManager** - Multi-interface WiFi management with task-based allocation
- **InterfacePool** - Integrated into RadioManager with acquire/release pattern
- **5GHz/DFS channel support** - Full 5GHz band (5170-5825 MHz) with DFS detection
- **Adapter capability detection** via `iw phy info` parsing
- **Task types** - SCAN, CAPTURE, DEAUTH, MONITOR, INJECT
- **Auto mode switching** - Automatic managed ↔ monitor based on task type
- **DFS channel helpers** - `is_dfs_channel()`, `get_non_dfs_5ghz_channels()`
- **Best channel selection** - `get_best_channel()` with DFS avoidance
- **MockRadioManager** - Full mock implementation for testing
- **26 new unit tests** for RadioManager

### Fixed
- **WiFiScanner channel hopping bug** - Now uses single `iw scan` call
- **Freq parsing for Debian 12** - Handles float frequencies (`2447.0` → `2447`)
- **Device busy handling** - Graceful retry on scan conflicts

### Tested
- **E2E Wardriving** - 31 APs scanned and saved to SQLite on Debian VM
- **TP-Link Archer T2U Plus** - RTL8821AU driver working with 2.4GHz + 5GHz
- **VirtualBox USB passthrough** - Verified working

---

## [Unreleased] - v0.4.0 (Handshake Capture)

### Planned
- Automatic EAPOL/PMKID capture
- hcxdumptool integration
- Deauth attack module (optional)
- RTL-SDR spectrum analysis
- Automatic interface hot-plug detection
- Priority-based task queuing
- Radio plugin for full orchestration

---

## [0.2.0] - 2025-12-11 (Wardriving & GPS) ✅

### Added
- GPS daemon integration (`infrastructure/gps/gpsd_client.py`)
- Async GPS position streaming with auto-reconnect
- SQLite wardriving database (`infrastructure/database/`)
- Domain models with Pydantic validation (`domain/models.py`)
- Event Bus pub/sub system (`core/events.py`)
- Async WiFi scanner (`infrastructure/wifi/scanner.py`)
- Wardriver plugin with GPS correlation
- Wigle.net CSV export
- GPX track export
- Mock GPS/WiFi clients for testing
- **AsyncWardrivingRepository** using `aiosqlite` (non-blocking I/O)
- **SSE real-time endpoint** (`/sse/events`)
- **Web UI map view** with Leaflet.js (`/map`)
- **GeoJSON API** (`/api/wardriver/aps.geojson`, `/api/wardriver/track.geojson`)
- **DistanceTracker** for GPS distance calculation
- Comprehensive async unit tests (86 tests passing)

### Changed
- Repository pattern → async-first with `aiosqlite`
- `datetime.utcnow()` → `datetime.now(UTC)` (Python 3.12+ compat)
- Updated `pyproject.toml` with `aiosqlite`, `pytest-asyncio`
- Fixture decorator: `@pytest.fixture` → `@pytest_asyncio.fixture`

### Fixed
- Deprecation warnings for datetime in async repository

## [0.1.0] - 2025-09-07

### Added
- Initial scaffold with CLI, config schema, core loop, utils
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
- Passive mode by default
- Aggressive features require explicit acknowledgment
- Token-based Web UI authentication
- Rate limiting on all endpoints
