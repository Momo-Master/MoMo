# 📡 WiFi Attack Techniques

> **Comprehensive WiFi Security Testing Guide**  
> MoMo Wireless Attack Documentation

---

## 📖 Overview

MoMo provides a full suite of WiFi attack capabilities for penetration testing and security research.

---

## ⚔️ Attack Types

### 1. Passive Reconnaissance

| Technique | Description | Tool |
|-----------|-------------|------|
| **Wardriving** | GPS-correlated AP scanning | `wardriver` plugin |
| **Channel Hopping** | Multi-channel monitoring | `RadioManager` |
| **Client Detection** | Identify connected devices | `Scanner` |

### 2. WPA2 Attacks

| Technique | Description | Clients Required |
|-----------|-------------|:----------------:|
| **PMKID Capture** | Clientless RSN attack | ❌ |
| **Deauth + Handshake** | Force reconnection | ✅ |
| **4-Way Handshake** | EAPOL capture | ✅ |

### 3. WPA3 Attacks

| Technique | Description | Status |
|-----------|-------------|:------:|
| **SAE Detection** | Identify WPA3 networks | ✅ |
| **Downgrade Attack** | Force WPA2 fallback | ✅ |
| **PMF Handling** | Management frame protection | ✅ |

### 4. Rogue AP Attacks

| Technique | Description | Status |
|-----------|-------------|:------:|
| **Evil Twin** | Clone legitimate AP | ✅ |
| **Karma** | Respond to probe requests | ✅ |
| **MANA** | Loud mode + EAP capture | ✅ |
| **Captive Portal** | Credential harvesting | ✅ |

---

## 🔧 Configuration

### Deauth Attacks

```yaml
aggressive:
  deauth:
    enabled: true
    max_per_minute: 0       # 0 = unlimited
    burst_limit: 10
```

### Evil Twin

```yaml
eviltwin:
  enabled: true
  interface: wlan1
  portal_template: generic  # generic, hotel, corporate, facebook, google, router
  channel: 6
```

### Karma/MANA

```yaml
karma:
  enabled: true
  respond_to_all: true
  capture_eap: true
  loud_ssids:
    - eduroam
    - Starbucks
    - attwifi
```

---

## 📊 Portal Templates

| Template | Use Case |
|----------|----------|
| `generic` | Generic WiFi login |
| `hotel` | Hotel WiFi portal |
| `corporate` | Enterprise login |
| `facebook` | Social login |
| `google` | Google sign-in |
| `router` | Router admin page |

---

## 🛡️ Defense Evasion

| Technique | Description |
|-----------|-------------|
| **MAC Randomization** | Change MAC per session |
| **Channel Rotation** | Avoid static monitoring |
| **Burst Limiting** | Reduce detection risk |
| **Quiet Hours** | Time-based restrictions |

---

<p align="center">
  <strong>Part of the 🔥 MoMo Ecosystem</strong>
</p>

