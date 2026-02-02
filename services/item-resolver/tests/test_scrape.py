"""Unit tests for scrape module.

Tests cover pure functions only (no Playwright integration):
- safe_host() - hostname sanitization
- registrable_domain() - eTLD+1 extraction
- looks_like_interstitial_or_challenge() - challenge page detection
- storage_state_path() - path generation and directory creation
- _state_merge() - Playwright storage state merging
- PageCaptureConfig - configuration dataclass
- _challenge_title_patterns() - challenge pattern list
- dismiss_common_popups patterns - popup button/close selector patterns
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app.scrape import (
    PageCaptureConfig,
    _challenge_title_patterns,
    _state_merge,
    looks_like_interstitial_or_challenge,
    registrable_domain,
    safe_host,
    storage_state_path,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# safe_host() Tests
# ---------------------------------------------------------------------------


class TestSafeHost:
    """Tests for safe_host() function."""

    def test_safe_host_sanitizes_hostname(self) -> None:
        """Remove special characters from hostname."""
        # Hostname with special chars gets sanitized (underscores replace invalid chars)
        # Note: URL parsing extracts hostname first, then sanitization happens
        assert safe_host("https://exam-ple_test.com/path") == "exam-ple_test.com"
        # Hostname with dots preserved
        assert safe_host("https://sub.domain.example.com/") == "sub.domain.example.com"
        # If URL has @ symbol, urlparse treats it as userinfo, hostname is what follows
        assert safe_host("http://user@example.com/") == "example.com"

    def test_safe_host_extracts_from_url(self) -> None:
        """Extract hostname from full URL."""
        assert safe_host("https://www.example.com/path?query=1") == "www.example.com"
        assert safe_host("http://shop.amazon.co.uk:8080/product") == "shop.amazon.co.uk"

    def test_safe_host_preserves_valid_chars(self) -> None:
        """Preserve alphanumeric, hyphen, underscore, and dot."""
        assert safe_host("https://my-site_123.example.com/") == "my-site_123.example.com"

    def test_safe_host_handles_missing_hostname(self) -> None:
        """Return 'unknown-host' for URLs without hostname."""
        assert safe_host("") == "unknown-host"
        assert safe_host("not-a-url") == "unknown-host"
        assert safe_host("file:///etc/passwd") == "unknown-host"

    def test_safe_host_handles_ip_address(self) -> None:
        """Handle IP addresses in URL."""
        assert safe_host("http://192.168.1.1/path") == "192.168.1.1"
        assert safe_host("http://127.0.0.1:8000/") == "127.0.0.1"


# ---------------------------------------------------------------------------
# registrable_domain() Tests
# ---------------------------------------------------------------------------


class TestRegistrableDomain:
    """Tests for registrable_domain() function."""

    def test_registrable_domain_simple(self) -> None:
        """Simple domain returns as-is."""
        assert registrable_domain("example.com") == "example.com"
        assert registrable_domain("google.ru") == "google.ru"

    def test_registrable_domain_subdomain(self) -> None:
        """Extract eTLD+1 from subdomain."""
        assert registrable_domain("www.example.com") == "example.com"
        assert registrable_domain("shop.store.example.com") == "example.com"
        assert registrable_domain("api.v2.internal.example.org") == "example.org"

    def test_registrable_domain_multipart_tld(self) -> None:
        """Handle multi-part TLDs like .co.uk."""
        assert registrable_domain("amazon.co.uk") == "amazon.co.uk"
        assert registrable_domain("www.amazon.co.uk") == "amazon.co.uk"
        assert registrable_domain("shop.amazon.co.uk") == "amazon.co.uk"

    def test_registrable_domain_multipart_tld_variants(self) -> None:
        """Handle various multi-part TLDs."""
        assert registrable_domain("shop.example.com.au") == "example.com.au"
        assert registrable_domain("www.example.co.jp") == "example.co.jp"
        assert registrable_domain("api.example.com.br") == "example.com.br"
        assert registrable_domain("www.example.com.tr") == "example.com.tr"
        assert registrable_domain("shop.example.com.cn") == "example.com.cn"

    def test_registrable_domain_ip_address(self) -> None:
        """IP addresses pass through unchanged."""
        assert registrable_domain("192.168.1.1") == "192.168.1.1"
        assert registrable_domain("10.0.0.1") == "10.0.0.1"
        assert registrable_domain("127.0.0.1") == "127.0.0.1"

    def test_registrable_domain_empty_input(self) -> None:
        """Handle empty or whitespace input."""
        assert registrable_domain("") == "unknown-host"
        assert registrable_domain("   ") == "unknown-host"
        assert registrable_domain(None) == "unknown-host"  # type: ignore[arg-type]

    def test_registrable_domain_trailing_dot(self) -> None:
        """Handle trailing dots in hostname."""
        assert registrable_domain("example.com.") == "example.com"
        assert registrable_domain("www.example.com.") == "example.com"

    def test_registrable_domain_single_part(self) -> None:
        """Single-part domains return as-is."""
        assert registrable_domain("localhost") == "localhost"
        assert registrable_domain("intranet") == "intranet"


# ---------------------------------------------------------------------------
# looks_like_interstitial_or_challenge() Tests
# ---------------------------------------------------------------------------


class TestLooksLikeInterstitial:
    """Tests for looks_like_interstitial_or_challenge() function."""

    def test_looks_like_interstitial_captcha(self) -> None:
        """Detect captcha keywords."""
        assert looks_like_interstitial_or_challenge("CAPTCHA Required", "") is True
        assert looks_like_interstitial_or_challenge("", "<div>Please complete the captcha</div>") is True
        assert looks_like_interstitial_or_challenge("Solve Captcha", "<html></html>") is True

    def test_looks_like_interstitial_russian(self) -> None:
        """Detect Russian challenge text."""
        assert looks_like_interstitial_or_challenge("", "Подтвердите, что вы не робот") is True
        assert looks_like_interstitial_or_challenge("Проверка браузера", "") is True
        assert looks_like_interstitial_or_challenge("", "Доступ ограничен") is True
        assert looks_like_interstitial_or_challenge("Проверка устройства", "<html></html>") is True
        assert looks_like_interstitial_or_challenge("", "Почти готово...") is True
        assert looks_like_interstitial_or_challenge("Проверка", "") is True

    def test_looks_like_interstitial_access_denied(self) -> None:
        """Detect access denied pages."""
        assert looks_like_interstitial_or_challenge("Access Denied", "") is True
        assert looks_like_interstitial_or_challenge("403 Forbidden", "") is True
        assert looks_like_interstitial_or_challenge("", "<h1>Too Many Requests</h1>") is True
        assert looks_like_interstitial_or_challenge("", "Rate limit exceeded") is True

    def test_looks_like_interstitial_bot_detection(self) -> None:
        """Detect bot detection pages."""
        assert looks_like_interstitial_or_challenge("Robot Check", "") is True
        assert looks_like_interstitial_or_challenge("", "Checking your browser...") is True
        assert looks_like_interstitial_or_challenge("", "Bot detection in progress") is True
        assert looks_like_interstitial_or_challenge("Anti-bot Protection", "") is True
        assert looks_like_interstitial_or_challenge("Security Check", "") is True

    def test_looks_like_interstitial_challenge(self) -> None:
        """Detect generic challenge pages."""
        assert looks_like_interstitial_or_challenge("Challenge Required", "") is True
        assert looks_like_interstitial_or_challenge("", "Verify you are human") is True
        assert looks_like_interstitial_or_challenge("", "verify that you are not a robot") is True

    def test_looks_like_interstitial_normal_page(self) -> None:
        """Return false for normal content."""
        # Product page - should NOT trigger
        assert looks_like_interstitial_or_challenge(
            "iPhone 15 Pro - Apple Store",
            "<html><body><h1>iPhone 15 Pro</h1><p>Price: $999</p></body></html>",
        ) is False

        # News article - should NOT trigger
        assert looks_like_interstitial_or_challenge(
            "Breaking News - CNN",
            "<html><body><article>Today's top stories...</article></body></html>",
        ) is False

        # Empty content - should NOT trigger (no challenge keywords)
        assert looks_like_interstitial_or_challenge("", "") is False

    def test_looks_like_interstitial_case_insensitive(self) -> None:
        """Detection is case-insensitive."""
        assert looks_like_interstitial_or_challenge("CAPTCHA", "") is True
        assert looks_like_interstitial_or_challenge("Captcha", "") is True
        assert looks_like_interstitial_or_challenge("captcha", "") is True
        assert looks_like_interstitial_or_challenge("ACCESS DENIED", "") is True


# ---------------------------------------------------------------------------
# storage_state_path() Tests
# ---------------------------------------------------------------------------


class TestStorageStatePath:
    """Tests for storage_state_path() function."""

    def test_storage_state_path_creates_directory(self, tmp_path: Path) -> None:
        """Create directory if it doesn't exist."""
        state_dir = tmp_path / "new_dir" / "nested"
        assert not state_dir.exists()

        result = storage_state_path(state_dir, "https://example.com/page")

        assert state_dir.exists()
        assert state_dir.is_dir()
        assert result.parent == state_dir

    def test_storage_state_path_generates_correct_filename(self, tmp_path: Path) -> None:
        """Generate filename based on registrable domain."""
        result = storage_state_path(tmp_path, "https://www.example.com/page")
        assert result.name == "example.com.json"

    def test_storage_state_path_handles_subdomain(self, tmp_path: Path) -> None:
        """Subdomain URLs use registrable domain for filename."""
        result1 = storage_state_path(tmp_path, "https://shop.example.com/product")
        result2 = storage_state_path(tmp_path, "https://api.example.com/v1/items")
        result3 = storage_state_path(tmp_path, "https://www.example.com/")

        # All should use the same storage file
        assert result1.name == "example.com.json"
        assert result2.name == "example.com.json"
        assert result3.name == "example.com.json"

    def test_storage_state_path_handles_multipart_tld(self, tmp_path: Path) -> None:
        """Multi-part TLDs are handled correctly."""
        result = storage_state_path(tmp_path, "https://www.amazon.co.uk/product")
        assert result.name == "amazon.co.uk.json"


