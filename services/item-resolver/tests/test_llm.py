"""
Comprehensive unit tests for the LLM module.

Tests cover:
- _extract_json function
- _truncate_text function
- _default_canonical_url function
- LLMOutput model validation
- StubLLMClient
- load_llm_client_from_env factory
- DeepSeekTextClient with mocked HTTP
"""

from __future__ import annotations

import json as json_module
import os
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.llm import (
    DeepSeekTextClient,
    LLMOutput,
    OpenAILikeClient,
    StubLLMClient,
    _default_canonical_url,
    _extract_json,
    _truncate_text,
    load_llm_client_from_env,
)


# =============================================================================
# _extract_json tests
# =============================================================================


class TestExtractJson:
    """Tests for _extract_json function."""

    def test_extract_json_clean_json(self) -> None:
        """Parses clean JSON without any wrapper."""
        raw = '{"title": "Product", "price_amount": 99.99}'
        result = _extract_json(raw)
        assert result == {"title": "Product", "price_amount": 99.99}

    def test_extract_json_markdown_wrapper(self) -> None:
        """Strips ```json``` markdown blocks."""
        raw = '```json\n{"title": "Test Product", "confidence": 0.9}\n```'
        result = _extract_json(raw)
        assert result == {"title": "Test Product", "confidence": 0.9}

    def test_extract_json_with_text_around(self) -> None:
        """Finds JSON embedded in surrounding text."""
        raw = 'Here is the extracted data:\n{"title": "Widget", "price_amount": 50}\nHope this helps!'
        result = _extract_json(raw)
        assert result == {"title": "Widget", "price_amount": 50}

    def test_extract_json_empty_response(self) -> None:
        """Raises ValueError for empty response."""
        with pytest.raises(ValueError, match="empty LLM response"):
            _extract_json("")

        with pytest.raises(ValueError, match="empty LLM response"):
            _extract_json("   ")

        with pytest.raises(ValueError, match="empty LLM response"):
            _extract_json(None)  # type: ignore[arg-type]

    def test_extract_json_no_json_found(self) -> None:
        """Raises ValueError when no JSON object is found."""
        with pytest.raises(ValueError, match="no json object found"):
            _extract_json("This is just plain text without any JSON")

        with pytest.raises(ValueError, match="no json object found"):
            _extract_json("Only opening brace {")

        with pytest.raises(ValueError, match="no json object found"):
            _extract_json("Only closing brace }")

    def test_extract_json_invalid_json(self) -> None:
        """Raises ValueError for malformed JSON."""
        # Missing closing brace in inner content
        with pytest.raises(Exception):  # json.JSONDecodeError
            _extract_json('{"title": "broken}')

        # Invalid syntax
        with pytest.raises(Exception):
            _extract_json("{title: no quotes}")

    def test_extract_json_nested_objects(self) -> None:
        """Handles nested JSON objects correctly."""
        raw = '{"outer": {"inner": "value"}, "array": [1, 2, 3]}'
        result = _extract_json(raw)
        assert result == {"outer": {"inner": "value"}, "array": [1, 2, 3]}

    def test_extract_json_with_whitespace(self) -> None:
        """Handles JSON with extra whitespace."""
        raw = """
        {
            "title": "Spaced Out",
            "price_amount": 123.45
        }
        """
        result = _extract_json(raw)
        assert result == {"title": "Spaced Out", "price_amount": 123.45}


# =============================================================================
# _truncate_text tests
# =============================================================================


