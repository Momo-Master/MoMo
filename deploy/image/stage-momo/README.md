# MoMo Pi-Gen Stage

Custom pi-gen stage for building MoMo Raspberry Pi images.

## Structure

```
stage-momo/
├── 00-install-momo/
│   ├── 00-packages        # APT packages to install
│   └── 01-run-chroot.sh   # Main installation script (runs in chroot)
├── EXPORT_IMAGE           # Flag: export .img.xz after this stage
├── EXPORT_NOOBS           # Flag: also create NOOBS format
└── README.md
```

## What Gets Installed

### System Packages
- Python 3 with venv and pip
- Network tools: hostapd, dnsmasq, iptables, iw, wireless-tools
- GPS: gpsd, gpsd-clients
- Hardware: i2c-tools
- Security tools: aircrack-ng, tcpdump, nmap (if available)

### MoMo
- Cloned to `/opt/momo`
- Virtual environment at `/opt/momo/.venv`
- All optional dependencies: recommended, wardriving, ble, eviltwin, firstboot

### Services
- `momo-firstboot.service` - First boot wizard (enabled)
- `momo.service` - Main MoMo service (enabled after wizard)
- `momo-ap.service` - Management AP (optional)

### Configuration
- `/etc/momo/` - Config directory (empty, wizard creates config)
- `/var/log/momo/` - Log directory
- `/var/lib/momo/` - Data directory

## Build

```bash
cd deploy/image
./make_image.sh --docker
```

Output: `releases/momo-pi5-YYYYMMDD.img.xz`
