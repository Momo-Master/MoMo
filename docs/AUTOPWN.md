# 🤖 Auto-Pwn Mode

> **Autonomous Attack Engine Documentation**  
> Version: 1.0.0 | Added in MoMo v1.5.0

---

## 📖 Overview

**Auto-Pwn Mode** enables MoMo to autonomously discover, analyze, and attack wireless networks without manual intervention. Perfect for unattended operations, wardriving sessions, or comprehensive site assessments.

### Key Features

| Feature | Description |
|---------|-------------|
| 🎯 **Smart Targeting** | Prioritizes targets by signal, security, and client activity |
| ⛓️ **Attack Chaining** | PMKID → Deauth → Evil Twin automatic fallback |
| 💾 **Session Persistence** | Resume after reboot, save progress |
| 🔋 **Safety Features** | Battery monitoring, duration limits |
| ☁️ **Cloud Integration** | Auto-sync to Nexus for cracking |

---

## 🚀 Quick Start

### Enable Auto-Pwn

```yaml
# configs/momo.yml
autopwn:
  enabled: true
  mode: balanced              # passive, balanced, aggressive
```

### Start via OLED Menu

Navigate to: **Main Menu → 🤖 Auto-Pwn → ▶ Start**

### Start via CLI

```bash
momo run -c configs/momo.yml --autopwn
```

---

## ⚙️ Configuration

```yaml
autopwn:
  enabled: false              # Master enable switch
  mode: balanced              # Attack intensity
  
  # Scanning
  scan_interval: 30           # Seconds between scans
  scan_channels: [1, 6, 11]   # 2.4GHz channels
  scan_5ghz: true             # Include 5GHz
  
  # Targeting
  max_concurrent_attacks: 1   # Parallel attack limit
  min_signal_dbm: -80         # Ignore weak signals
  prefer_wpa2: true           # WPA2 over WPA3
  prefer_with_clients: true   # APs with active clients
  max_attack_attempts: 3      # Per target
  cooldown_seconds: 300       # 5 min retry cooldown
  
  # Attack Types
  enable_pmkid: true          # PMKID grab
  enable_deauth: true         # Deauth + handshake
  enable_eviltwin: false      # Rogue AP (needs 2nd iface)
  attack_timeout: 120         # Per attack timeout
  
  # Cracking
  enable_local_crack: true    # John the Ripper
  enable_cloud_crack: false   # Send to Nexus
  
  # Safety
  stop_on_low_battery: 20     # Stop at 20%
  max_session_duration: 0     # 0 = unlimited
  
  # Session
  session_dir: logs/autopwn
  auto_save_interval: 30
```

---

## 🎯 Attack Modes

| Mode | Behavior |
|------|----------|
| `passive` | Scan only, no attacks |
| `balanced` | Smart targeting, avoid detection |
| `aggressive` | Maximum speed, all techniques |

---

## ⛓️ Attack Chain

```
┌─────────────┐
│   Target    │
│  Discovered │
└──────┬──────┘
       │
       ▼
┌─────────────┐     Success    ┌─────────────┐
│  1. PMKID   │ ──────────────▶│   Capture   │
│   Attack    │                │  Complete   │
└──────┬──────┘                └─────────────┘
       │ Fail
       ▼
┌─────────────┐     Success    ┌─────────────┐
│  2. Deauth  │ ──────────────▶│   Capture   │
│ + Handshake │                │  Complete   │
└──────┬──────┘                └─────────────┘
       │ Fail
       ▼
┌─────────────┐     Success    ┌─────────────┐
│ 3. Evil Twin│ ──────────────▶│ Credential  │
│  (optional) │                │  Captured   │
└──────┬──────┘                └─────────────┘
       │ Fail
       ▼
┌─────────────┐
│  Cooldown   │
│  & Retry    │
└─────────────┘
```

---

## 📊 OLED Menu

```
┌────────────────────────┐
│ 🤖 Auto-Pwn            │
├────────────────────────┤
│ State: RUNNING         │
│ Mode: [Aggressive ▼]   │
│ ────────────────────── │
│ ▶ Start                │
│ ⏸ Pause                │
│ ■ Stop                 │
│ ────────────────────── │
│ Targets: 12            │
│ Captured: 5            │
│ Cracked: 2             │
└────────────────────────┘
```

---

## 🔒 Safety Features

| Feature | Description |
|---------|-------------|
| **Battery Monitor** | Stops at configurable threshold |
| **Duration Limit** | Max session time |
| **Whitelist** | Never attack your own networks |
| **Cooldown** | Prevent repeated attacks |
| **Session Save** | Auto-save every 30s |

---

<p align="center">
  <strong>Part of the 🔥 MoMo Ecosystem</strong>
</p>

