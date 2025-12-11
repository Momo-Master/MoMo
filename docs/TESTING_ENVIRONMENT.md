# 🧪 MoMo Test Ortamı Kurulumu

> **Status:** ✅ Verified Working (2025-12-11)

## Mevcut Test Ortamı

| Ortam | OS | Donanım | Durum |
|-------|-----|---------|-------|
| Windows | Win10/11 | - | ✅ Mock tests |
| VM | Debian 12 | RTL8821AU | ✅ Real WiFi |
| Pi | - | - | 🔜 Planned |

### Aktif VM Bağlantısı

```
┌─────────────────────────────────────────────────────┐
│              TEST ORTAMI BİLGİLERİ                   │
├─────────────────────────────────────────────────────┤
│  SSH Host:     192.168.1.23                         │
│  SSH User:     vboxuser                             │
│  SSH Pass:     eo804482                             │
│  OS:           Debian 12 (Bookworm) 64-bit          │
│  Kernel:       6.12.57+deb13-amd64                  │
│  RAM:          4GB                                  │
│  CPU:          2 cores                              │
├─────────────────────────────────────────────────────┤
│  WiFi Adapter: TP-Link Archer T2U Plus              │
│  Chipset:      RTL8821AU                            │
│  Interface:    wlxec750c53353a                      │
│  Driver:       aircrack-ng/rtl8812au (DKMS)         │
│  2.4GHz:       14 channels (1-14)                   │
│  5GHz:         44 channels (15-177)                 │
│  Monitor Mode: ✅ Working                           │
│  Injection:    ✅ Working                           │
├─────────────────────────────────────────────────────┤
│  Project Path: ~/MoMo                               │
│  Python:       3.13.5                               │
│  Venv:         ~/MoMo/venv                          │
└─────────────────────────────────────────────────────┘
```

### SSH Bağlantı Komutları

```bash
# Windows PowerShell (plink ile)
plink -batch -pw eo804482 vboxuser@192.168.1.23 "cd ~/MoMo && source venv/bin/activate && python --version"

# Windows (ssh ile)
ssh vboxuser@192.168.1.23

# Dosya kopyalama (Windows → VM)
scp -r C:\Users\Chef\Desktop\ghub\MoMo\* vboxuser@192.168.1.23:~/MoMo/
```

## Geliştirme Stratejisi

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Windows      │    │   Linux VM      │    │  Raspberry Pi   │
│   (Geliştirme)  │ →  │    (Test)       │ →  │  (Production)   │
│                 │    │ ✅ VERIFIED     │    │                 │
│ - Kod yazma     │    │ - Unit tests    │    │ - Gerçek WiFi   │
│ - Mock testler  │    │ - iw/airmon     │    │ - Gerçek GPS    │
│ - IDE           │    │ - USB passthru  │    │ - Full system   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 1️⃣ Windows Üzerinde Geliştirme

### Neler Çalışır?
- ✅ Kod yazma/düzenleme
- ✅ Mock testler (MockWiFiScanner, MockGPSClient, MockRadioManager)
- ✅ Database testleri (aiosqlite)
- ✅ Web UI testleri (Flask)
- ✅ Event Bus testleri
- ✅ Unit testler (104 test)

### Neler Çalışmaz?
- ❌ `iw` komutu (Linux only)
- ❌ Gerçek WiFi scanning
- ❌ Monitor mode
- ❌ gpsd daemon
- ❌ Gerçek GPS cihazı

### Windows'ta Test Komutu
```powershell
cd C:\Users\Chef\Desktop\MoMo-main
python -m pytest tests/ -v
```

---

## 2️⃣ VirtualBox ile Linux VM Kurulumu

### Önerilen VM Konfigürasyonu

| Ayar | Değer |
|------|-------|
| OS | Raspberry Pi OS (64-bit) veya Debian 12 |
| RAM | 4GB minimum |
| CPU | 2 core |
| Disk | 20GB |
| Network | Bridged Adapter |

### Adım 1: VirtualBox Kurulumu

```powershell
# Winget ile kurulum
winget install Oracle.VirtualBox

# Veya manuel: https://www.virtualbox.org/wiki/Downloads
```

### Adım 2: Raspberry Pi OS İndirme