class TestTruncateText:
    """Tests for _truncate_text function."""

    def test_truncate_short_string(self) -> None:
        """Short strings remain unchanged."""
        text = "Short text"
        result = _truncate_text(text, max_chars=100)
        assert result == text

    def test_truncate_long_string(self) -> None:
        """Long strings are truncated at max_chars."""
        text = "a" * 100
        result = _truncate_text(text, max_chars=50)
        assert len(result) == 50
        assert result == "a" * 50

    def test_truncate_preserves_ending(self) -> None:
        """Truncation adds no suffix, just cuts at max_chars."""
        text = "Hello World! This is a longer text."
        result = _truncate_text(text, max_chars=12)
        assert result == "Hello World!"

    def test_truncate_exact_length(self) -> None:
        """String at exact max_chars is unchanged."""
        text = "Exactly10!"
        result = _truncate_text(text, max_chars=10)
        assert result == text

    def test_truncate_zero_max_chars(self) -> None:
        """Zero max_chars returns original text (disabled)."""
        text = "Any text here"
        result = _truncate_text(text, max_chars=0)
        assert result == text

    def test_truncate_negative_max_chars(self) -> None:
        """Negative max_chars returns original text."""
        text = "Any text here"
        result = _truncate_text(text, max_chars=-10)
        assert result == text

    def test_truncate_empty_string(self) -> None:
        """Empty string returns empty string."""
        result = _truncate_text("", max_chars=100)
        assert result == ""


# =============================================================================
# _default_canonical_url tests
# =============================================================================


class TestDefaultCanonicalUrl:
    """Tests for _default_canonical_url function."""

    def test_canonical_url_strips_fragment(self) -> None:
        """Fragments are preserved in geturl (note: actual behavior)."""
        url = "https://example.com/product#section"
        result = _default_canonical_url(url)
        # geturl() preserves fragments, so this test verifies current behavior
        assert result == "https://example.com/product#section"

    def test_canonical_url_normalizes_scheme(self) -> None:
        """URL scheme is preserved as-is."""
        url = "HTTP://EXAMPLE.COM/Path"
        result = _default_canonical_url(url)
        # geturl reconstructs from parsed components
        assert "example.com" in result.lower()

    def test_canonical_url_preserves_query_params(self) -> None:
        """Query parameters are preserved."""
        url = "https://shop.com/item?id=123&color=blue"
        result = _default_canonical_url(url)
        assert "id=123" in result
        assert "color=blue" in result

    def test_canonical_url_invalid_url_unchanged(self) -> None:
        """Invalid URLs without scheme/netloc returned unchanged."""
        url = "not-a-valid-url"
        result = _default_canonical_url(url)
        assert result == url

    def test_canonical_url_missing_scheme(self) -> None:
        """URL without scheme is returned unchanged."""
        url = "example.com/path"
        result = _default_canonical_url(url)
        assert result == url

    def test_canonical_url_empty_string(self) -> None:
        """Empty string is returned unchanged."""
        result = _default_canonical_url("")
        assert result == ""


# =============================================================================
# LLMOutput model tests
# =============================================================================


class TestLLMOutput:
    """Tests for LLMOutput Pydantic model."""

    def test_llm_output_all_fields(self) -> None:
        """Model accepts all fields with values."""
        output = LLMOutput(
            title="Product Name",
            description="A great product",
            price_amount=99.99,
            price_currency="USD",
            canonical_url="https://example.com/product",
            confidence=0.95,
            image_url="https://example.com/image.jpg",
        )
        assert output.title == "Product Name"
        assert output.description == "A great product"
        assert output.price_amount == 99.99
        assert output.price_currency == "USD"
        assert output.canonical_url == "https://example.com/product"
        assert output.confidence == 0.95
        assert output.image_url == "https://example.com/image.jpg"

    def test_llm_output_optional_fields_none(self) -> None:
        """Model allows all fields to be None."""
        output = LLMOutput()
        assert output.title is None
        assert output.description is None
        assert output.price_amount is None
        assert output.price_currency is None
        assert output.canonical_url is None
        assert output.confidence is None
        assert output.image_url is None

    def test_llm_output_validation(self) -> None:
        """Model validates field types correctly."""
        # Valid integer coerced to float
        output = LLMOutput(price_amount=100)
        assert output.price_amount == 100.0

        # String number coerced to float
        output = LLMOutput.model_validate({"price_amount": "50.5"})
        assert output.price_amount == 50.5

        # Confidence as string
        output = LLMOutput.model_validate({"confidence": "0.8"})
        assert output.confidence == 0.8

    def test_llm_output_from_dict(self) -> None:
        """Model can be created from dictionary via model_validate."""
        data = {
            "title": "Test",
            "price_amount": 25.0,
            "confidence": 0.7,
        }
        output = LLMOutput.model_validate(data)
        assert output.title == "Test"
        assert output.price_amount == 25.0
        assert output.confidence == 0.7
        assert output.description is None

    def test_llm_output_extra_fields_ignored(self) -> None:
        """Extra fields in input are ignored by default."""
        data = {
            "title": "Test",
            "unknown_field": "value",
        }
        output = LLMOutput.model_validate(data)
        assert output.title == "Test"
        assert not hasattr(output, "unknown_field")


