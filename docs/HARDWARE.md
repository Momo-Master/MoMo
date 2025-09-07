# Hardware

- Raspberry Pi 5 (64-bit Bookworm)
- Wi-Fi: TP-Link Archer T2U Plus (RTL8812AU)
- Optional: SSD1106 OLED via I²C (0x3C)

## Notes

- Enable I²C: `sudo raspi-config` -> Interfaces -> I2C
- Install RTL8812AU driver: `rtl8812au-dkms` (Bookworm repo or vendor)
- Use powered USB hub if power issues occur
