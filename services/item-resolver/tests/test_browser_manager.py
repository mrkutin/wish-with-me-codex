"""Unit tests for browser_manager module.

Tests cover:
- BrowserProfile dataclass and defaults
- Default headers configuration
- Cookies for specific hosts
- Chromium launch arguments
- Proxy configuration from environment
- BrowserManager class
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

from app.browser_manager import (
    DEFAULT_PROFILE,
    ROTATING_PROFILES,
    BrowserManager,
    BrowserProfile,
    chromium_launch_args,
    cookies_for_host,
    default_headers,
    load_manager_from_env,
    proxy_from_env,
)


# ---------------------------------------------------------------------------
# BrowserProfile Tests
# ---------------------------------------------------------------------------


class TestBrowserProfile:
    """Tests for BrowserProfile dataclass and defaults."""

    def test_browser_profile_defaults(self) -> None:
        """DEFAULT_PROFILE has expected values."""
        assert DEFAULT_PROFILE.locale == "ru-RU"
        assert DEFAULT_PROFILE.timezone_id == "Europe/Moscow"
        assert DEFAULT_PROFILE.is_mobile is False
        assert DEFAULT_PROFILE.has_touch is False
        assert DEFAULT_PROFILE.viewport == {"width": 1920, "height": 1080}
        assert "Chrome" in DEFAULT_PROFILE.user_agent
        assert DEFAULT_PROFILE.geolocation is not None
        assert DEFAULT_PROFILE.geolocation["latitude"] == 55.7558
        assert DEFAULT_PROFILE.geolocation["longitude"] == 37.6173

    def test_browser_profile_custom_values(self) -> None:
        """BrowserProfile accepts custom values."""
        profile = BrowserProfile(
            user_agent="Custom User Agent",
            viewport={"width": 800, "height": 600},
            locale="en-US",
            timezone_id="America/New_York",
            is_mobile=True,
            has_touch=True,
            geolocation={"latitude": 40.7128, "longitude": -74.0060, "accuracy": 50.0},
        )
        assert profile.user_agent == "Custom User Agent"
        assert profile.viewport == {"width": 800, "height": 600}
        assert profile.locale == "en-US"
        assert profile.timezone_id == "America/New_York"
        assert profile.is_mobile is True
        assert profile.has_touch is True
        assert profile.geolocation["latitude"] == 40.7128

    def test_rotating_profiles_exist(self) -> None:
        """ROTATING_PROFILES list is not empty and contains valid profiles."""
        assert len(ROTATING_PROFILES) > 0
        assert DEFAULT_PROFILE in ROTATING_PROFILES
        for profile in ROTATING_PROFILES:
            assert isinstance(profile, BrowserProfile)
            assert profile.user_agent
            assert profile.viewport
            assert "width" in profile.viewport
            assert "height" in profile.viewport


# ---------------------------------------------------------------------------
# Headers Tests
# ---------------------------------------------------------------------------


class TestDefaultHeaders:
    """Tests for default_headers function."""

    def test_default_headers_includes_accept_language(self) -> None:
        """Default headers include Accept-Language with Russian locale."""
        headers = default_headers()
        assert "Accept-Language" in headers
        assert "ru-RU" in headers["Accept-Language"]
        assert "ru" in headers["Accept-Language"]
        assert "en-US" in headers["Accept-Language"]

    def test_default_headers_includes_sec_fetch(self) -> None:
        """Default headers include Sec-Fetch headers for stealth."""
        headers = default_headers()
        assert headers["Sec-Fetch-Dest"] == "document"
        assert headers["Sec-Fetch-Mode"] == "navigate"
        assert headers["Sec-Fetch-Site"] == "none"
        assert headers["Sec-Fetch-User"] == "?1"

    def test_default_headers_includes_user_agent(self) -> None:
        """Default headers do NOT include User-Agent (set via profile)."""
        headers = default_headers()
        # User-Agent is set via BrowserProfile, not in default_headers
        assert "User-Agent" not in headers
        # But Accept header should be present
        assert "Accept" in headers
        assert "text/html" in headers["Accept"]


# ---------------------------------------------------------------------------
# Cookies Tests
# ---------------------------------------------------------------------------


class TestCookiesForHost:
    """Tests for cookies_for_host function."""

    def test_cookies_for_host_yandex_market(self) -> None:
        """Yandex Market gets specific cookies."""
        cookies = cookies_for_host("market.yandex.ru")
        assert len(cookies) > 0

        cookie_names = [c["name"] for c in cookies]
        assert "_ym_uid" in cookie_names
        assert "_ym_d" in cookie_names
        assert "yandexuid" in cookie_names
        assert "yuidss" in cookie_names
        assert "yandex_gid" in cookie_names
        assert "_ym_isad" in cookie_names

        # Check domains
        for cookie in cookies:
            assert cookie["domain"] in (".market.yandex.ru", ".yandex.ru")
            assert cookie["path"] == "/"

    def test_cookies_for_host_yandex_ru(self) -> None:
        """Shared Yandex cookies for yandex.ru domain."""
        cookies = cookies_for_host("www.yandex.ru")
        assert len(cookies) > 0

        cookie_names = [c["name"] for c in cookies]
        assert "yandexuid" in cookie_names
        assert "i" in cookie_names

    def test_cookies_for_host_aliexpress(self) -> None:
        """AliExpress gets locale/region cookies."""
        cookies = cookies_for_host("aliexpress.ru")
        assert len(cookies) == 1

        cookie = cookies[0]
        assert cookie["name"] == "aep_usuc_f"
        assert cookie["domain"] == ".aliexpress.ru"
        assert "site=rus" in cookie["value"]
        assert "c_tp=RUB" in cookie["value"]
        assert "region=RU" in cookie["value"]
        assert "b_locale=ru_RU" in cookie["value"]

    def test_cookies_for_host_unknown(self) -> None:
        """Unknown hosts return empty cookie list."""
        cookies = cookies_for_host("example.com")
        assert cookies == []

        cookies = cookies_for_host("amazon.com")
        assert cookies == []

        cookies = cookies_for_host("ozon.ru")
        assert cookies == []


# ---------------------------------------------------------------------------
# Chromium Launch Args Tests
# ---------------------------------------------------------------------------


class TestChromiumLaunchArgs:
    """Tests for chromium_launch_args function."""

    def test_chromium_launch_args_basics(self) -> None:
        """Required args are present in launch arguments."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROXY_IGNORE_CERT_ERRORS", None)
            args = chromium_launch_args()

        assert "--disable-dev-shm-usage" in args
        assert "--window-size=1920,1080" in args
        assert "--disable-web-security" in args
        assert "--disable-features=IsolateOrigins" in args
        assert "--disable-site-isolation-trials" in args

    def test_chromium_launch_args_no_sandbox(self) -> None:
        """Sandbox is disabled for container compatibility."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROXY_IGNORE_CERT_ERRORS", None)
            args = chromium_launch_args()

        assert "--no-sandbox" in args
        assert "--disable-setuid-sandbox" in args

    def test_chromium_launch_args_disable_automation(self) -> None:
        """Automation features are disabled for stealth."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROXY_IGNORE_CERT_ERRORS", None)
            args = chromium_launch_args()

        assert "--disable-blink-features=AutomationControlled" in args

    def test_chromium_launch_args_with_proxy_cert_errors(self) -> None:
        """Certificate errors can be ignored for MITM proxies."""
        # Test with "1"
        with patch.dict(os.environ, {"PROXY_IGNORE_CERT_ERRORS": "1"}):
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" in args

        # Test with "true"
        with patch.dict(os.environ, {"PROXY_IGNORE_CERT_ERRORS": "true"}):
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" in args

        # Test with "yes"
        with patch.dict(os.environ, {"PROXY_IGNORE_CERT_ERRORS": "yes"}):
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" in args

        # Test with "TRUE" (case insensitive)
        with patch.dict(os.environ, {"PROXY_IGNORE_CERT_ERRORS": "TRUE"}):
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" in args

        # Test without the env var
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROXY_IGNORE_CERT_ERRORS", None)
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" not in args

        # Test with "0" (disabled)
        with patch.dict(os.environ, {"PROXY_IGNORE_CERT_ERRORS": "0"}):
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" not in args

        # Test with "false"
        with patch.dict(os.environ, {"PROXY_IGNORE_CERT_ERRORS": "false"}):
            args = chromium_launch_args()
            assert "--ignore-certificate-errors" not in args


