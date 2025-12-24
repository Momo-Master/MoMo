"""
OLED Display Support for First Boot Wizard.

Shows setup information on OLED screen including:
- QR code for WiFi connection
- Setup status messages
- Network information
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SetupOLED:
    """
    OLED display handler for first boot wizard.
    
    Displays setup information to help users connect.
    """
    
    def __init__(self, width: int = 128, height: int = 64):
        """
        Initialize OLED handler.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self.width = width
        self.height = height
        self._display = None
        self._font = None
        self._font_small = None
        self._available = False
        
        self._init_display()
    
    def _init_display(self):
        """Initialize OLED display if available."""
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import ssd1306
            from PIL import ImageFont
            
            serial = i2c(port=1, address=0x3C)
            self._display = ssd1306(serial, width=self.width, height=self.height)
            
            # Try to load fonts
            try:
                self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
                self._font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
            except Exception:
                self._font = ImageFont.load_default()
                self._font_small = self._font
            
            self._available = True
            logger.info("OLED display initialized")
            
        except ImportError:
            logger.debug("luma.oled not installed, OLED disabled")
        except Exception as e:
            logger.debug(f"OLED not available: {e}")
    
    @property
    def available(self) -> bool:
        """Check if display is available."""
        return self._available
    
    def show_setup_screen(
        self,
        ssid: str,
        password: str,
        ip_address: str,
    ):
        """
        Show setup screen with WiFi credentials.
        
        Args:
            ssid: WiFi network name
            password: WiFi password
            ip_address: IP address for web wizard
        """
        if not self._available:
            return
        
        try:
            from PIL import Image, ImageDraw
            
            # Create image
            image = Image.new("1", (self.width, self.height), 0)
            draw = ImageDraw.Draw(image)
            
            # Title
            draw.text((0, 0), "🔥 MoMo Setup", font=self._font, fill=1)
            
            # WiFi info
            draw.text((0, 16), f"WiFi: {ssid[:14]}", font=self._font_small, fill=1)
            draw.text((0, 28), f"Pass: {password[:14]}", font=self._font_small, fill=1)
            
            # IP address
            draw.text((0, 44), ip_address, font=self._font, fill=1)
            
            # Display
            self._display.display(image)
            
        except Exception as e:
            logger.error(f"Failed to update OLED: {e}")
    
    def show_qr_code(self, ssid: str, password: str):
        """
        Show WiFi QR code on display.
        
        Args:
            ssid: WiFi network name
            password: WiFi password
        """
        if not self._available:
            return
        
        try:
            import qrcode
            from PIL import Image
            
            # Generate WiFi QR code
            wifi_string = f"WIFI:T:WPA;S:{ssid};P:{password};;"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=2,
                border=1,
            )
            qr.add_data(wifi_string)
            qr.make(fit=True)
            
            # Create QR image
            qr_img = qr.make_image(fill_color="white", back_color="black")
            qr_img = qr_img.resize((self.height, self.height))  # Square
            
            # Create final image
            image = Image.new("1", (self.width, self.height), 0)
            
            # Paste QR on the right
            qr_x = self.width - self.height
            image.paste(qr_img, (qr_x, 0))
            
            # Add text on the left
            from PIL import ImageDraw
            draw = ImageDraw.Draw(image)
            draw.text((0, 0), "Scan QR", font=self._font_small, fill=1)
            draw.text((0, 12), "to connect", font=self._font_small, fill=1)
            draw.text((0, 28), ssid[:8], font=self._font_small, fill=1)
            
            self._display.display(image)
            
        except ImportError:
            logger.debug("qrcode library not installed")
            self.show_setup_screen(ssid, password, "192.168.4.1")
        except Exception as e:
            logger.error(f"Failed to show QR: {e}")
    
    def show_status(self, message: str, line2: str = ""):
        """
        Show status message on display.
        
        Args:
            message: Main status message
            line2: Optional second line
        """
        if not self._available:
            return
        
        try:
            from PIL import Image, ImageDraw
            
            image = Image.new("1", (self.width, self.height), 0)
            draw = ImageDraw.Draw(image)
            
            # Center the text vertically
            y = 20 if not line2 else 16
            draw.text((4, y), message[:20], font=self._font, fill=1)
            
            if line2:
                draw.text((4, y + 16), line2[:20], font=self._font_small, fill=1)
            
            self._display.display(image)
            
        except Exception as e:
            logger.error(f"Failed to update OLED: {e}")
    
    def show_complete(self, new_ssid: str, ip: str):
        """
        Show setup complete screen.
        
        Args:
            new_ssid: New management network SSID
            ip: New IP address
        """
        if not self._available:
            return
        
        try:
            from PIL import Image, ImageDraw
            
            image = Image.new("1", (self.width, self.height), 0)
            draw = ImageDraw.Draw(image)
            
            draw.text((0, 0), "✓ Setup Complete!", font=self._font, fill=1)
            draw.line((0, 14, self.width, 14), fill=1)
            
            draw.text((0, 20), f"WiFi: {new_ssid[:14]}", font=self._font_small, fill=1)
            draw.text((0, 34), f"Dashboard:", font=self._font_small, fill=1)
            draw.text((0, 48), f"http://{ip}:8082", font=self._font_small, fill=1)
            
            self._display.display(image)
            
        except Exception as e:
            logger.error(f"Failed to update OLED: {e}")
    
    def clear(self):
        """Clear the display."""
        if not self._available:
            return
        
        try:
            from PIL import Image
            image = Image.new("1", (self.width, self.height), 0)
            self._display.display(image)
        except Exception:
            pass

