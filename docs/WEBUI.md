# Minimal Web UI

## Overview

- Static HTML/CSS served at `/`.
- Auth: Bearer token via `MOMO_UI_TOKEN`. Bypass only if explicitly configured elsewhere.
- Uses `/api/metrics-lite` for a compact status JSON.

## Endpoints

- `GET /` — dashboard
- `GET /api/status` — detailed status (auth required)
- `GET /api/metrics-lite` — compact JSON for UI

## Example

```bash
momo web-url --show-token
# then in another terminal
curl -H "Authorization: Bearer $MOMO_UI_TOKEN" http://<host>:8082/api/status
```

## Security

- Default one-shot behavior binds to `0.0.0.0` with a strong token.
- Change to `127.0.0.1` for hardened deployments and place a reverse proxy in front.
