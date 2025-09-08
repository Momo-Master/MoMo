# Operations

## Services

- `momo.service`: runs `momo run -c /opt/momo/configs/momo.yml`
- `momo-oled.service`: optional OLED status (placeholder)
- `momo-web.service`: optional Web UI (first boot enabled; can bind LAN with token)

## CLI

## Web UI

- First-boot: enabled, binds `0.0.0.0:8082` with a strong token.
- Auth: Bearer via `MOMO_UI_TOKEN` or Basic with username `momo` and password from `MOMO_UI_PASSWORD`.
- Rate limiting: `web.rate_limit` (default `60/minute`).
- Endpoints: `/api/health`, `/api/status`, `/api/rotate`, `/api/handshakes`, `/api/handshakes/<file>`, `/api/metrics` (proxy).
- HTML pages: `/`, `/handshakes`, `/metrics`, `/about`.
- LAN vs localhost: For hardened setups, prefer `127.0.0.1` bind and a reverse proxy/SSH tunnel. MoMo logs warnings for public binds.

## Config resolution order

MoMo resolves configuration in this order (first match wins):

1. `-c/--config` CLI argument
2. `MOMO_CONFIG` environment variable
3. `/etc/momo/momo.yml`
4. `/opt/momo/configs/momo.yml`
5. `configs/momo.yml` (repo default)

Print the chosen path:

```bash
momo config-which -c configs/momo.yml
```

## Server bindings

Configure under `server.*` in `momo.yml` (first-boot defaults expose on LAN with token):

```yaml
server:
  health: { enabled: true, bind_host: 0.0.0.0, port: 8081 }
  metrics: { enabled: true, bind_host: 0.0.0.0, port: 9091 }
  web: { enabled: true, bind_host: 0.0.0.0, port: 8082 }
```

If you change to public binds, consider UFW:

```bash
sudo ufw allow 8081,8082,9091/tcp
```

## Systemd setup

- Virtualenv install uses `deploy/systemd/momo.service`.
- Global install uses `deploy/systemd/momo-global.service`.
- `deploy/setup_systemd.sh` selects the right unit and writes `/etc/momo/momo.yml` and `/etc/default/momo`.

Troubleshooting:

```bash
systemctl status momo
momo doctor
```
- `momo version`
- `momo init <path>`
- `momo config-validate <configs/momo.yml>`
- `momo run -c configs/momo.yml [--health-port 8080] [--dry-run]`
- `momo status -c configs/momo.yml`
- `momo diag -c configs/momo.yml`
- `momo rotate-now -c configs/momo.yml`
### Plugin drop-in workflow

- Copy plugin folders from external sources into `momo/apps/momo_plugins/` (or `_examples/` if unused).
- Ensure each plugin exposes `init(opts)` and optional `shutdown()`.

### Plugin usage examples

- Enable in `configs/momo.yml`:
  - `plugins.enabled: ["autobackup", "wpa-sec"]`
  - `plugins.options.autobackup.*` for adapter configuration
  - Optional per-plugin options: `plugins.options.webcfg.port: 8088`, `plugins.options.wpa_sec.endpoint: "..."`, etc.

### WPA-Sec (opt-in)

- Add `"wpa-sec"` to `plugins.enabled`
- DO NOT put API keys in YAML. Use systemd env overrides:
  - `sudo systemctl edit momo` then:
    - `Environment="WPA_SEC_API_KEY=xxx"`
- Defaults run in `dry_run` until key is provided

### Mini Web Panel (webcfg)

- Default disabled; binds to `127.0.0.1`
- Requires `MOMO_UI_TOKEN` env unless `allow_unauth=true`
- Metrics: `momo_webcfg_requests_total`, `momo_webcfg_active`

### Handshakes Downloader

- `momo handshakes_dl --dest logs/handshakes --since 7d --src logs`

#### AutoBackup quick start

- Drop the original plugin as `momo/apps/momo_plugins/_thirdparty/autobackup_pwn.py` (keep license header)
- Adapter is `momo/apps/momo_plugins/autobackup.py`
- Enable and configure under `plugins.options.autobackup`

## Logs

- Default under `logs/YYYY-MM-DD/`
- `handshakes/*.pcapng` and `*.22000`
- `meta/` for stats JSON (future)

## Health endpoint

- `/healthz` returns basic JSON: `{mode, channel, hs, files, temp}`
- Enabled with `--health-port`

## Prometheus metrics

- `/metrics` exposes Prometheus text format
- Enable with `--prom-port`
- Includes `momo_plugins_enabled` and AutoBackup counters: `momo_autobackup_runs_total`, `momo_autobackup_failures_total`, `momo_autobackup_last_success_timestamp`.

New counters for capture naming:

- `momo_rename_total`
- `momo_rename_skipped_total`
- `momo_convert_skipped_total`

## Rotation

- Automatic based on time/size
- Force rotation: `momo rotate-now -c configs/momo.yml`
- System rotate triggers `SIGUSR1` via logrotate config

## Capture File Naming

- Default template: `{ts}__{ssid}__{bssid}__ch{channel}.pcapng`
- Configure under `capture.naming` in `configs/momo.yml`:
  - `by_ssid: true`
  - `template: "{ts}__{ssid}__{bssid}__ch{channel}"`
  - `max_name_len: 64`
  - `allow_unicode: false` (Windows safe)
  - `whitespace: "_"`
- If multiple networks detected, the dominant one is chosen (hcxpcapngtool info; tshark/scapy optional fallback).
- Hidden/empty SSID becomes `hidden`; if nothing is detected, rename is skipped.
