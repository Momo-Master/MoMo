# Security

> **Version:** 0.8.0 | **Last Updated:** 2025-12-12

## ⚠️ Legal Disclaimer

MoMo is designed for **authorized security testing and educational purposes only**.

- Only use on networks you own or have explicit permission to test
- Respect local laws and regulations
- The developers are not responsible for misuse

## 🔥 Aggressive Mode (Default)

MoMo is configured for **full offensive capability** by default:

| Feature | Status | Description |
|---------|--------|-------------|
| Passive Scanning | ✅ Always | WiFi/BLE discovery |
| Deauth Attacks | ✅ Enabled | mdk4/aireplay-ng |
| Packet Injection | ✅ Enabled | Frame injection |
| Evil Twin | ✅ Enabled | Rogue AP creation |
| PMKID Capture | ✅ Enabled | Clientless attack |
| Handshake Capture | ✅ Enabled | EAPOL capture |
| Local Cracking | ✅ Enabled | John (local) / Cloud (Hashcat) |

### No Software Restrictions

```yaml
# configs/momo.yml - Aggressive defaults
aggressive:
  enabled: true
  require_ack_env: false      # No confirmation needed
  deauth:
    enabled: true
    max_per_minute: 0         # Unlimited
    burst_limit: 0            # Unlimited
  whitelist: []               # No whitelist
  blacklist: []               # No blacklist
  quiet_hours: null           # No quiet hours
  panic_file: null            # No panic file
```

### Physical Security Note

> **Operator Responsibility:** Physical security measures (location, timing, RF shielding) are the operator's responsibility. Software does not impose limits.

MoMo prioritizes a secure-by-default posture. Aggressive actions are disabled unless explicitly allowed and acknowledged. On first boot, network-facing components are enabled on LAN with a strong token; you can change binds to `127.0.0.1` later.

## SSH Hardening (docs only)

- Disable password login, use keys
- Change default pi user or disable
- Install `ufw` and allow only needed ports
- Install `fail2ban`

### SSH hardening examples

- `/etc/ssh/sshd_config`:
  - `PasswordAuthentication no`
  - `PermitRootLogin prohibit-password`
  - `KexAlgorithms` and `Ciphers` per hardening guides

### UFW LAN restriction snippet

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp
sudo ufw enable
```

## Web UI security

- First boot: enabled and bound to `0.0.0.0:8082` with a strong token persisted at `/opt/momo/.momo_ui_token` and exported via a systemd drop-in (`env.conf`).
- Authentication options (set via environment):
  - Bearer token: `MOMO_UI_TOKEN`
  - Basic auth (username `momo`): `MOMO_UI_PASSWORD`
- Rate limiting: configured via `web.rate_limit` (defaults to `60/minute`).
- Recommendation: for hardened setups, change `server.web.bind_host: 127.0.0.1` and expose via a reverse proxy (Nginx/Caddy) with TLS, or use SSH tunneling.
- Do not store tokens/passwords in git or YAML; pass via systemd environment overrides.

Example systemd override for secrets:

```bash
sudo systemctl edit momo
# In the editor, add:
[Service]
Environment="MOMO_UI_TOKEN=change-me-strong"
```

## Secrets management (plugins and services)

- Pass all API keys (e.g., WPA‑Sec) via systemd drop-ins using `Environment=` lines.
- Never commit secrets to git or place them in `configs/momo.yml`.
- Limit read permissions of `/opt/momo/configs` if you store any sensitive paths.

## Aggressive Features

All aggressive features are **enabled by default** with **no rate limits**:

| Feature | Config Key | Default |
|---------|------------|---------|
| Deauth attacks | `aggressive.deauth.enabled` | `true` |
| Rate limiting | `aggressive.deauth.max_per_minute` | `0` (unlimited) |
| Quiet hours | `aggressive.quiet_hours` | `null` (disabled) |
| Panic file | `aggressive.panic_file` | `null` (disabled) |

## 🎯 Target Selection (Operator Safety)

Protect your own networks while attacking everything else:

| Feature | Purpose | Config Key |
|---------|---------|------------|
| **Blacklist** | NEVER attack these | `aggressive.ssid_blacklist`, `bssid_blacklist` |
| **Whitelist** | ONLY attack these (focus mode) | `aggressive.ssid_whitelist`, `bssid_whitelist` |

### Example Configuration

```yaml
aggressive:
  # Protect your own networks
  ssid_blacklist: ["MyHomeWiFi", "MyOffice5G"]
  bssid_blacklist: ["AA:BB:CC:DD:EE:FF"]
  
  # Or focus on specific targets only
  ssid_whitelist: ["TargetNetwork"]
  bssid_whitelist: []
