# Password Cracking Integration

> **Version:** 1.0.0 | **Last Updated:** 2025-12-19

---

## ⚠️ IMPORTANT: GPU Cracking Moved to Cloud

**As of v1.0.0, GPU-based Hashcat cracking has been moved to Cloud infrastructure.**

### Why?
- **Pi 5 thermal limits**: GPU-level cracking generates too much heat
- **Battery drain**: Heavy cracking drains mobile power banks quickly
- **Efficiency**: Cloud GPU VPS cracks 100-1000x faster than Pi 5

### New Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CRACKING ARCHITECTURE v2.0                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  MoMo (Pi 5)                 Nexus (Pi 4)              Cloud VPS    │
│  ───────────                 ───────────               ─────────    │
│  • Capture handshake  ───►  • Route to cloud  ───►  • GPU Hashcat  │
│  • Local John (mini)         • Job management         • rockyou+    │
│  • Convert to .22000         • Result aggregation     • Fast crack  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### What's Available Locally?

| Tool | Use Case | Speed |
|------|----------|-------|
| **John the Ripper** | Quick checks, mini wordlist | ~100 H/s |
| **hcxpcapngtool** | Convert captures to .22000 | Instant |

### Cloud Cracking via Nexus

```bash
# Submit to cloud (via Nexus API)
curl -X POST http://nexus:8080/api/cracking/submit \
  -d '{"hash_file": "handshake.22000", "wordlist": "rockyou"}'

# Check status
curl http://nexus:8080/api/cracking/jobs/<job_id>

# Get result
curl http://nexus:8080/api/cracking/results/<job_id>
```

---

## Local Cracking (John the Ripper)

For quick local checks, use John with mini wordlists only:

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cracking/status` | GET | Overall status + cloud note |
| `/api/cracking/john/status` | GET | John status |
| `/api/cracking/john/jobs` | GET/POST | List/start John jobs |
| `/api/cracking/john/jobs/<id>` | GET/DELETE | Get/stop job |
| `/api/cracking/cloud/status` | GET | Cloud cracking status |

### Start Local John Job

```bash
curl -X POST http://localhost:8080/api/cracking/john/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "hash_file": "logs/handshakes/capture.22000",
    "mode": "wordlist",
    "wordlist": "configs/wordlists/rockyou-mini.txt"
  }'
```

### Configuration

```yaml
# momo.yml
cracking:
  enabled: true               # Enable local cracking
  use_john: true              # Use John the Ripper
  john_path: john             # Path to john binary
  max_runtime_seconds: 300    # 5 min max (prevent battery drain)
  handshakes_dir: logs/handshakes
  potfile: logs/john.pot
  
  # Cloud settings (via Nexus)
  cloud_enabled: false        # Enable when Nexus is configured
  nexus_api_url: ""           # Nexus API URL
```

---

## Wordlist Management

Local wordlists should be SMALL for Pi 5:

| Wordlist | Size | Words | Purpose |
|----------|------|-------|---------|
| rockyou-mini.txt | 500KB | 10K | Quick check |
| wifi-common.txt | 100KB | 5K | WiFi-specific |
| numeric-8.txt | 50KB | 1K | 8-digit patterns |

For full wordlists (rockyou.txt 14M+), use Cloud!

---

## Cloud GPU VPS Setup

### Requirements

- Ubuntu VPS with NVIDIA GPU ($0.50-2/hour)
- Hashcat installed
- API endpoint for job submission

### Recommended Providers

- **Vast.ai** - Cheapest, community GPUs
- **RunPod** - Reliable, instant
- **Lambda Labs** - Professional, A100s

### Performance Comparison

| Platform | Hash Rate | Cost/Hour | WPA2 Crack Time |
|----------|-----------|-----------|-----------------|
| Pi 5 (CPU) | ~50 H/s | Free | Weeks |
| Pi 5 (John) | ~100 H/s | Free | Weeks |
| Cloud A10 | ~500K H/s | $0.50 | Minutes |
| Cloud A100 | ~2M H/s | $2.00 | Seconds |

---

## Migration Notes

### Removed from MoMo

- `momo/infrastructure/cracking/hashcat_manager.py`
- `momo/apps/momo_plugins/hashcat_cracker.py`
- Hashcat-specific config options

### Still Available

- `momo/infrastructure/cracking/john_manager.py`
- `momo/infrastructure/cracking/wordlist_manager.py`
- `/api/cracking/john/*` endpoints

### Future (via Nexus)

- `/api/cracking/cloud/*` endpoints
- Automatic handshake sync to cloud
- Result notification via WebSocket/LoRa

---

## Troubleshooting

### "Hashcat not found"

Hashcat is no longer used locally. Use John or Cloud.

### "John too slow"

Expected on Pi 5. Use mini wordlists or submit to Cloud.

### "Cloud not configured"

1. Deploy Nexus
2. Configure cloud GPU VPS
3. Set `nexus_api_url` in config
4. Enable `cloud_enabled: true`

---

*MoMo v1.6.0 - GPU cracking moved to Cloud*
