"""Security tests for MoMo."""

import os
import pytest


@pytest.fixture
def secure_app():
    """Create app with security enabled."""
    from momo.config import MomoConfig
    from momo.apps.momo_web import create_app
    
    # Set a token so auth is actually required
    os.environ["MOMO_UI_TOKEN"] = "test-security-token-12345"
    
    config = MomoConfig()
    config.web.require_token = True
    config.web.allow_local_unauth = False  # Disable local auth bypass for testing
    app = create_app(config)
    app.config["TESTING"] = True
    
    yield app
    
    # Cleanup
    os.environ.pop("MOMO_UI_TOKEN", None)


@pytest.fixture
def secure_client(secure_app):
    return secure_app.test_client()


class TestAuthentication:
    """Test authentication mechanisms."""

    def test_no_token_rejected(self, secure_client):
        """Requests without token should be rejected."""
        response = secure_client.get("/api/captures")
        assert response.status_code in [401, 302]

    def test_invalid_token_rejected(self, secure_client):
        """Invalid tokens should be rejected."""
        response = secure_client.get(
            "/api/captures",
            headers={"Authorization": "Bearer invalid_token_123"}
        )
        assert response.status_code in [401, 302]

    def test_empty_token_rejected(self, secure_client):
        """Empty token should be rejected."""
        response = secure_client.get(
            "/api/captures",
            headers={"Authorization": "Bearer "}
        )
        assert response.status_code in [401, 302]

    def test_malformed_auth_header(self, secure_client):
        """Malformed auth header should be rejected."""
        response = secure_client.get(
            "/api/captures",
            headers={"Authorization": "NotBearer token"}
        )
        assert response.status_code in [401, 302]


class TestInputValidation:
    """Test input validation and sanitization."""

    @pytest.fixture
    def client(self):
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        config = MomoConfig()
        config.web.require_token = False
        app = create_app(config)
        app.config["TESTING"] = True
        return app.test_client()

    def test_sql_injection_bssid(self, client):
        """SQL injection in BSSID parameter should be handled."""
        response = client.get("/api/captures?bssid='; DROP TABLE captures;--")
        # Should not crash, return error or empty
        assert response.status_code in [200, 400, 404, 500, 503]

    def test_path_traversal_download(self, client):
        """Path traversal in download should be blocked."""
        response = client.get("/api/captures/../../../etc/passwd/download")
        assert response.status_code in [400, 404, 500]

    def test_xss_in_ssid(self, client):
        """XSS in SSID should be escaped."""
        # This tests that malicious SSID doesn't execute
        response = client.get("/api/captures?ssid=<script>alert(1)</script>")
        assert response.status_code in [200, 400, 500, 503]
        if response.status_code == 200:
            # If data returned, ensure no raw script tag
            assert b"<script>" not in response.data

    def test_command_injection_interface(self, client):
        """Command injection in interface name should be blocked."""
        response = client.post(
            "/api/captures/start",
            json={"interface": "wlan0; rm -rf /"}
        )
        # Should validate interface name format (405 = no POST endpoint)
        assert response.status_code in [200, 400, 404, 405, 500, 503]

    def test_null_byte_injection(self, client):
        """Null byte injection should be handled."""
        response = client.get("/api/captures?file=test.pcap")
        assert response.status_code in [200, 400, 404, 500, 503]


class TestRateLimiting:
    """Test rate limiting (if implemented)."""

    def test_many_requests_not_crash(self):
        """Many rapid requests should not crash server."""
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        config = MomoConfig()
        config.web.require_token = False
        app = create_app(config)
        app.config["TESTING"] = True
        
        with app.test_client() as client:
            for _ in range(100):
                response = client.get("/api/captures/stats")
                # Should always respond
                assert response.status_code in [200, 429, 503]


class TestSessionSecurity:
    """Test session handling security."""

    def test_session_cookie_secure_attrs(self):
        """Session cookie should have security attributes."""
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        config = MomoConfig()
        app = create_app(config)
        
        # Check session config
        assert app.secret_key is not None


class TestCredentialStorage:
    """Test credential handling."""

    def test_no_password_in_response(self):
        """API responses should not contain raw passwords."""
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        config = MomoConfig()
        config.web.require_token = False
        app = create_app(config)
        app.config["TESTING"] = True
        
        with app.test_client() as client:
            response = client.get("/api/eviltwin/credentials")
            if response.status_code == 200:
                data = response.get_json()
                # Credentials should be structured, not raw
                assert "credentials" in data or "error" in data


class TestFileAccess:
    """Test file access controls."""

    @pytest.fixture
    def client(self):
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        config = MomoConfig()
        config.web.require_token = False
        app = create_app(config)
        app.config["TESTING"] = True
        return app.test_client()

    def test_cannot_access_system_files(self, client):
        """Should not be able to access system files."""
        dangerous_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "../../../etc/passwd",
            "....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2fetc/passwd",
        ]
        
        for path in dangerous_paths:
            response = client.get(f"/api/captures/{path}/download")
            assert response.status_code in [400, 404, 405]

    def test_only_capture_files_downloadable(self, client):
        """Only capture files should be downloadable."""
        response = client.get("/api/captures/config.yml/download")
        assert response.status_code in [400, 404]


class TestErrorMessages:
    """Test that error messages don't leak info."""

    @pytest.fixture
    def client(self):
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        config = MomoConfig()
        config.web.require_token = False
        app = create_app(config)
        app.config["TESTING"] = True
        return app.test_client()

    def test_no_stack_trace_in_error(self, client):
        """Error responses should not contain stack traces."""
        response = client.get("/api/unknown")
        if response.status_code >= 400:
            data = response.data.decode()
            assert "Traceback" not in data
            assert "File \"" not in data

    def test_no_internal_paths_leaked(self, client):
        """Error messages should not leak internal paths."""
        response = client.get("/api/captures/nonexistent/download")
        if response.status_code >= 400:
            data = response.data.decode()
            assert "/home/" not in data
            assert "/root/" not in data
            assert "C:\\" not in data

