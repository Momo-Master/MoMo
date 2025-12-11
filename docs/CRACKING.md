# Password Cracking Integration

> **Version:** 0.7.0 | **Last Updated:** 2025-12-12

MoMo includes full hashcat integration for WPA/WPA2 password cracking.

⚠️ **WARNING:** Only crack handshakes you obtained legally and ethically.

## Table of Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Web UI](#web-ui)
- [API Endpoints](#api-endpoints)
- [Wordlist Management](#wordlist-management)
- [Attack Modes](#attack-modes)
- [CLI Usage](#cli-usage)

---

## Overview

The cracking system supports:

| Feature | Description |
|---------|-------------|
| **Hash Mode 22000** | WPA-PBKDF2-PMKID+EAPOL (modern format) |
| **Dictionary Attack** | Wordlist-based cracking |
| **Brute-force Attack** | Mask-based cracking |
| **Rule-based Attack** | Wordlist + rules |
| **Auto-crack** | Automatically crack new handshakes |
| **Progress Tracking** | Real-time speed and ETA |
| **Potfile** | Remember cracked passwords |

### Architecture

```
┌─────────────────────────────────────────────────┐
│                 HashcatManager                   │
├─────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐              │
│  │ CrackJob    │  │ WordlistMgr │              │
│  │ - status    │  │ - scan()    │              │
│  │ - progress  │  │ - get_best()│              │
│  │ - results   │  │ - add()     │              │
│  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────┘
```

---

## Configuration

### momo.yml

```yaml
cracking:
  enabled: true               # Enable cracking
  auto_crack: false           # Auto-crack new handshakes
  workload_profile: 3         # 1=low, 2=default, 3=high, 4=nightmare
  max_runtime_seconds: 0      # 0 = unlimited
  check_interval: 60          # Seconds between auto-crack checks
  handshakes_dir: logs/handshakes
  potfile: logs/hashcat.potfile
```

### Workload Profiles

| Profile | Name | Description |
|---------|------|-------------|
| 1 | Low | Desktop use, minimal GPU impact |
| 2 | Default | Balanced |
| 3 | High | Dedicated cracking, some lag |
| 4 | Nightmare | Full GPU, system may be unusable |

---

## Web UI

Access the cracking interface at `http://<ip>:8080/cracking`

### Features

- **Job Submission:** Select hash file, wordlist, attack mode
- **Progress Display:** Real-time progress, speed, ETA
- **Cracked Passwords:** View all recovered passwords
- **Wordlist Selection:** Choose from available wordlists

### Screenshot

```
┌─────────────────────────────────────────────────────────────┐
│  🔓 Password Cracking                                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │    5    │ │    3    │ │    1    │ │    2    │           │
│  │  Total  │ │ Cracked │ │ Active  │ │Wordlists│           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │ 🚀 Start Job       │  │ 🔑 Cracked         │            │
│  │ Hash file: [____]  │  │ password123 (5.2s) │            │
│  │ Wordlist:  [▼___]  │  │ secret!@#  (12.1s) │            │
│  │ [Start Cracking]   │  │ qwerty2024 (3.8s)  │            │
│  └────────────────────┘  └────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cracking/status` | GET | Plugin status |
| `/api/cracking/jobs` | GET | List all jobs |
| `/api/cracking/jobs` | POST | Start new job |
| `/api/cracking/jobs/<id>` | DELETE | Stop job |
| `/api/cracking/cracked` | GET | List cracked passwords |
| `/api/cracking/wordlists` | GET | List available wordlists |
| `/api/cracking/stats` | GET | Cracking statistics |

### Start a Job

```bash
curl -X POST http://localhost:8080/api/cracking/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "hash_file": "logs/handshakes/capture.22000",
    "wordlist": "/usr/share/wordlists/rockyou.txt",
    "attack_mode": 0
  }'
```

### Response

```json
{
  "ok": true,
  "job_id": "abc123",
  "hash_file": "logs/handshakes/capture.22000",
  "wordlist": "/usr/share/wordlists/rockyou.txt",
  "attack_mode": 0
}
```

---

## Wordlist Management

### Automatic Discovery

WordlistManager scans common paths:

```
/usr/share/wordlists/
/usr/share/dict/
/opt/wordlists/
~/.wordlists/
./wordlists/
```

### Common Wordlists

| Name | Words | Description |
|------|-------|-------------|
| rockyou.txt | 14M | Classic password list |
| rockyou2024.txt | 10B+ | Massive updated list |
| common-passwords.txt | 10K | Most common passwords |
| wifi-passwords.txt | 1M | WiFi-specific passwords |

### Install rockyou.txt

```bash
# Debian/Ubuntu
sudo apt install wordlists
sudo gunzip /usr/share/wordlists/rockyou.txt.gz

# Kali Linux
# Already available at /usr/share/wordlists/rockyou.txt
```

---

## Attack Modes

### Dictionary Attack (mode 0)

Uses a wordlist to try passwords:

```bash
# Via API
{
  "attack_mode": 0,
  "wordlist": "/usr/share/wordlists/rockyou.txt"
}
```

### Brute-force Attack (mode 3)

Uses masks for pattern-based attacks:

```bash
# Via API
{
  "attack_mode": 3,
  "mask": "?d?d?d?d?d?d?d?d"  # 8 digits
}
```

### Mask Characters

| Char | Meaning |
|------|---------|
| `?d` | Digit (0-9) |
| `?l` | Lowercase (a-z) |
| `?u` | Uppercase (A-Z) |
| `?s` | Special (!@#$...) |
| `?a` | All printable |

### Examples

| Mask | Pattern | Example |
|------|---------|---------|
| `?d?d?d?d?d?d?d?d` | 8 digits | 12345678 |
| `?u?l?l?l?l?l?d?d` | Word + 2 digits | Password12 |
| `?d?d?d?d?d?d?d?d?d?d` | Phone number | 5551234567 |

---

## CLI Usage

### Convert Capture to Hash

```bash
# Convert pcapng to 22000 format
hcxpcapngtool -o output.22000 input.pcapng

# View hash info
cat output.22000
```

### Manual hashcat

```bash
# Dictionary attack
hashcat -m 22000 -a 0 capture.22000 rockyou.txt

# Brute-force (8 digits)
hashcat -m 22000 -a 3 capture.22000 ?d?d?d?d?d?d?d?d

# Show cracked
hashcat -m 22000 capture.22000 --show
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `momo_crack_jobs_total` | Total jobs started |
| `momo_crack_jobs_cracked` | Successful cracks |
| `momo_crack_jobs_exhausted` | Wordlist exhausted |
| `momo_crack_passwords_found` | Passwords recovered |
| `momo_crack_active_jobs` | Currently running |
| `momo_crack_errors_total` | Errors encountered |

---

## Requirements

### Install hashcat

```bash
# Debian/Ubuntu
sudo apt install hashcat

# Verify
hashcat --version
```

### GPU Support

For GPU acceleration:

```bash
# NVIDIA
sudo apt install nvidia-driver nvidia-cuda-toolkit

# AMD
sudo apt install rocm-opencl-runtime
```

---

## Troubleshooting

### hashcat not found

```bash
# Check if installed
which hashcat

# Install
sudo apt install hashcat
```

### No GPU detected

```bash
# Check OpenCL devices
hashcat -I

# Force CPU
hashcat -m 22000 -a 0 -D 1 ...
```

### Potfile issues

```bash
# Clear potfile
rm logs/hashcat.potfile

# Or disable potfile check
hashcat --potfile-disable ...
```