```
# Raspberry Pi Desktop (x86)
https://www.raspberrypi.com/software/raspberry-pi-desktop/

# Veya Debian 12 (daha hafif)
https://www.debian.org/download
```

### Adım 3: VM Oluşturma

1. VirtualBox → New
2. Name: `MoMo-Test`
3. Type: Linux, Version: Debian (64-bit)
4. Memory: 4096 MB
5. Hard disk: Create (VDI, Dynamic, 20GB)

### Adım 4: VM Ayarları

```
Settings → System → Processor → 2 CPU
Settings → Network → Adapter 1 → Bridged Adapter
Settings → USB → USB 3.0 Controller (xHCI)
```

### Adım 5: USB WiFi Adaptör Passthrough

**VirtualBox'ta USB cihaz ekleme:**
1. VM'i kapat
2. Settings → USB → Add Filter (+)
3. WiFi adaptörünü seç (örn: Alfa AWUS036ACH)
4. VM'i başlat

**Desteklenen WiFi Adaptörleri:**
| Adaptör | Chipset | Monitor Mode | 5GHz |
|---------|---------|--------------|------|
| Alfa AWUS036ACH | RTL8812AU | ✅ | ✅ |
| Alfa AWUS036AXML | MediaTek MT7921AU | ✅ | ✅ |
| Panda PAU09 | RT5572 | ✅ | ✅ |
| TP-Link TL-WN722N v1 | AR9271 | ✅ | ❌ |

### Adım 6: VM İçinde Kurulum

```bash
# Sistem güncelleme
sudo apt update && sudo apt upgrade -y

# Gerekli paketler
sudo apt install -y \
    git python3 python3-pip python3-venv \
    iw wireless-tools aircrack-ng \
    gpsd gpsd-clients \
    net-tools

# Proje klonlama
git clone https://github.com/user/MoMo.git
cd MoMo

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Bağımlılıklar
pip install -e ".[dev,wardriving]"

# Testler
pytest tests/ -v
```

---

## 3️⃣ USB GPS Passthrough

### GPS Cihazı Bağlama

```
VirtualBox → Settings → USB → Add Filter
→ u-blox (örnek) veya GPS cihazınız
```

### gpsd Kurulumu (VM içinde)

```bash
# gpsd kurulumu
sudo apt install gpsd gpsd-clients

# GPS cihazını bul
ls /dev/ttyUSB* /dev/ttyACM*

# gpsd konfigürasyonu
sudo nano /etc/default/gpsd
```

```
# /etc/default/gpsd
DEVICES="/dev/ttyUSB0"
GPSD_OPTIONS="-n"
START_DAEMON="true"
```

```bash
# Servisi başlat
sudo systemctl restart gpsd

# Test
gpsmon
cgps -s
```

---

## 4️⃣ WiFi Monitor Mode Testi (VM)

```bash
# Interface'leri listele
iw dev

# Monitor mode'a geç
sudo ip link set wlan0 down
sudo iw dev wlan0 set type monitor
sudo ip link set wlan0 up

# Kanal ayarla
sudo iw dev wlan0 set channel 6

# Tarama
sudo iw dev wlan0 scan

# MoMo ile test
cd MoMo
source .venv/bin/activate
python -c "
import asyncio
from momo.infrastructure.wifi import RadioManager

async def test():
    mgr = RadioManager()
    ifaces = await mgr.discover_interfaces()
    for iface in ifaces:
        print(f'{iface.name}: {iface.mode}, caps: {iface.capabilities}')

asyncio.run(test())
"
```

---

## 5️⃣ Shared Folder (Windows ↔ VM)

### VirtualBox Guest Additions

```bash
# VM içinde
sudo apt install virtualbox-guest-utils virtualbox-guest-x11

# Shared folder mount
sudo mount -t vboxsf MoMo /mnt/momo
```

### Alternatif: Git ile Senkronizasyon

```bash
# Windows'ta commit
git add -A && git commit -m "WIP" && git push

# VM'de pull
git pull
```

---

## 6️⃣ WSL2 Alternatifi (Sınırlı)

> ⚠️ WSL2'de USB WiFi passthrough zor, önerilmez.

```powershell
# WSL2 kurulumu
wsl --install -d Debian

# USB desteği (usbipd gerekli)
# https://learn.microsoft.com/en-us/windows/wsl/connect-usb
```

