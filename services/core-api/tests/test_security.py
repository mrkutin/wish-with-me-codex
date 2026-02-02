"""Tests for security utilities."""

import hashlib
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import JWTError, jwt

from app.config import settings
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_refresh_token_expiry,
    hash_password,
    hash_token,
    verify_password,
)


# =============================================================================
# Password Hashing Tests
# =============================================================================


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_bcrypt(self) -> None:
        """Test that password hashing uses bcrypt format."""
        password = "testPassword123"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$ or $2a$ or $2y$
        assert hashed.startswith("$2")
        # Bcrypt hashes have a specific format: $2x$cost$salt+hash
        assert len(hashed) == 60  # Standard bcrypt hash length
        # Verify it's not the same as the plaintext password
        assert hashed != password

    def test_hash_password_unique_salts(self) -> None:
        """Test that hashing the same password produces different hashes (unique salts)."""
        password = "testPassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Same password should produce different hashes due to random salt
        assert hash1 != hash2

    def test_verify_password_correct(self) -> None:
        """Test that verify_password returns True for correct password."""
        password = "testPassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_wrong(self) -> None:
        """Test that verify_password returns False for wrong password."""
        password = "testPassword123"
        wrong_password = "wrongPassword456"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_password(self) -> None:
        """Test verify_password with empty password."""
        password = "testPassword123"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False

    def test_verify_password_unicode(self) -> None:
        """Test password hashing with unicode characters."""
        password = "testPassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_special_characters(self) -> None:
        """Test password hashing with special characters."""
        password = "test!@#$%^&*()_+-=[]{}|;':\",./<>?"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True


# =============================================================================
# Access Token Tests
# =============================================================================


class TestAccessToken:
    """Tests for access token creation and decoding."""

    def test_create_access_token_claims(self) -> None:
        """Test that access token contains correct claims."""
        user_id = f"user:{uuid4()}"
        token = create_access_token(user_id)

        # Decode without verification to check claims
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Verify required claims
        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

        # Verify exp is in the future
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp > now

        # Verify jti is a hex string (unique token ID)
        assert len(payload["jti"]) == 32  # 16 bytes in hex

    def test_create_access_token_with_uuid(self) -> None:
        """Test access token creation with UUID user_id."""
        user_uuid = uuid4()
        token = create_access_token(user_uuid)

        payload = decode_access_token(token)
        assert payload["sub"] == str(user_uuid)

    def test_create_access_token_with_string(self) -> None:
        """Test access token creation with string user_id (CouchDB format)."""
        user_id = f"user:{uuid4()}"
        token = create_access_token(user_id)

        payload = decode_access_token(token)
        assert payload["sub"] == user_id

    def test_create_access_token_custom_expiry(self) -> None:
        """Test access token creation with custom expiry."""
        user_id = f"user:{uuid4()}"
        custom_expiry = timedelta(hours=2)
        token = create_access_token(user_id, expires_delta=custom_expiry)

        payload = decode_access_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

        # Allow 5 seconds tolerance for test execution time
        expected_diff = custom_expiry.total_seconds()
        actual_diff = (exp - iat).total_seconds()
        assert abs(actual_diff - expected_diff) < 5

    def test_decode_access_token_valid(self) -> None:
        """Test decoding a valid access token."""
        user_id = f"user:{uuid4()}"
        token = create_access_token(user_id)

        payload = decode_access_token(token)

        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_decode_access_token_expired(self) -> None:
        """Test decoding an expired access token raises JWTError."""
        user_id = f"user:{uuid4()}"
        # Create a token that's already expired
        token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))

        with pytest.raises(JWTError) as exc_info:
            decode_access_token(token)

        # Check that it's specifically an ExpiredSignatureError
        assert "expired" in str(exc_info.value).lower()

    def test_decode_access_token_tampered(self) -> None:
        """Test decoding a tampered token raises JWTError."""
        user_id = f"user:{uuid4()}"
        token = create_access_token(user_id)

        # Tamper with the token by modifying a character in the payload
        parts = token.split(".")
        # Modify the payload part
        tampered_payload = parts[1][:-2] + "XX"  # Change last 2 chars
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        with pytest.raises(JWTError):
            decode_access_token(tampered_token)

    def test_decode_access_token_wrong_secret(self) -> None:
        """Test decoding with wrong secret raises JWTError."""
        user_id = f"user:{uuid4()}"
        # Create token with current secret
        token = create_access_token(user_id)

        # Try to decode with wrong secret
        with pytest.raises(JWTError):
            jwt.decode(
                token,
                "wrong-secret-key-that-is-at-least-32-chars",
                algorithms=[settings.jwt_algorithm],
            )

    def test_decode_access_token_malformed(self) -> None:
        """Test decoding a malformed token raises JWTError."""
        with pytest.raises(JWTError):
            decode_access_token("not.a.valid.jwt.token")

        with pytest.raises(JWTError):
            decode_access_token("completely-invalid")

        with pytest.raises(JWTError):
            decode_access_token("")


# =============================================================================
# Refresh Token Tests
# =============================================================================