# ---------------------------------------------------------------------------
# Proxy Configuration Tests
# ---------------------------------------------------------------------------


class TestProxyFromEnv:
    """Tests for proxy_from_env function."""

    def test_proxy_from_env_no_proxy(self) -> None:
        """Returns None when no proxy server is configured."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROXY_SERVER", None)
            os.environ.pop("PROXY_USERNAME", None)
            os.environ.pop("PROXY_PASSWORD", None)
            os.environ.pop("PROXY_BYPASS", None)
            result = proxy_from_env()

        assert result is None

    def test_proxy_from_env_empty_server(self) -> None:
        """Returns None when PROXY_SERVER is empty string."""
        with patch.dict(os.environ, {"PROXY_SERVER": ""}):
            result = proxy_from_env()

        assert result is None

    def test_proxy_from_env_whitespace_server(self) -> None:
        """Returns None when PROXY_SERVER is whitespace only."""
        with patch.dict(os.environ, {"PROXY_SERVER": "   "}):
            result = proxy_from_env()

        assert result is None

    def test_proxy_from_env_with_server(self) -> None:
        """Returns dict with server when PROXY_SERVER is set."""
        with patch.dict(
            os.environ,
            {"PROXY_SERVER": "http://proxy.example.com:8080"},
            clear=False,
        ):
            os.environ.pop("PROXY_USERNAME", None)
            os.environ.pop("PROXY_PASSWORD", None)
            os.environ.pop("PROXY_BYPASS", None)
            result = proxy_from_env()

        assert result is not None
        assert result["server"] == "http://proxy.example.com:8080"
        assert "username" not in result
        assert "password" not in result
        assert "bypass" not in result

    def test_proxy_from_env_with_auth(self) -> None:
        """Includes username/password when set."""
        with patch.dict(
            os.environ,
            {
                "PROXY_SERVER": "http://proxy.example.com:8080",
                "PROXY_USERNAME": "proxyuser",
                "PROXY_PASSWORD": "proxypass123",
            },
            clear=False,
        ):
            os.environ.pop("PROXY_BYPASS", None)
            result = proxy_from_env()

        assert result is not None
        assert result["server"] == "http://proxy.example.com:8080"
        assert result["username"] == "proxyuser"
        assert result["password"] == "proxypass123"

    def test_proxy_from_env_with_bypass(self) -> None:
        """Includes bypass list when set."""
        with patch.dict(
            os.environ,
            {
                "PROXY_SERVER": "http://proxy.example.com:8080",
                "PROXY_BYPASS": "localhost,127.0.0.1,.internal.com",
            },
            clear=False,
        ):
            os.environ.pop("PROXY_USERNAME", None)
            os.environ.pop("PROXY_PASSWORD", None)
            result = proxy_from_env()

        assert result is not None
        assert result["server"] == "http://proxy.example.com:8080"
        assert result["bypass"] == "localhost,127.0.0.1,.internal.com"

    def test_proxy_from_env_full_config(self) -> None:
        """Full proxy configuration with all options."""
        with patch.dict(
            os.environ,
            {
                "PROXY_SERVER": "socks5://proxy.corp.com:1080",
                "PROXY_USERNAME": "admin",
                "PROXY_PASSWORD": "secret",
                "PROXY_BYPASS": "*.internal.com,localhost",
            },
        ):
            result = proxy_from_env()

        assert result is not None
        assert result["server"] == "socks5://proxy.corp.com:1080"
        assert result["username"] == "admin"
        assert result["password"] == "secret"
        assert result["bypass"] == "*.internal.com,localhost"


# ---------------------------------------------------------------------------
# BrowserManager Tests
# ---------------------------------------------------------------------------


class TestBrowserManager:
    """Tests for BrowserManager class."""

    def test_load_manager_from_env_creates_manager(self) -> None:
        """load_manager_from_env creates BrowserManager with env settings."""
        with patch.dict(
            os.environ,
            {
                "BROWSER_CHANNEL": "chromium",
                "HEADLESS": "true",
                "MAX_CONCURRENCY": "4",
            },
        ):
            manager = load_manager_from_env()

        assert isinstance(manager, BrowserManager)
        assert manager.channel == "chromium"
        assert manager.headless is True

    def test_load_manager_from_env_defaults(self) -> None:
        """load_manager_from_env uses defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BROWSER_CHANNEL", None)
            os.environ.pop("HEADLESS", None)
            os.environ.pop("MAX_CONCURRENCY", None)
            manager = load_manager_from_env()

        assert manager.channel == "chromium"
        assert manager.headless is True

    def test_load_manager_from_env_chrome_channel(self) -> None:
        """load_manager_from_env handles chrome channel."""
        with patch.dict(os.environ, {"BROWSER_CHANNEL": "chrome"}):
            manager = load_manager_from_env()

        assert manager.channel == "chrome"

    def test_load_manager_from_env_invalid_channel(self) -> None:
        """load_manager_from_env defaults to chromium for invalid channel."""
        with patch.dict(os.environ, {"BROWSER_CHANNEL": "firefox"}):
            manager = load_manager_from_env()

        assert manager.channel == "chromium"

    def test_load_manager_from_env_headless_false(self) -> None:
        """load_manager_from_env respects HEADLESS=false."""
        for value in ("0", "false", "no", "False", "NO"):
            with patch.dict(os.environ, {"HEADLESS": value}):
                manager = load_manager_from_env()
            assert manager.headless is False, f"Failed for HEADLESS={value}"

    def test_browser_manager_concurrency_semaphore(self) -> None:
        """BrowserManager creates semaphore with correct concurrency."""
        manager = BrowserManager(channel="chromium", headless=True, max_concurrency=5)

        assert isinstance(manager.semaphore, asyncio.Semaphore)
        # Semaphore internal value check
        assert manager.semaphore._value == 5

    def test_browser_manager_concurrency_minimum(self) -> None:
        """BrowserManager enforces minimum concurrency of 1."""
        manager = BrowserManager(channel="chromium", headless=True, max_concurrency=0)
        assert manager.semaphore._value == 1

        manager = BrowserManager(channel="chromium", headless=True, max_concurrency=-5)
        assert manager.semaphore._value == 1

    def test_browser_manager_properties(self) -> None:
        """BrowserManager exposes channel and headless properties."""
        manager = BrowserManager(channel="chrome", headless=False, max_concurrency=3)

        assert manager.channel == "chrome"
        assert manager.headless is False
        assert manager.semaphore._value == 3
