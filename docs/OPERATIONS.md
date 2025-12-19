# Operations Guide

> **Version:** 0.8.0 | **Last Updated:** 2025-12-12

## Table of Contents

- [Quick Start](#quick-start)
- [Services](#services)
- [CLI Commands](#cli-commands)
- [Web UI](#web-ui)
- [Configuration](#configuration)
- [Plugin System](#plugin-system)
- [Logging](#logging)
- [Monitoring](#monitoring)
- [Maintenance](#maintenance)

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/Momo-Master/MoMo.git
cd MoMo
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with dry-run (no hardware needed)
momo run -c configs/momo.yml --dry-run
```

---

## Services

MoMo runs as systemd services:

| Service | Description | Default |
|---------|-------------|---------|
| `momo.service` | Core capture loop | Enabled |
| `momo-oled.service` | OLED status display | Optional |
| `momo-web.service` | Web UI & API | Enabled on first boot |

### Service Management

```bash
# Start/Stop
sudo systemctl start momo
sudo systemctl stop momo
sudo systemctl restart momo

# Status and logs
systemctl status momo
journalctl -u momo -f

# Enable on boot
sudo systemctl enable momo
```

### Systemd Setup

```bash
# Automatic setup
./deploy/setup_systemd.sh

# Manual (virtualenv)
sudo cp deploy/systemd/momo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable momo
```

---

## CLI Commands

```bash
# Version and info
momo version
momo doctor

# Configuration
momo config-which                    # Show resolved config path
momo config-validate configs/momo.yml

# Initialize new config
momo init /path/to/new/config

# Run
momo run -c configs/momo.yml
momo run -c configs/momo.yml --dry-run    # Simulate without hardware
momo run -c configs/momo.yml --health-port 8081

# Status
momo status -c configs/momo.yml
momo diag -c configs/momo.yml

# Manual rotation
momo rotate-now -c configs/momo.yml

# Handshakes
momo handshakes_dl --dest logs/handshakes --since 7d --src logs

# Web UI
momo web-url --show-token
```

---

## Web UI

### Overview

- **Default:** Enabled on first boot, binds `0.0.0.0:8082`
- **Authentication:** Bearer token (`MOMO_UI_TOKEN`) or Basic auth
- **Rate Limiting:** Configurable via `web.rate_limit` (default: 60/minute)

### Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /` | No | Dashboard HTML |
| `GET /handshakes` | No | Handshakes list page |
| `GET /metrics` | No | Metrics page |
| `GET /about` | No | About page |
| `GET /api/health` | No | Basic health JSON |
| `GET /api/status` | Yes | Detailed status |
| `GET /api/metrics-lite` | No | Compact metrics JSON |
| `GET /api/handshakes` | Yes | List handshake files |
| `GET /api/handshakes/<file>` | Yes | Download handshake |
| `POST /api/rotate` | Yes | Force log rotation |
| `GET /api/metrics` | No | Prometheus proxy |

### Security Recommendations

```yaml
# Hardened config (127.0.0.1 bind + reverse proxy)
server:
  web:
    enabled: true
    bind_host: 127.0.0.1
    port: 8082
```

```bash
# Access via SSH tunnel
ssh -L 8082:localhost:8082 pi@momo.local
# Then open http://localhost:8082
```

---

## Configuration

### Resolution Order

MoMo resolves config in this order (first match wins):

1. `-c/--config` CLI argument
2. `MOMO_CONFIG` environment variable
3. `/etc/momo/momo.yml`
4. `/opt/momo/configs/momo.yml`
5. `configs/momo.yml` (repo default)

### Server Bindings

```yaml
server:
  health:
    enabled: true
    bind_host: 0.0.0.0
    port: 8081
  metrics:
    enabled: true
    bind_host: 0.0.0.0
    port: 9091
  web:
    enabled: true
    bind_host: 0.0.0.0
    port: 8082
```

### Firewall (UFW)

```bash
sudo ufw allow 8081,8082,9091/tcp
sudo ufw enable
```

---

## Plugin System

MoMo features a modern, Marauder-inspired plugin architecture. See [PLUGINS.md](PLUGINS.md) for full documentation.

### Architecture

- **Modern plugins:** `momo/plugins/` (new architecture)
- **Legacy plugins:** `momo/apps/momo_plugins/` (backward compatible)
- **Loading:** Priority-based (lower = earlier)
- **Lifecycle:** `on_load()` → `on_start()` → `on_tick()` → `on_stop()`
- **Events:** Pub/sub communication between plugins

### Quick Plugin Example

```python
from momo.core import BasePlugin, PluginMetadata, PluginType

class MyPlugin(BasePlugin):
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            plugin_type=PluginType.CUSTOM,
        )
    
    async def on_start(self) -> None:
        self.log.info("Started!")
        await self.emit("ready", {})
    
    async def on_stop(self) -> None:
        self.log.info("Stopped!")
```

### Enabling Plugins

```yaml
plugins:
  enabled:
    - wardriver
    - ble_scanner
    - capture
  options:
    wardriver:
      enabled: true
      db_path: "logs/wardriving.db"
    ble_scanner:
      scan_duration: 5.0
    # Note: hashcat_cracker removed in v1.6.0 - use Cloud via Nexus
```

### Available Plugins

| Plugin | Type | Description | Docs |
|--------|------|-------------|------|
| `wardriver` | Scanner | GPS-correlated AP scanning | - |
| `wifi_scanner` | Scanner | WiFi AP/client discovery | - |
| `ble_scanner` | Scanner | BLE device/beacon detection | - |
| `active_wifi` | Attack | Deauth/beacon attacks | [ACTIVE_WIFI.md](ACTIVE_WIFI.md) |
| `evil_twin` | Attack | Rogue AP + captive portal | - |
| `capture` | Capture | Handshake capture | - |

> **Note:** `hashcat_cracker` and `evilginx_aitm` removed in v1.6.0. Use Cloud/VPS.

### Secrets Management

**Never put API keys in config files!**

```bash
# Use systemd environment overrides
sudo systemctl edit momo
# Add:
[Service]
Environment="WPA_SEC_API_KEY=your-api-key"
Environment="MOMO_UI_TOKEN=your-strong-token"
```

---

## Logging

### Structure

```
logs/
├── YYYY-MM-DD/
│   ├── handshakes/
│   │   ├── capture-00001.pcapng
│   │   └── {ts}__{ssid}__{bssid}__ch{channel}.pcapng
│   └── meta/
│       └── stats.json
└── meta/
    ├── momo.pid
    └── stats.json
```

### Capture File Naming

```yaml
capture:
  naming:
    by_ssid: true
    template: "{ts}__{ssid}__{bssid}__ch{channel}"
    max_name_len: 64
    allow_unicode: false
    whitespace: "_"
```

### Log Rotation

```bash
# Manual rotation
momo rotate-now -c configs/momo.yml

# Via signal
kill -USR1 $(cat logs/meta/momo.pid)
```

---

## Monitoring

### Health Endpoint

```bash
curl http://localhost:8081/healthz
# {"mode": "passive", "channel": 6, "hs": 5, "temp": 45.2}
```

### Prometheus Metrics

```bash
curl http://localhost:9091/metrics
```

**Key Metrics:**

| Metric | Description |
|--------|-------------|
| `momo_aps_discovered_total` | Total APs found |
| `momo_handshakes_captured_total` | Handshakes captured |
| `momo_current_channel` | Current WiFi channel |
| `momo_temperature_celsius` | CPU temperature |
| `momo_storage_free_bytes` | Free disk space |
| `momo_plugins_enabled` | Active plugins count |

### Grafana Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'momo'
    static_configs:
      - targets: ['momo.local:9091']
```

---

## Maintenance

### Storage Quotas

```yaml
storage:
  quota:
    max_days: 30
    max_size_gb: 5
  prune_on_boot: true
```

### Manual Cleanup

```bash
# Remove old captures
find logs/ -name "*.pcapng" -mtime +30 -delete

# Check disk usage
du -sh logs/
df -h
```

### Updates

```bash
cd /opt/momo
git pull
pip install -e .[recommended]
sudo systemctl restart momo
```

### Diagnostics

```bash
# Full system check
momo doctor

# Service status
systemctl status momo momo-web

# Hardware check
sudo iw dev
gpsmon
i2cdetect -y 1
```
