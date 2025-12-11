# Hardware Requirements & Setup

> **Version:** 0.8.0 | **Last Updated:** 2025-12-12

## Supported Platforms

| Component | Recommended | Notes |
|-----------|-------------|-------|
| **SBC** | Raspberry Pi 5 (8GB) | Primary target, Pi 4 may work with limitations |
| **OS** | Raspberry Pi OS Bookworm (64-bit) | Debian 12 based, kernel 6.1+ |
| **Python** | 3.11+ | Required for match-case, walrus operator |

## WiFi Adapters

### Verified Working ✅

| Adapter | Chipset | Monitor | Injection | 2.4GHz | 5GHz | Test Date |
|---------|---------|---------|-----------|--------|------|-----------|
| **TP-Link Archer T2U Plus** | RTL8821AU | ✅ | ✅ | 14 ch | 44 ch | 2025-12-11 |
| Alfa AWUS036ACH | RTL8812AU | ✅ | ✅ | ✅ | ✅ | - |
| Alfa AWUS036ACM | MT7612U | ✅ | ✅ | ✅ | ✅ | - |
| Panda PAU09 | RT5572 | ✅ | ✅ | ✅ | ❌ | - |

### Test Results (TP-Link Archer T2U Plus)

```
Environment: Debian 12 (VirtualBox VM)
Driver: aircrack-ng/rtl8812au (DKMS)
Interface: wlxec750c53353a

Capabilities:
  - 2.4GHz channels: 1-14 (14 total)
  - 5GHz channels: 15-177 (44 total, includes DFS)
  - Monitor mode: ✅
  - Packet injection: ✅

Performance:
  - APs found: 31 (mixed 2.4/5GHz environment)
  - Scan time: ~3 seconds
  - Signal range: -90dBm to -37dBm
```

### Driver Installation

```bash
# RTL8812AU (Archer T2U Plus, AWUS036ACH)
sudo apt update
sudo apt install -y dkms git bc
git clone https://github.com/aircrack-ng/rtl8812au.git
cd rtl8812au
sudo make dkms_install

# Verify
sudo iw dev wlan1 info
sudo iw phy phy1 info | grep -i monitor
```

## GPS Modules

### Recommended

| Module | Interface | Notes |
|--------|-----------|-------|
| u-blox NEO-6M | USB/UART | Cheap, reliable, gpsd compatible |
| u-blox NEO-M8N | USB/UART | Better accuracy, faster fix |
| GlobalSat BU-353S4 | USB | Plug-and-play, SiRF Star IV |

### GPS Setup

```bash
# Install gpsd
sudo apt install -y gpsd gpsd-clients

# Configure (USB GPS example)
sudo nano /etc/default/gpsd
# Set: DEVICES="/dev/ttyUSB0" or "/dev/ttyACM0"
# Set: GPSD_OPTIONS="-n"

# Start and enable
sudo systemctl enable gpsd
sudo systemctl start gpsd

# Test
gpsmon
cgps -s
```

## OLED Display (Optional)

| Display | Controller | Interface | Resolution |
|---------|------------|-----------|------------|
| 0.96" OLED | SSD1306 | I²C | 128x64 |
| 1.3" OLED | SH1106 | I²C | 128x64 |

### I²C Setup

```bash
# Enable I²C
sudo raspi-config
# -> Interface Options -> I2C -> Enable

# Verify
sudo i2cdetect -y 1
# Should show device at 0x3C

# Install Python library
pip install luma.oled
```

## Power Considerations

### Recommended Setup

- **Power Supply:** Official Pi 5 27W USB-C PSU
- **For Multiple Adapters:** Powered USB 3.0 Hub (5V/3A minimum)
- **Portable:** PiSugar 3 Plus (5000mAh) or similar

### Power Budget

| Component | Typical Draw |
|-----------|--------------|
| Pi 5 (idle) | ~3W |
| Pi 5 (load) | ~8W |
| WiFi Adapter | 0.5-2W |
| GPS Module | 0.1-0.3W |
| OLED Display | 0.05W |

## Thermal Management

```bash
# Check temperature
vcgencmd measure_temp

# Install monitoring
sudo apt install -y lm-sensors
sensors
```

### Recommendations

- Use heatsinks on Pi 5 (included in most kits)
- Active cooling (fan) for sustained operation
- Throttling starts at 80°C, shutdown at 85°C
- MoMo monitors temperature via `psutil` and exposes metrics

## Storage

### Recommended

- **Boot:** 32GB+ Class 10 microSD (A2 rated preferred)
- **Data:** External SSD via USB 3.0 (for long sessions)

### Storage Quotas

MoMo enforces storage limits by default:

```yaml
storage:
  quota:
    max_days: 30
    max_size_gb: 5
  prune_on_boot: true
```

## Complete Build Example

```
┌─────────────────────────────────────┐
│         Raspberry Pi 5 8GB          │
│                                     │
│  ┌─────────┐  ┌─────────┐          │
│  │ USB-C   │  │ USB 3.0 │──► WiFi  │
│  │ Power   │  │   Hub   │    Adapter
│  └─────────┘  └─────────┘          │
│                    │               │
│               ┌────┴────┐          │
│               │ USB GPS │          │
│               └─────────┘          │
│                                     │
│  ┌─────────┐                       │
│  │ I²C     │──► OLED Display       │
│  │ GPIO    │                       │
│  └─────────┘                       │
└─────────────────────────────────────┘
```

## Troubleshooting

### WiFi Adapter Not Detected

```bash
# Check USB devices
lsusb

# Check kernel messages
dmesg | grep -i wifi

# Reload driver
sudo modprobe -r 88XXau
sudo modprobe 88XXau
```

### GPS No Fix

```bash
# Check device
ls -la /dev/ttyUSB* /dev/ttyACM*

# Check gpsd
systemctl status gpsd
gpspipe -r

# Cold start may take 1-5 minutes for first fix
```

### I²C Device Not Found

```bash
# Check I²C enabled
sudo raspi-config nonint get_i2c

# Check wiring (SDA=GPIO2, SCL=GPIO3)
# Check address with i2cdetect
```