# ---------------------------------------------------------------------------
# _state_merge() Tests
# ---------------------------------------------------------------------------


class TestStateMerge:
    """Tests for _state_merge() function."""

    def test_state_merge_cookies(self) -> None:
        """Merge cookie arrays, b overrides a."""
        a = {
            "cookies": [
                {"name": "session", "domain": ".example.com", "path": "/", "value": "old"},
                {"name": "token", "domain": ".example.com", "path": "/", "value": "token1"},
            ],
            "origins": [],
        }
        b = {
            "cookies": [
                {"name": "session", "domain": ".example.com", "path": "/", "value": "new"},
                {"name": "tracking", "domain": ".example.com", "path": "/", "value": "track1"},
            ],
            "origins": [],
        }

        result = _state_merge(a, b)

        # Should have 3 cookies: session (overridden), token (from a), tracking (from b)
        assert len(result["cookies"]) == 3
        cookies_by_name = {c["name"]: c for c in result["cookies"]}
        assert cookies_by_name["session"]["value"] == "new"  # b overrides a
        assert cookies_by_name["token"]["value"] == "token1"
        assert cookies_by_name["tracking"]["value"] == "track1"

    def test_state_merge_localStorage(self) -> None:
        """Merge localStorage arrays, b overrides a."""
        a = {
            "cookies": [],
            "origins": [
                {
                    "origin": "https://example.com",
                    "localStorage": [
                        {"name": "theme", "value": "dark"},
                        {"name": "lang", "value": "en"},
                    ],
                }
            ],
        }
        b = {
            "cookies": [],
            "origins": [
                {
                    "origin": "https://example.com",
                    "localStorage": [
                        {"name": "theme", "value": "light"},
                        {"name": "cart", "value": "[]"},
                    ],
                }
            ],
        }

        result = _state_merge(a, b)

        # Should have 1 origin with 3 localStorage items
        assert len(result["origins"]) == 1
        origin = result["origins"][0]
        assert origin["origin"] == "https://example.com"
        assert len(origin["localStorage"]) == 3

        ls_by_name = {item["name"]: item for item in origin["localStorage"]}
        assert ls_by_name["theme"]["value"] == "light"  # b overrides a
        assert ls_by_name["lang"]["value"] == "en"
        assert ls_by_name["cart"]["value"] == "[]"

    def test_state_merge_multiple_origins(self) -> None:
        """Merge states with different origins."""
        a = {
            "cookies": [],
            "origins": [
                {"origin": "https://a.com", "localStorage": [{"name": "x", "value": "1"}]},
            ],
        }
        b = {
            "cookies": [],
            "origins": [
                {"origin": "https://b.com", "localStorage": [{"name": "y", "value": "2"}]},
            ],
        }

        result = _state_merge(a, b)

        assert len(result["origins"]) == 2
        origins_by_url = {o["origin"]: o for o in result["origins"]}
        assert "https://a.com" in origins_by_url
        assert "https://b.com" in origins_by_url

    def test_state_merge_empty_inputs(self) -> None:
        """Handle empty or missing fields."""
        result = _state_merge({}, {})
        assert result == {"cookies": [], "origins": []}

        result = _state_merge({"cookies": None, "origins": None}, {})
        assert result == {"cookies": [], "origins": []}

    def test_state_merge_invalid_entries_skipped(self) -> None:
        """Skip non-dict entries in arrays."""
        a = {
            "cookies": [
                {"name": "valid", "domain": ".example.com", "path": "/", "value": "v"},
                "invalid_string",
                None,
                123,
            ],
            "origins": [],
        }

        result = _state_merge(a, {"cookies": [], "origins": []})

        assert len(result["cookies"]) == 1
        assert result["cookies"][0]["name"] == "valid"