```

### Logic

1. If target is in **BLACKLIST** → ❌ BLOCK (your network is safe)
2. If **WHITELIST is set** AND target NOT in whitelist → ❌ BLOCK (focus mode)
3. Otherwise → ✅ ATTACK

> **Note:** Empty lists = no restrictions. Blacklist is for protection, whitelist is for focus.

---

## 🛡️ External Threat Protection

### Web API Security

| Protection | Status | Description |
|------------|--------|-------------|
| Token Auth | ✅ | Bearer token required for all endpoints |
| Constant-time compare | ✅ | Prevents timing attacks on token |
| Input validation | ✅ | All user inputs sanitized |
| Rate limiting | ⚠️ | Optional (disabled for aggressive) |
| Local network only | ✅ | Binds to LAN (0.0.0.0) |

### Command Injection Prevention

| Protection | Implementation |
|------------|----------------|
| No `shell=True` | Prefer `subprocess.run(["cmd", "arg"])` |
| No `eval()` | Use `getattr()` instead |
| No `os.system()` | Use `subprocess` with list args |
| Path validation | Prevent directory traversal |

### Security Module

All security functions in `momo/core/security.py`:

```python
from momo.core.security import (
    sanitize_ssid,          # Remove control chars from SSID
    sanitize_bssid,         # Validate MAC address format
    sanitize_path,          # Prevent directory traversal
    sanitize_html,          # Prevent XSS
    sanitize_int,           # Bounds-check integers
    validate_interface_name, # Prevent injection via iface
    validate_channel,       # Valid WiFi channels only
    is_local_request,       # Check if from LAN
    constant_time_compare,  # Timing attack prevention
    is_safe_upload,         # Validate uploaded files
)
```

### Network Security

```yaml
# MoMo binds to local network only
web:
  bind_host: 0.0.0.0    # LAN only (not exposed to internet)
  bind_port: 8082

# For internet exposure, use reverse proxy with TLS:
# nginx → https://momo.local → http://127.0.0.1:8082
```

### Recommendations

1. **Never expose to internet** without reverse proxy + TLS
2. **Change default token** (`MOMO_UI_TOKEN`)
3. **Use SSH key auth** instead of password
4. **Enable firewall** (ufw) on Raspberry Pi
5. **Regular updates** (`apt update && apt upgrade`)

## Logs and data handling

- Default storage quotas: 30 days / 5 GB; automatic pruning enabled.
- Logs are stored under `logs/YYYY-MM-DD/` and may contain sensitive capture data; secure filesystem permissions accordingly.
- Consider moving backups (AutoBackup) to encrypted storage.

## System updates and dependencies

- Keep Debian packages up to date (`apt-get update && apt-get upgrade`).
- Drivers built via DKMS (e.g., rtl8821au) should be rebuilt after kernel updates; verify sources.
- Python dependencies are pinned by the installer; periodically re-run the installer to update.

## Service user and permissions

- Services run as systemd units; by default they may inherit root permissions. For hardened setups, consider running under a dedicated service user and restrict file permissions in `/opt/momo` and `logs/`.
