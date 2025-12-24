# MoMo Pi-Gen Stage

This is a custom pi-gen stage that creates a ready-to-use MoMo image.

## What it does

1. **System Packages** - Installs all required dependencies (hostapd, dnsmasq, aircrack-ng, etc.)
2. **MoMo Installation** - Clones repo, creates venv, installs with all extras
3. **Hardware Setup** - Enables I2C, SPI for OLED and sensors
4. **Systemd Services** - Installs and enables momo-firstboot service
5. **Network Config** - Prepares hostapd/dnsmasq for First Boot Wizard
6. **User Setup** - Creates `momo` system user with correct permissions

## Files

| File | Purpose |
|------|---------|
| `00-run.sh` | Host-side script (file copies) |
| `00-run-chroot.sh` | Chroot script (main installation) |
| `01-packages` | Additional apt packages |

## First Boot Flow

1. Image flashed to SD card
2. Pi boots for first time
3. `momo-firstboot.service` starts
4. WiFi AP "MoMo-Setup" created
5. User connects and completes wizard
6. Main MoMo services enabled and started
7. Device ready for use

## Build

```bash
cd deploy/image
./make_image.sh --docker
```

## Output

- `releases/momo-pi5-YYYYMMDD.img.xz` - Compressed image
- `releases/momo-pi5-YYYYMMDD.img.xz.sha256` - Checksum

## Customization

Edit `00-run-chroot.sh` to:
- Change default WiFi credentials
- Add custom packages
- Modify default configuration
- Pre-configure Nexus connection
