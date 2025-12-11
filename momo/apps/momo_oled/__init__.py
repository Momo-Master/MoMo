"""OLED module placeholder with soft-fail imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OledStatus:
    mode: str
    channel: int | None
    handshakes: int
    files: int
    temperature_c: float | None


def try_init_display() -> object | None:  # pragma: no cover - optional dependency
    try:
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106

        serial = i2c(port=1, address=0x3C)
        device = sh1106(serial)
        return device
    except Exception:
        return None


def render_status(device: object | None, status: OledStatus) -> None:  # pragma: no cover
    if device is None:
        return
    from PIL import Image, ImageDraw, ImageFont  # lazy import

    width = device.width
    height = device.height
    image = Image.new("1", (width, height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((0, 0), f"Mode: {status.mode}", font=font, fill=255)
    draw.text((0, 12), f"Ch: {status.channel}", font=font, fill=255)
    draw.text((0, 24), f"HS: {status.handshakes}", font=font, fill=255)
    draw.text((0, 36), f"Files: {status.files}", font=font, fill=255)
    if status.temperature_c is not None:
        draw.text((0, 48), f"T: {status.temperature_c:.1f}C", font=font, fill=255)
    device.display(image)


