# Security

## Defaults

- Passive mode by default
- No shipped wordlists
- Whitelist/blacklist enforced by config

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

## Aggressive features safety

- Disabled by default with multiple guardrails in `aggressive.*` config:
  - Explicit acknowledgment required via `aggressive.require_ack_env`.
  - Scope control via SSID/BSSID whitelists/blacklists.
  - Rate limits (max deauth/assoc per minute), burst/cooldown windows.
  - Quiet hours to avoid activity during restricted times.
  - Panic file (`aggressive.panic_file`) stops activity; optional RF kill.
- On repeated child failures, the supervisor forces PASSIVE mode.

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