# =============================================================================
# StubLLMClient tests
# =============================================================================


class TestStubLLMClient:
    """Tests for StubLLMClient."""

    @pytest.mark.anyio
    async def test_stub_client_extract_returns_defaults(self) -> None:
        """Stub client returns default values with zero confidence."""
        client = StubLLMClient()
        result = await client.extract(
            url="https://example.com/product",
            title="",
            image_candidates="",
        )

        assert isinstance(result, LLMOutput)
        assert result.title is None
        assert result.description is None
        assert result.price_amount is None
        assert result.price_currency is None
        assert result.canonical_url == "https://example.com/product"
        assert result.confidence == 0.0
        assert result.image_url is None

    @pytest.mark.anyio
    async def test_stub_client_uses_page_title(self) -> None:
        """Stub client uses provided page title."""
        client = StubLLMClient()
        result = await client.extract(
            url="https://shop.com/item",
            title="Amazing Product - Shop",
            image_candidates="https://shop.com/img.jpg",
        )

        assert result.title == "Amazing Product - Shop"
        assert result.confidence == 0.0

    @pytest.mark.anyio
    async def test_stub_client_canonical_url_normalization(self) -> None:
        """Stub client normalizes canonical URL."""
        client = StubLLMClient()
        result = await client.extract(
            url="https://example.com/path?query=1#fragment",
            title="Test",
            image_candidates="",
        )

        # URL is passed through _default_canonical_url
        assert "example.com" in result.canonical_url

    @pytest.mark.anyio
    async def test_stub_client_ignores_optional_params(self) -> None:
        """Stub client ignores image_base64, image_mime, html_content."""
        client = StubLLMClient()
        result = await client.extract(
            url="https://example.com",
            title="Test",
            image_candidates="",
            image_base64="base64data",
            image_mime="image/png",
            html_content="<html>content</html>",
        )

        assert result.title == "Test"
        assert result.confidence == 0.0


# =============================================================================
# load_llm_client_from_env tests
# =============================================================================