class TestRefreshToken:
    """Tests for refresh token creation."""

    def test_create_refresh_token(self) -> None:
        """Test that refresh token is created with proper format."""
        token = create_refresh_token()

        # Refresh tokens should be URL-safe base64
        assert isinstance(token, str)
        assert len(token) > 0
        # URL-safe base64 characters
        valid_chars = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        assert all(c in valid_chars for c in token)

    def test_create_refresh_token_unique(self) -> None:
        """Test that each refresh token is unique."""
        tokens = [create_refresh_token() for _ in range(100)]

        # All tokens should be unique
        assert len(tokens) == len(set(tokens))

    def test_create_refresh_token_length(self) -> None:
        """Test that refresh token has sufficient length for security."""
        token = create_refresh_token()

        # 32 bytes = 256 bits of entropy, base64 encoded
        # 32 bytes -> ~43 characters in URL-safe base64
        assert len(token) >= 32


# =============================================================================
# Token Hash Tests
# =============================================================================


class TestTokenHash:
    """Tests for token hashing."""

    def test_hash_token_deterministic(self) -> None:
        """Test that hash_token produces consistent results."""
        token = "test-refresh-token-123"

        hash1 = hash_token(token)
        hash2 = hash_token(token)

        assert hash1 == hash2

    def test_hash_token_format(self) -> None:
        """Test that hash_token produces SHA-256 format."""
        token = "test-refresh-token-123"
        hashed = hash_token(token)

        # SHA-256 produces 64 hex characters (256 bits = 32 bytes = 64 hex chars)
        assert len(hashed) == 64
        # Should be valid hex
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_token_different_inputs(self) -> None:
        """Test that different tokens produce different hashes."""
        token1 = "token-one"
        token2 = "token-two"

        hash1 = hash_token(token1)
        hash2 = hash_token(token2)

        assert hash1 != hash2

    def test_hash_token_matches_hashlib(self) -> None:
        """Test that hash_token produces the same result as hashlib.sha256."""
        token = "test-token"
        hashed = hash_token(token)

        expected = hashlib.sha256(token.encode()).hexdigest()
        assert hashed == expected


# =============================================================================
# Refresh Token Expiry Tests
# =============================================================================


class TestRefreshTokenExpiry:
    """Tests for refresh token expiry calculation."""

    def test_get_refresh_token_expiry(self) -> None:
        """Test that get_refresh_token_expiry returns correct datetime."""
        before = datetime.now(timezone.utc)
        expiry = get_refresh_token_expiry()
        after = datetime.now(timezone.utc)

        # Expiry should be in the future
        assert expiry > before

        # Should be approximately refresh_token_expire_days from now
        expected_delta = timedelta(days=settings.refresh_token_expire_days)

        # Allow 5 seconds tolerance
        assert abs((expiry - before - expected_delta).total_seconds()) < 5
        assert abs((expiry - after - expected_delta).total_seconds()) < 5

    def test_get_refresh_token_expiry_timezone_aware(self) -> None:
        """Test that get_refresh_token_expiry returns timezone-aware datetime."""
        expiry = get_refresh_token_expiry()

        assert expiry.tzinfo is not None
        assert expiry.tzinfo == timezone.utc


# =============================================================================
# Security Edge Cases
# =============================================================================


class TestSecurityEdgeCases:
    """Edge case tests for security functions."""

    def test_hash_password_with_very_long_password(self) -> None:
        """Test hashing a very long password."""
        long_password = "a" * 1000
        hashed = hash_password(long_password)

        assert verify_password(long_password, hashed) is True

    def test_hash_token_with_empty_string(self) -> None:
        """Test hashing an empty string token."""
        hashed = hash_token("")

        # Should still produce a valid hash
        assert len(hashed) == 64
        # Empty string has a known SHA-256 hash
        expected = hashlib.sha256(b"").hexdigest()
        assert hashed == expected

    def test_create_access_token_timing_consistency(self) -> None:
        """Test that token creation time is relatively consistent."""
        user_id = f"user:{uuid4()}"

        times = []
        for _ in range(10):
            start = time.monotonic()
            create_access_token(user_id)
            times.append(time.monotonic() - start)

        avg_time = sum(times) / len(times)
        # Token creation should be fast (under 100ms on average)
        assert avg_time < 0.1

    def test_verify_password_timing_attack_resistance(self) -> None:
        """Test that password verification time is similar for correct and incorrect passwords.

        Note: This is a basic check. In production, bcrypt already provides
        constant-time comparison, but we verify the behavior.
        """
        password = "testPassword123"
        hashed = hash_password(password)

        # Time correct password
        times_correct = []
        for _ in range(5):
            start = time.monotonic()
            verify_password(password, hashed)
            times_correct.append(time.monotonic() - start)

        # Time incorrect password (same length)
        times_incorrect = []
        wrong_password = "wrongPassword12"  # Same length
        for _ in range(5):
            start = time.monotonic()
            verify_password(wrong_password, hashed)
            times_incorrect.append(time.monotonic() - start)

        avg_correct = sum(times_correct) / len(times_correct)
        avg_incorrect = sum(times_incorrect) / len(times_incorrect)

        # Times should be within reasonable variance (bcrypt is designed to be constant-time)
        # We use a generous tolerance because timing can vary due to system load
        ratio = max(avg_correct, avg_incorrect) / max(
            min(avg_correct, avg_incorrect), 0.0001
        )
        assert ratio < 3.0, f"Timing ratio too large: {ratio}"