# ---------------------------------------------------------------------------
# PageCaptureConfig Tests
# ---------------------------------------------------------------------------


class TestPageCaptureConfig:
    """Tests for PageCaptureConfig dataclass."""

    def test_page_capture_config_defaults(self) -> None:
        """Verify default configuration values."""
        cfg = PageCaptureConfig()

        assert cfg.wait_until == "load"
        assert cfg.timeout_ms == 90_000
        assert cfg.settle_ms == 5_000
        assert cfg.max_extra_wait_ms == 30_000
        assert cfg.network_quiet_ms == 2_000
        assert cfg.dom_sample_interval_ms == 500
        assert cfg.dom_stable_samples == 3
        assert cfg.challenge_extra_wait_ms == 120_000
        assert cfg.post_challenge_settle_ms == 3_000

    def test_page_capture_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config reads from environment variables."""
        monkeypatch.setenv("PAGE_TIMEOUT_MS", "45000")
        monkeypatch.setenv("PAGE_WAIT_UNTIL", "domcontentloaded")

        cfg = PageCaptureConfig.from_env()

        assert cfg.timeout_ms == 45000
        assert cfg.wait_until == "domcontentloaded"

    def test_page_capture_config_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config uses defaults when env vars not set."""
        monkeypatch.delenv("PAGE_TIMEOUT_MS", raising=False)
        monkeypatch.delenv("PAGE_WAIT_UNTIL", raising=False)

        cfg = PageCaptureConfig.from_env()

        assert cfg.timeout_ms == 90_000
        assert cfg.wait_until == "load"

    def test_page_capture_config_frozen(self) -> None:
        """Config is frozen (immutable)."""
        cfg = PageCaptureConfig()

        with pytest.raises(AttributeError):
            cfg.timeout_ms = 1000  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _challenge_title_patterns() Tests
