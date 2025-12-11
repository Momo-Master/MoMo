# Roadmap

## Short-term
- Pi 5 + Archer T2U baseline
- Rotating logs
- Passive/semi/aggressive modes
- OLED micro-dashboard
- Plugin import

## Mid-term
- e-Paper integration
- GPS logging
- SDR support
- Multi-adapter hopping
- Dashboard (FastAPI)
 - Prometheus exporter

## Long-term
- Grafana/InfluxDB metrics
- AI-assisted channel dwell optimization
- Distributed nodes
- Cloud sync (opt-in)

## Planning: Multi-adapter support

- Schema: `capture.adapters: [wlan1, wlan2]`
- Round-robin channel hop per adapter, adapter health checks
