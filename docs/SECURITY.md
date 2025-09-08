# Security

## Defaults

- Passive mode by default
- No shipped wordlists
- Whitelist/blacklist enforced by config

## SSH Hardening (docs only)

- Disable password login, use keys
- Change default pi user or disable
- Install `ufw` and allow only needed ports
- Install `fail2ban`

### SSH hardening examples

- `/etc/ssh/sshd_config`:
  - `PasswordAuthentication no`
  - `PermitRootLogin prohibit-password`
  - `KexAlgorithms` and `Ciphers` per hardening guides

### UFW LAN restriction snippet

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp
sudo ufw enable
```

## UI Credentials

- Any UI requires first-run credential change (future dashboard)