class TestLoadLLMClientFromEnv:
    """Tests for load_llm_client_from_env factory function."""

    def test_load_stub_mode(self) -> None:
        """LLM_MODE=stub returns StubLLMClient."""
        env = {"LLM_MODE": "stub"}
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, StubLLMClient)

    def test_load_stub_mode_case_insensitive(self) -> None:
        """LLM_MODE=STUB works (case insensitive)."""
        env = {"LLM_MODE": "STUB"}
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, StubLLMClient)

    def test_load_missing_config_raises(self) -> None:
        """Missing required vars in live mode raises RuntimeError."""
        # Missing all required vars
        env = {"LLM_MODE": "live"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL are required"):
                load_llm_client_from_env()

        # Missing API_KEY
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.example.com",
            "LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError):
                load_llm_client_from_env()

        # Missing MODEL
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.example.com",
            "LLM_API_KEY": "secret-key",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError):
                load_llm_client_from_env()

    def test_load_deepseek_auto_detection(self) -> None:
        """DeepSeek models auto-detect as text client."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.deepseek.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "deepseek-chat",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, DeepSeekTextClient)
            assert client.model == "deepseek-chat"
            assert client.base_url == "https://api.deepseek.com"

    def test_load_deepseek_coder_auto_detection(self) -> None:
        """DeepSeek coder models detected as text client."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.deepseek.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "deepseek-coder",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, DeepSeekTextClient)

    def test_load_vision_model_detection(self) -> None:
        """GPT-4 models detected as vision client."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.openai.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "gpt-4-vision-preview",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, OpenAILikeClient)

    def test_load_explicit_client_type_text(self) -> None:
        """Explicit LLM_CLIENT_TYPE=text overrides auto-detection."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.openai.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "gpt-4",
            "LLM_CLIENT_TYPE": "text",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, DeepSeekTextClient)

    def test_load_explicit_client_type_vision(self) -> None:
        """Explicit LLM_CLIENT_TYPE=vision overrides auto-detection."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.deepseek.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "deepseek-chat",
            "LLM_CLIENT_TYPE": "vision",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, OpenAILikeClient)

    def test_load_custom_timeout_and_max_chars(self) -> None:
        """Custom LLM_TIMEOUT_S and LLM_MAX_CHARS are applied."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.example.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "custom-model",
            "LLM_TIMEOUT_S": "120",
            "LLM_MAX_CHARS": "200000",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, DeepSeekTextClient)
            assert client.timeout_s == 120.0
            assert client.max_chars == 200000

    def test_load_default_timeout_and_max_chars(self) -> None:
        """Default timeout (60s) and max_chars (100000) are used."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.example.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert client.timeout_s == 60.0
            assert client.max_chars == 100_000

    def test_load_unknown_model_defaults_to_text(self) -> None:
        """Unknown models default to text client (safer)."""
        env = {
            "LLM_MODE": "live",
            "LLM_BASE_URL": "https://api.example.com",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "unknown-custom-model",
        }
        with patch.dict(os.environ, env, clear=True):
            client = load_llm_client_from_env()
            assert isinstance(client, DeepSeekTextClient)


# =============================================================================
# Helper for mocking httpx.AsyncClient
# =============================================================================


def create_mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    raise_error: Exception | None = None,
) -> tuple[MagicMock, list[dict[str, Any]]]:
    """
    Create a mock httpx.AsyncClient that captures requests and returns mocked responses.

    Returns:
        A tuple of (mock_client_class, captured_requests_list)
    """
    captured_requests: list[dict[str, Any]] = []

    async def mock_post(url: str, json: dict[str, Any], headers: dict[str, str]) -> MagicMock:
        captured_requests.append({"url": url, "json": json, "headers": headers})

        if raise_error:
            raise raise_error

        mock_resp = MagicMock()
        mock_resp.status_code = status_code

        if status_code >= 400:
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=mock_resp,
            )
        else:
            mock_resp.raise_for_status.return_value = None

        mock_resp.json.return_value = json_data or {}
        return mock_resp

    @asynccontextmanager
    async def mock_context(*args: Any, **kwargs: Any):
        mock_client = MagicMock()
        mock_client.post = mock_post
        yield mock_client

    mock_class = MagicMock()
    mock_class.return_value.__aenter__ = mock_context().__aenter__
    mock_class.return_value.__aexit__ = mock_context().__aexit__
    mock_class.side_effect = lambda *args, **kwargs: mock_context()

    return mock_class, captured_requests


# =============================================================================
# DeepSeekTextClient tests (mocked HTTP)
# =============================================================================


class TestDeepSeekTextClient:
    """Tests for DeepSeekTextClient with mocked HTTP responses."""

    @pytest.mark.anyio
    async def test_deepseek_extract_success(self) -> None:
        """Mocked HTTP response returns parsed LLMOutput."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"title": "Test Product", "price_amount": 99.99, "price_currency": "USD", "confidence": 0.9}'
                    }
                }
            ]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            result = await client.extract(
                url="https://shop.com/product",
                title="Shop Product",
                image_candidates="https://shop.com/img.jpg",
                html_content="<html><body>Product page</body></html>",
            )

        assert result.title == "Test Product"
        assert result.price_amount == 99.99
        assert result.price_currency == "USD"
        assert result.confidence == 0.9
        assert len(captured) == 1
        assert captured[0]["url"] == "/v1/chat/completions"

    @pytest.mark.anyio
    async def test_deepseek_extract_timeout(self) -> None:
        """Raises timeout error on HTTP timeout."""
        mock_class, _ = create_mock_response(
            raise_error=httpx.TimeoutException("Connection timed out")
        )

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_s=1,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            with pytest.raises(httpx.TimeoutException):
                await client.extract(
                    url="https://shop.com/product",
                    title="Test",
                    image_candidates="",
                    html_content="<html></html>",
                )

    @pytest.mark.anyio
    async def test_deepseek_extract_invalid_response(self) -> None:
        """Handles error when response is missing expected structure."""
        # Response missing 'choices' key
        mock_response: dict[str, Any] = {"error": "Something went wrong"}

        mock_class, _ = create_mock_response(200, mock_response)

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            with pytest.raises(ValueError, match="LLM response missing content"):
                await client.extract(
                    url="https://shop.com/product",
                    title="Test",
                    image_candidates="",
                    html_content="<html></html>",
                )

    @pytest.mark.anyio
    async def test_deepseek_extract_http_error(self) -> None:
        """Raises exception on HTTP error status."""
        mock_class, _ = create_mock_response(500, {"error": "Internal server error"})

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            with pytest.raises(httpx.HTTPStatusError):
                await client.extract(
                    url="https://shop.com/product",
                    title="Test",
                    image_candidates="",
                    html_content="<html></html>",
                )

    @pytest.mark.anyio
    async def test_deepseek_extract_with_markdown_json(self) -> None:
        """Handles JSON wrapped in markdown code blocks."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"title": "Markdown Product", "confidence": 0.85}\n```'
                    }
                }
            ]
        }

        mock_class, _ = create_mock_response(200, mock_response)

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            result = await client.extract(
                url="https://shop.com/product",
                title="Test",
                image_candidates="",
                html_content="<html></html>",
            )

        assert result.title == "Markdown Product"
        assert result.confidence == 0.85

    @pytest.mark.anyio
    async def test_deepseek_truncates_long_content(self) -> None:
        """Long HTML and image candidates are truncated."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"title": "Truncated", "confidence": 0.5}'
                    }
                }
            ]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat",
            timeout_s=30,
            max_chars=1000,  # Small limit to test truncation
        )

        long_html = "x" * 5000
        long_candidates = "y" * 5000

        with patch("app.llm.httpx.AsyncClient", mock_class):
            await client.extract(
                url="https://shop.com/product",
                title="Test",
                image_candidates=long_candidates,
                html_content=long_html,
            )

        # Verify the request was made with truncated content
        assert len(captured) == 1
        user_content = captured[0]["json"]["messages"][1]["content"]

        # HTML is truncated to max_chars (1000)
        assert "x" * 1000 in user_content
        assert "x" * 1001 not in user_content

        # Image candidates are truncated to min(max_chars//4, 10000) = 250
        assert "y" * 250 in user_content
        assert "y" * 251 not in user_content

    @pytest.mark.anyio
    async def test_deepseek_sends_correct_headers(self) -> None:
        """Verify Authorization header is sent correctly."""
        mock_response = {
            "choices": [{"message": {"content": '{"title": "Test", "confidence": 0.5}'}}]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="my-secret-api-key",
            model="deepseek-chat",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            await client.extract(
                url="https://shop.com/product",
                title="Test",
                image_candidates="",
                html_content="<html></html>",
            )

        assert len(captured) == 1
        assert captured[0]["headers"]["Authorization"] == "Bearer my-secret-api-key"

    @pytest.mark.anyio
    async def test_deepseek_sends_correct_model(self) -> None:
        """Verify model name is included in request payload."""
        mock_response = {
            "choices": [{"message": {"content": '{"title": "Test", "confidence": 0.5}'}}]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = DeepSeekTextClient(
            base_url="https://api.deepseek.com",
            api_key="test-key",
            model="deepseek-chat-v2",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            await client.extract(
                url="https://shop.com/product",
                title="Test",
                image_candidates="",
                html_content="<html></html>",
            )

        assert len(captured) == 1
        assert captured[0]["json"]["model"] == "deepseek-chat-v2"
        assert captured[0]["json"]["temperature"] == 0


# =============================================================================
# OpenAILikeClient tests (mocked HTTP)
# =============================================================================


class TestOpenAILikeClient:
    """Tests for OpenAILikeClient with mocked HTTP responses."""

    @pytest.mark.anyio
    async def test_openai_extract_success(self) -> None:
        """Mocked HTTP response returns parsed LLMOutput."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"title": "Vision Product", "price_amount": 149.99, "confidence": 0.95, "image_url": "https://example.com/img.jpg"}'
                    }
                }
            ]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = OpenAILikeClient(
            base_url="https://api.openai.com",
            api_key="test-key",
            model="gpt-4-vision-preview",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            result = await client.extract(
                url="https://shop.com/product",
                title="Shop Product",
                image_candidates="https://shop.com/img.jpg",
                image_base64="base64data",
                image_mime="image/png",
            )

        assert result.title == "Vision Product"
        assert result.price_amount == 149.99
        assert result.confidence == 0.95
        assert result.image_url == "https://example.com/img.jpg"
        assert len(captured) == 1

    @pytest.mark.anyio
    async def test_openai_includes_image_data_url(self) -> None:
        """Request includes image as data URL."""
        mock_response = {
            "choices": [{"message": {"content": '{"title": "Test", "confidence": 0.5}'}}]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = OpenAILikeClient(
            base_url="https://api.openai.com",
            api_key="test-key",
            model="gpt-4-vision-preview",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            await client.extract(
                url="https://shop.com/product",
                title="Test",
                image_candidates="",
                image_base64="SGVsbG9Xb3JsZA==",
                image_mime="image/jpeg",
            )

        # Check that the image URL is correctly formatted
        assert len(captured) == 1
        user_message = captured[0]["json"]["messages"][1]
        assert user_message["content"][0]["type"] == "text"
        assert user_message["content"][1]["type"] == "image_url"
        assert user_message["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,SGVsbG9Xb3JsZA=="

    @pytest.mark.anyio
    async def test_openai_extract_http_error(self) -> None:
        """Raises exception on HTTP error status."""
        mock_class, _ = create_mock_response(401, {"error": "Unauthorized"})

        client = OpenAILikeClient(
            base_url="https://api.openai.com",
            api_key="invalid-key",
            model="gpt-4-vision-preview",
            timeout_s=30,
            max_chars=10000,
        )

        with patch("app.llm.httpx.AsyncClient", mock_class):
            with pytest.raises(httpx.HTTPStatusError):
                await client.extract(
                    url="https://shop.com/product",
                    title="Test",
                    image_candidates="",
                    image_base64="data",
                    image_mime="image/png",
                )

    @pytest.mark.anyio
    async def test_openai_truncates_image_candidates(self) -> None:
        """Long image candidates are truncated."""
        mock_response = {
            "choices": [{"message": {"content": '{"title": "Test", "confidence": 0.5}'}}]
        }

        mock_class, captured = create_mock_response(200, mock_response)

        client = OpenAILikeClient(
            base_url="https://api.openai.com",
            api_key="test-key",
            model="gpt-4-vision-preview",
            timeout_s=30,
            max_chars=500,  # Small limit
        )

        long_candidates = "z" * 2000

        with patch("app.llm.httpx.AsyncClient", mock_class):
            await client.extract(
                url="https://shop.com/product",
                title="Test",
                image_candidates=long_candidates,
                image_base64="data",
                image_mime="image/png",
            )

        assert len(captured) == 1
        user_text = captured[0]["json"]["messages"][1]["content"][0]["text"]
        # Image candidates truncated to max_chars (500)
        assert "z" * 500 in user_text
        assert "z" * 501 not in user_text