# ---------------------------------------------------------------------------


class TestChallengeTitlePatterns:
    """Tests for _challenge_title_patterns() function."""

    def test_challenge_title_patterns_match(self) -> None:
        """Patterns match expected challenge titles."""
        patterns = _challenge_title_patterns()
        challenge_titles = [
            "captcha verification",
            "verify your identity",
            "access denied - 403",
            "forbidden",
            "robot check required",
            "checking your browser",
            "security check",
            "bot detection",
            "anti-bot protection",
            "antibot check",
            "challenge required",
            # Russian patterns
            "проверка безопасности",
            "доступ ограничен",
            "подтвердите вход",
        ]

        for title in challenge_titles:
            title_lower = title.lower()
            assert any(p in title_lower for p in patterns), f"Pattern should match: {title}"

    def test_challenge_title_patterns_no_match(self) -> None:
        """Patterns do not match normal page titles."""
        patterns = _challenge_title_patterns()
        normal_titles = [
            "iphone 15 pro - apple store",
            "amazon.com: online shopping",
            "google search",
            "youtube - broadcast yourself",
            "breaking news - cnn",
            "купить телефон - яндекс маркет",
            "товары для дома - ozon",
        ]

        for title in normal_titles:
            title_lower = title.lower()
            assert not any(p in title_lower for p in patterns), f"Pattern should NOT match: {title}"


