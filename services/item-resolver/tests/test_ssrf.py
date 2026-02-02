"""Comprehensive SSRF security tests for item-resolver.

Tests cover:
- Private IP ranges (RFC 1918)
- IPv6 loopback and private ranges
- IP encoding bypasses (decimal, octal, hex, URL-encoded)
- IPv6-mapped IPv4 addresses
- Domain variations and unicode
- API endpoint SSRF protection
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.errors import ErrorCode
from app.main import create_app
from app.ssrf import ValidatedURL, validate_public_http_url

if TYPE_CHECKING:
    from collections.abc import Generator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create test client with stub fetcher mode."""
    os.environ["RU_BEARER_TOKEN"] = "test_secret"
    os.environ.pop("SSRF_ALLOWLIST_HOSTS", None)
    yield TestClient(create_app(fetcher_mode="stub"))


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Standard auth headers for API requests."""
    return {"Authorization": "Bearer test_secret"}


# ---------------------------------------------------------------------------
# Private IP Range Tests (RFC 1918 + Special Ranges)
# ---------------------------------------------------------------------------


class TestPrivateIPRanges:
    """Tests for blocking private IP ranges."""

    def test_rejects_private_10_0_0_0(self) -> None:
        """Block 10.0.0.0/8 private range."""
        # Mock DNS resolution to return private IP
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("10.0.0.1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://internal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_private_10_255_255_255(self) -> None:
        """Block upper bound of 10.0.0.0/8 range."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("10.255.255.255")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://internal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_private_172_16(self) -> None:
        """Block 172.16.0.0/12 private range."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("172.16.0.1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://internal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_private_172_31(self) -> None:
        """Block upper bound of 172.16.0.0/12 range (172.31.x.x)."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("172.31.255.255")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://internal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_private_192_168(self) -> None:
        """Block 192.168.0.0/16 private range."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("192.168.1.1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://internal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_private_192_168_255_255(self) -> None:
        """Block upper bound of 192.168.0.0/16 range."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("192.168.255.255")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://internal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_link_local_169_254(self) -> None:
        """Block 169.254.0.0/16 link-local range (AWS metadata, etc)."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("169.254.169.254")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://metadata.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_multicast(self) -> None:
        """Block 224.0.0.0/4 multicast range."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("224.0.0.1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://multicast.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_multicast_upper_bound(self) -> None:
        """Block upper bound of multicast range (239.x.x.x)."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("239.255.255.255")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://multicast.example.com/")
            assert "internal networks" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# IPv6 Tests
# ---------------------------------------------------------------------------


class TestIPv6:
    """Tests for IPv6 address blocking."""

    def test_rejects_ipv6_loopback(self) -> None:
        """Block IPv6 loopback ::1."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("::1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://ipv6host.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_ipv6_loopback_bracketed(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block IPv6 loopback with bracket notation in URL."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://[::1]/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_rejects_ipv6_link_local(self) -> None:
        """Block fe80::/10 link-local range."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("fe80::1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://linklocal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_ipv6_link_local_full(self) -> None:
        """Block fe80::/10 with full address."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("fe80::1:2:3:4")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://linklocal.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_ipv6_private_fc00(self) -> None:
        """Block fc00::/7 unique local addresses."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("fc00::1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://private6.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_ipv6_private_fd00(self) -> None:
        """Block fd00::/8 (subset of fc00::/7)."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("fd00::1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://private6.example.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_ipv6_unspecified(self) -> None:
        """Block unspecified address ::."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("::")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://unspec.example.com/")
            assert "internal networks" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# IP Encoding Bypass Tests
# ---------------------------------------------------------------------------


class TestIPEncodingBypasses:
    """Tests for IP encoding bypass attempts."""

    def test_rejects_decimal_ip(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block decimal IP notation: 2130706433 = 127.0.0.1.

        Decimal encoding: 127*256^3 + 0*256^2 + 0*256 + 1 = 2130706433
        """
        r = client.post(
            "/v1/page_source",
            json={"url": "http://2130706433/"},
            headers=auth_headers,
        )
        # Should be blocked - either as invalid URL or SSRF
        assert r.status_code in (403, 422)

    def test_rejects_decimal_ip_private(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block decimal IP for private range: 167772161 = 10.0.0.1."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://167772161/"},
            headers=auth_headers,
        )
        assert r.status_code in (403, 422)

    def test_rejects_octal_ip(self) -> None:
        """Block octal IP notation via mocked DNS resolution.

        Note: Real DNS resolution may interpret 0177.0.0.1 differently
        (e.g., as 177.0.0.1 on some systems). We test via mock to ensure
        the _is_forbidden_ip check works correctly for loopback addresses.
        """
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            # Simulate DNS returning actual loopback (as some systems might)
            mock_resolve.return_value = [ipaddress.ip_address("127.0.0.1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://0177.0.0.1/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_octal_ip_full(self) -> None:
        """Block full octal notation via mocked DNS resolution.

        Note: Real DNS behavior varies by system. We mock to verify
        the SSRF check correctly blocks loopback addresses regardless
        of how they're represented in the URL.
        """
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("127.0.0.1")]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://0177.0000.0000.0001/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_rejects_hex_ip(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block hex IP notation: 0x7f.0.0.1 = 127.0.0.1."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://0x7f.0.0.1/"},
            headers=auth_headers,
        )
        assert r.status_code in (403, 422)

    def test_rejects_hex_ip_full(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block full hex notation: 0x7f000001 = 127.0.0.1."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://0x7f000001/"},
            headers=auth_headers,
        )
        assert r.status_code in (403, 422)

    def test_rejects_ipv6_mapped_ipv4(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block IPv6-mapped IPv4: ::ffff:127.0.0.1."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://[::ffff:127.0.0.1]/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_rejects_ipv6_mapped_ipv4_private(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block IPv6-mapped private IPv4: ::ffff:10.0.0.1."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://[::ffff:10.0.0.1]/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_rejects_ipv6_mapped_ipv4_hex(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block IPv6-mapped IPv4 in hex: ::ffff:7f00:1 = 127.0.0.1."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://[::ffff:7f00:1]/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_rejects_url_encoded(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block URL-encoded IP: %31%32%37.0.0.1 = 127.0.0.1."""
        # Note: URL encoding in hostname is generally not decoded by urllib
        # but we test anyway for defense in depth
        r = client.post(
            "/v1/page_source",
            json={"url": "http://%31%32%37.0.0.1/"},
            headers=auth_headers,
        )
        # Should be blocked or fail to parse
        assert r.status_code in (403, 422)

    def test_rejects_url_encoded_full(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block fully URL-encoded IP."""
        # %31%32%37%2e%30%2e%30%2e%31 = 127.0.0.1
        r = client.post(
            "/v1/page_source",
            json={"url": "http://%31%32%37%2e%30%2e%30%2e%31/"},
            headers=auth_headers,
        )
        assert r.status_code in (403, 422)

    def test_rejects_mixed_encoding(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block mixed octal/decimal encoding."""
        # 0x7f.0.0.0x1 = 127.0.0.1
        r = client.post(
            "/v1/page_source",
            json={"url": "http://0x7f.0.0.0x1/"},
            headers=auth_headers,
        )
        assert r.status_code in (403, 422)


# ---------------------------------------------------------------------------
# Domain and Protocol Bypass Tests
# ---------------------------------------------------------------------------


class TestDomainBypasses:
    """Tests for domain-based bypass attempts."""

    def test_rejects_case_variations(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Ensure scheme validation is case-insensitive."""
        # HTTP should work (just testing case handling)
        r = client.post(
            "/v1/page_source",
            json={"url": "HTTP://localhost/"},
            headers=auth_headers,
        )
        assert r.status_code == 403  # Still blocked - localhost is blocked

    def test_rejects_scheme_case_ftp(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject FTP regardless of case."""
        r = client.post(
            "/v1/page_source",
            json={"url": "FTP://example.com/"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_file_scheme(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject file:// scheme."""
        r = client.post(
            "/v1/page_source",
            json={"url": "file:///etc/passwd"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_gopher_scheme(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject gopher:// scheme (common SSRF vector)."""
        r = client.post(
            "/v1/page_source",
            json={"url": "gopher://localhost:6379/_INFO"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_dict_scheme(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject dict:// scheme."""
        r = client.post(
            "/v1/page_source",
            json={"url": "dict://localhost:6379/INFO"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_unicode_domain(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test handling of unicode/IDN domains that may resolve to internal IPs."""
        # This tests that unicode normalization doesn't bypass checks
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("127.0.0.1")]
            r = client.post(
                "/v1/page_source",
                json={"url": "http://xn--n3h.example.com/"},
                headers=auth_headers,
            )
            # Should be blocked when it resolves to loopback
            assert r.status_code == 403

    def test_rejects_unicode_localhost_lookalike(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block unicode lookalikes of localhost."""
        # Test various unicode characters that look like ASCII
        urls = [
            "http://lоcalhost/",  # Cyrillic 'o'
            "http://ⓛⓞⓒⓐⓛⓗⓞⓢⓣ/",  # Circled letters
        ]
        for url in urls:
            r = client.post(
                "/v1/page_source",
                json={"url": url},
                headers=auth_headers,
            )
            # Should either fail to resolve or be blocked
            assert r.status_code in (403, 422)

    def test_rejects_dot_local_domain(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block .local mDNS domains."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://myprinter.local/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_rejects_localhost_variants(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block various localhost representations."""
        urls = [
            "http://localhost/",
            "http://localhost.localdomain/",
            "http://127.0.0.1/",
            "http://127.1/",  # Shortened form
            "http://127.0.1/",
        ]
        for url in urls:
            r = client.post(
                "/v1/page_source",
                json={"url": url},
                headers=auth_headers,
            )
            assert r.status_code == 403, f"Expected 403 for {url}"

    def test_rejects_unresolvable_host(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block hosts that cannot be resolved."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://this-domain-definitely-does-not-exist-12345.invalid/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert r.json()["code"] == ErrorCode.SSRF_BLOCKED
        assert "resolve" in r.json()["message"].lower()


# ---------------------------------------------------------------------------
# Allowlist Tests
# ---------------------------------------------------------------------------


class TestAllowlist:
    """Tests for allowlist functionality."""

    def test_accepts_allowlisted_host(self) -> None:
        """Accept hosts on the allowlist without DNS resolution."""
        os.environ["SSRF_ALLOWLIST_HOSTS"] = "trusted.internal.example.com"
        try:
            result = validate_public_http_url("https://trusted.internal.example.com/page")
            assert isinstance(result, ValidatedURL)
            assert result.hostname == "trusted.internal.example.com"
            assert result.scheme == "https"
        finally:
            os.environ.pop("SSRF_ALLOWLIST_HOSTS", None)

    def test_allowlist_case_insensitive(self) -> None:
        """Allowlist matching should be case-insensitive."""
        os.environ["SSRF_ALLOWLIST_HOSTS"] = "Trusted.Example.COM"
        try:
            result = validate_public_http_url("https://trusted.example.com/page")
            assert isinstance(result, ValidatedURL)
        finally:
            os.environ.pop("SSRF_ALLOWLIST_HOSTS", None)

    def test_allowlist_multiple_hosts(self) -> None:
        """Multiple allowlisted hosts separated by comma."""
        os.environ["SSRF_ALLOWLIST_HOSTS"] = "a.example.com, b.example.com, c.example.com"
        try:
            for host in ["a.example.com", "b.example.com", "c.example.com"]:
                result = validate_public_http_url(f"https://{host}/page")
                assert isinstance(result, ValidatedURL)
        finally:
            os.environ.pop("SSRF_ALLOWLIST_HOSTS", None)

    def test_accepts_public_ip(self) -> None:
        """Accept legitimate public IPs."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            # Google's public DNS IP
            mock_resolve.return_value = [ipaddress.ip_address("8.8.8.8")]
            result = validate_public_http_url("http://dns.google/")
            assert isinstance(result, ValidatedURL)

    def test_accepts_public_ip_cloudflare(self) -> None:
        """Accept Cloudflare's public IP."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("1.1.1.1")]
            result = validate_public_http_url("http://cloudflare-dns.com/")
            assert isinstance(result, ValidatedURL)


# ---------------------------------------------------------------------------
# API Endpoint SSRF Tests
# ---------------------------------------------------------------------------


class TestAPIEndpointSSRF:
    """Tests for SSRF protection on API endpoints."""

    def test_page_source_ssrf_blocked(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Verify /v1/page_source blocks SSRF attempts."""
        ssrf_payloads = [
            "http://localhost/",
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://metadata.google.internal/",  # GCP metadata
        ]
        for payload in ssrf_payloads:
            r = client.post(
                "/v1/page_source",
                json={"url": payload},
                headers=auth_headers,
            )
            assert r.status_code == 403, f"Expected 403 for {payload}, got {r.status_code}"
            assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_image_base64_ssrf_blocked(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Verify /v1/image_base64 blocks SSRF attempts."""
        ssrf_payloads = [
            "http://localhost/image.png",
            "http://127.0.0.1/image.png",
            "http://[::1]/image.png",
            "http://10.0.0.1/image.png",
            "http://192.168.1.1/image.png",
            "http://172.16.0.1/image.png",
        ]
        for payload in ssrf_payloads:
            r = client.post(
                "/v1/image_base64",
                json={"url": payload},
                headers=auth_headers,
            )
            assert r.status_code == 403, f"Expected 403 for {payload}, got {r.status_code}"
            assert r.json()["code"] == ErrorCode.SSRF_BLOCKED

    def test_resolve_ssrf_blocked(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Verify /resolver/v1/resolve blocks SSRF attempts."""
        ssrf_payloads = [
            "http://localhost/",
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://169.254.169.254/",
            "http://internal.local/",
        ]
        for payload in ssrf_payloads:
            r = client.post(
                "/resolver/v1/resolve",
                json={"url": payload},
                headers=auth_headers,
            )
            assert r.status_code == 403, f"Expected 403 for {payload}, got {r.status_code}"
            assert r.json()["code"] == ErrorCode.SSRF_BLOCKED


# ---------------------------------------------------------------------------
# Cloud Metadata Service Tests
# ---------------------------------------------------------------------------


class TestCloudMetadata:
    """Tests for blocking cloud metadata service access."""

    def test_blocks_aws_metadata_169_254(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block AWS EC2 metadata service at 169.254.169.254."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_blocks_aws_metadata_imdsv2(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block AWS IMDSv2 endpoint."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://169.254.169.254/latest/api/token"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_blocks_gcp_metadata(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block GCP metadata service."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("169.254.169.254")]
            r = client.post(
                "/v1/page_source",
                json={"url": "http://metadata.google.internal/computeMetadata/v1/"},
                headers=auth_headers,
            )
            assert r.status_code == 403

    def test_blocks_azure_metadata(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block Azure metadata service."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [ipaddress.ip_address("169.254.169.254")]
            r = client.post(
                "/v1/page_source",
                json={"url": "http://169.254.169.254/metadata/instance"},
                headers=auth_headers,
            )
            assert r.status_code == 403


# ---------------------------------------------------------------------------
# DNS Rebinding Protection Tests
# ---------------------------------------------------------------------------


class TestDNSRebinding:
    """Tests for DNS rebinding attack protection."""

    def test_blocks_if_any_ip_is_private(self) -> None:
        """Block if ANY resolved IP is private (defense against DNS rebinding)."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            # Simulate a host that resolves to both public and private IPs
            mock_resolve.return_value = [
                ipaddress.ip_address("8.8.8.8"),  # Public
                ipaddress.ip_address("127.0.0.1"),  # Private - should trigger block
            ]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://rebind.attacker.com/")
            assert "internal networks" in str(exc_info.value).lower()

    def test_blocks_mixed_public_private_ipv6(self) -> None:
        """Block if resolved IPs include private IPv6."""
        with patch("app.ssrf._resolve_all_ips") as mock_resolve:
            import ipaddress

            mock_resolve.return_value = [
                ipaddress.ip_address("8.8.8.8"),  # Public v4
                ipaddress.ip_address("::1"),  # Loopback v6
            ]
            with pytest.raises(Exception) as exc_info:
                validate_public_http_url("http://rebind.attacker.com/")
            assert "internal networks" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Edge Cases and Input Validation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_rejects_empty_url(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject empty URL."""
        r = client.post(
            "/v1/page_source",
            json={"url": ""},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_whitespace_url(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject whitespace-only URL."""
        r = client.post(
            "/v1/page_source",
            json={"url": "   "},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_url_without_hostname(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject URL without hostname."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http:///path/only"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_javascript_scheme(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject javascript: scheme."""
        r = client.post(
            "/v1/page_source",
            json={"url": "javascript:alert(1)"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_rejects_data_scheme(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject data: scheme."""
        r = client.post(
            "/v1/page_source",
            json={"url": "data:text/html,<script>alert(1)</script>"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["code"] == ErrorCode.INVALID_URL

    def test_handles_url_with_auth(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Handle URL with username:password (should still validate host)."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://user:pass@localhost/"},
            headers=auth_headers,
        )
        assert r.status_code == 403  # localhost is blocked

    def test_handles_url_with_port(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Handle URL with non-standard port."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://localhost:8080/"},
            headers=auth_headers,
        )
        assert r.status_code == 403  # localhost is still blocked

    def test_handles_ipv4_with_port(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Handle IPv4 with port."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://127.0.0.1:3000/"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_handles_very_long_url(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Handle very long URLs gracefully."""
        long_path = "a" * 10000
        os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
        try:
            r = client.post(
                "/v1/page_source",
                json={"url": f"https://example.com/{long_path}"},
                headers=auth_headers,
            )
            # Should succeed (allowlisted host) or fail gracefully
            assert r.status_code in (200, 422)
        finally:
            os.environ.pop("SSRF_ALLOWLIST_HOSTS", None)


# ---------------------------------------------------------------------------
# Original Tests (preserved from existing file)
# ---------------------------------------------------------------------------


class TestOriginalSSRFTests:
    """Original tests preserved for backwards compatibility."""

    def test_rejects_localhost(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block localhost hostname."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://localhost/"},
            headers=auth_headers,
        )
        assert r.status_code == 403
        body = r.json()
        assert body["code"] == ErrorCode.SSRF_BLOCKED
        assert "message" in body
        assert "trace_id" in body

    def test_rejects_loopback_ipv4(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block 127.0.0.1 loopback."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://127.0.0.1/"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_rejects_loopback_ipv6(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block ::1 loopback."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://[::1]/"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_rejects_dot_local(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Block .local mDNS domains."""
        r = client.post(
            "/v1/page_source",
            json={"url": "http://printer.local/"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_accepts_public_host_example_dot_com(self) -> None:
        """Allow public hosts when allowlisted."""
        os.environ["RU_BEARER_TOKEN"] = "test_secret"
        os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
        try:
            client = TestClient(create_app(fetcher_mode="stub"))
            r = client.post(
                "/v1/page_source",
                json={"url": "https://example.com/"},
                headers={"Authorization": "Bearer test_secret"},
            )
            assert r.status_code == 200
        finally:
            os.environ.pop("SSRF_ALLOWLIST_HOSTS", None)

    def test_rejects_invalid_url_scheme(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject non-HTTP schemes."""
        r = client.post(
            "/v1/page_source",
            json={"url": "ftp://example.com/"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        body = r.json()
        assert body["code"] == ErrorCode.INVALID_URL
        assert "message" in body
        assert "trace_id" in body

    def test_rejects_empty_url(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Reject empty URL."""
        r = client.post(
            "/v1/page_source",
            json={"url": ""},
            headers=auth_headers,
        )
        assert r.status_code == 422
        body = r.json()
        assert body["code"] == ErrorCode.INVALID_URL