---

## 7️⃣ Docker ile Test (WiFi Hariç)

```yaml
# docker-compose.yml
version: '3.8'
services:
  momo-test:
    build: .
    volumes:
      - .:/app
    command: pytest tests/ -v
```

```bash
docker-compose run momo-test
```

---

## 8️⃣ Raspberry Pi'ye Deploy

### SSH ile Bağlantı

```bash
ssh pi@raspberrypi.local
```

### Projeyi Kopyalama

```bash
# rsync ile
rsync -avz --exclude='.venv' --exclude='__pycache__' \
    /mnt/momo/ pi@raspberrypi.local:~/MoMo/

# Veya git ile
git clone https://github.com/user/MoMo.git
```

### Pi Üzerinde Kurulum

```bash
cd MoMo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[wardriving]"

# Servis olarak başlat
sudo cp installers/momo.service /etc/systemd/system/
sudo systemctl enable momo
sudo systemctl start momo
```

---

## 📊 Test Matrisi

| Test Türü | Windows | Linux VM | Raspberry Pi |
|-----------|---------|----------|--------------|
| Unit Tests (Mock) | ✅ | ✅ | ✅ |
| Database (aiosqlite) | ✅ | ✅ | ✅ |
| Web UI | ✅ | ✅ | ✅ |
| Event Bus | ✅ | ✅ | ✅ |
| WiFi Scanning | ❌ | ✅* | ✅ |
| GPS | ❌ | ✅* | ✅ |
| Monitor Mode | ❌ | ✅* | ✅ |
| Packet Injection | ❌ | ✅* | ✅ |
| OLED Display | ❌ | ❌ | ✅ |

*USB passthrough gerekli

---

## 🎯 Gerçek Test Sonuçları (2025-12-11)

### RadioManager Test

```bash
sudo $(which python) -c "
from momo.infrastructure.wifi.radio_manager import RadioManager, TaskType
import asyncio

async def test():
    manager = RadioManager()
    interfaces = await manager.discover_interfaces()
    for iface in interfaces:
        caps = iface.capabilities
        print(f'{iface.name}:')
        print(f'  2.4GHz: {len(caps.channels_2ghz)} channels')
        print(f'  5GHz: {len(caps.channels_5ghz)} channels')
asyncio.run(test())
"

# Çıktı:
# wlxec750c53353a:
#   2.4GHz: 14 channels
#   5GHz: 44 channels
```

### WiFiScanner Test

```bash
sudo $(which python) -c "
from momo.infrastructure.wifi.scanner import WiFiScanner, ScanConfig
import asyncio

async def test():
    config = ScanConfig(interface='wlxec750c53353a')
    scanner = WiFiScanner(config)
    await scanner.start()
    results = await scanner.scan_once()
    print(f'Found {len(results)} APs')
    for ap in sorted(results, key=lambda x: x.rssi, reverse=True)[:5]:
        print(f'  {ap.ssid:25} | CH:{ap.channel:3} | {ap.rssi}dBm')
asyncio.run(test())
"

# Çıktı:
# Found 31 APs
#   Cyber_Misafir             | CH:  8 | -37dBm
#   Cyber                     | CH: 56 | -42dBm
#   FiberHGW_TPD258           | CH:  6 | -44dBm
#   ...
```

### Full E2E Test (Scan + Database)

```bash
# 31 AP tarandı ve SQLite'a kaydedildi
# Tüm bileşenler entegre çalışıyor ✅
```

---

## 🚀 Hızlı Başlangıç

```bash
# 1. VirtualBox kur
# 2. Raspberry Pi OS VM oluştur
# 3. USB WiFi adaptör bağla
# 4. VM'de:

sudo apt update && sudo apt install -y git python3-pip iw gpsd
git clone <repo>
cd MoMo
pip install -e ".[dev,wardriving]"

# Mock testler
pytest tests/unit/ -v

# Gerçek WiFi testi
sudo python -c "
import asyncio
from momo.infrastructure.wifi import RadioManager, TaskType

async def main():
    mgr = RadioManager()
    await mgr.discover_interfaces()
    print('Interfaces:', [i.name for i in mgr.interfaces])
    
asyncio.run(main())
"
```

---

*Son güncelleme: 2025-12-11*