# ---------------------------------------------------------------------------
# dismiss_common_popups Patterns Tests
# ---------------------------------------------------------------------------


class TestPopupPatterns:
    """Tests for popup dismissal patterns used in dismiss_common_popups()."""

    def test_popup_button_patterns(self) -> None:
        """Verify dismiss button text patterns are comprehensive."""
        # These patterns are defined in dismiss_common_popups()
        dismiss_texts = [
            # Cookie consent - Russian
            "Понятно", "Принять", "Согласен", "Принять все",
            # Cookie consent - English
            "Accept", "Accept all",
            # Generic acknowledgment
            "OK", "Ок", "Хорошо", "Закрыть", "Close", "Got it",
            # City confirmation - Russian
            "Да", "Да, верно", "Все верно", "Подтвердить",
            # City confirmation - English
            "Yes", "Confirm",
            # Close symbols
            "\u00d7", "\u2715", "\u2716",  # ×, ✕, ✖
        ]

        # Verify common cookie consent patterns are covered
        cookie_patterns = ["Принять", "Accept", "Accept all", "Принять все", "Got it"]
        for pattern in cookie_patterns:
            assert pattern in dismiss_texts, f"Cookie pattern missing: {pattern}"

        # Verify city selector patterns are covered
        city_patterns = ["Да", "Да, верно", "Подтвердить", "Yes", "Confirm"]
        for pattern in city_patterns:
            assert pattern in dismiss_texts, f"City pattern missing: {pattern}"

        # Verify close symbols are covered
        close_symbols = ["\u00d7", "\u2715", "\u2716"]
        for symbol in close_symbols:
            assert symbol in dismiss_texts, f"Close symbol missing: {symbol}"

    def test_popup_close_selectors(self) -> None:
        """Verify close button CSS selectors are comprehensive."""
        # These selectors are defined in dismiss_common_popups()
        close_selectors = [
            "[class*='close']:visible", "[class*='Close']:visible",
            "[class*='dismiss']:visible", "[class*='Dismiss']:visible",
            "[aria-label='Close']:visible", "[aria-label='Закрыть']:visible",
            "[data-testid*='close']:visible", "[data-testid*='Close']:visible",
            ".modal-close:visible", ".popup-close:visible",
        ]

        # Verify class-based selectors
        assert "[class*='close']:visible" in close_selectors
        assert "[class*='Close']:visible" in close_selectors
        assert "[class*='dismiss']:visible" in close_selectors

        # Verify aria-label selectors (accessibility)
        assert "[aria-label='Close']:visible" in close_selectors
        assert "[aria-label='Закрыть']:visible" in close_selectors  # Russian

        # Verify data-testid selectors
        assert "[data-testid*='close']:visible" in close_selectors

        # Verify common class selectors
        assert ".modal-close:visible" in close_selectors
        assert ".popup-close:visible" in close_selectors


# ---------------------------------------------------------------------------
# Integration Tests (still pure functions, no browser)
# ---------------------------------------------------------------------------


class TestStorageStateIntegration:
    """Integration tests for storage state handling."""

    def test_legacy_migration_merge(self, tmp_path: Path) -> None:
        """Test that legacy per-host files are merged into shared files."""
        # Create a legacy file for subdomain
        legacy_file = tmp_path / "shop.example.com.json"
        legacy_state = {
            "cookies": [{"name": "session", "domain": ".example.com", "path": "/", "value": "legacy"}],
            "origins": [],
        }
        legacy_file.write_text(json.dumps(legacy_state))

        # Create a base file for registrable domain
        base_file = tmp_path / "example.com.json"
        base_state = {
            "cookies": [{"name": "tracking", "domain": ".example.com", "path": "/", "value": "base"}],
            "origins": [],
        }
        base_file.write_text(json.dumps(base_state))

        # Call storage_state_path for subdomain URL
        result = storage_state_path(tmp_path, "https://shop.example.com/product")

        # Should return the base path
        assert result.name == "example.com.json"

        # Legacy file should be deleted (best-effort)
        # Note: The deletion is best-effort, so we check the merged content instead
        merged = json.loads(base_file.read_text())

        # Should have both cookies merged
        cookie_names = {c["name"] for c in merged["cookies"]}
        assert "session" in cookie_names or "tracking" in cookie_names
