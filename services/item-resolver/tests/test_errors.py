from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.errors import (
    ErrorCode,
    ErrorResponse,
    ResolverError,
    blocked_or_unavailable,
    invalid_url,
    llm_parse_failed,
    ssrf_blocked,
    timeout,
    unknown_error,
)
from app.main import create_app


def _client() -> TestClient:
    os.environ["RU_BEARER_TOKEN"] = "test_token"
    os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
    return TestClient(create_app(fetcher_mode="stub"))


class TestErrorFactories:
    def test_invalid_url_error(self) -> None:
        err = invalid_url("test message")
        assert err.error_code == ErrorCode.INVALID_URL
        assert err.error_message == "test message"
        assert err.status_code == 422

    def test_ssrf_blocked_error(self) -> None:
        err = ssrf_blocked("blocked")
        assert err.error_code == ErrorCode.SSRF_BLOCKED
        assert err.error_message == "blocked"
        assert err.status_code == 403

    def test_blocked_or_unavailable_error(self) -> None:
        err = blocked_or_unavailable("page blocked")
        assert err.error_code == ErrorCode.BLOCKED_OR_UNAVAILABLE
        assert err.error_message == "page blocked"
        assert err.status_code == 502

    def test_timeout_error(self) -> None:
        err = timeout("timed out")
        assert err.error_code == ErrorCode.TIMEOUT
        assert err.error_message == "timed out"
        assert err.status_code == 504

    def test_llm_parse_failed_error(self) -> None:
        err = llm_parse_failed("parse error")
        assert err.error_code == ErrorCode.LLM_PARSE_FAILED
        assert err.error_message == "parse error"
        assert err.status_code == 502

    def test_unknown_error(self) -> None:
        err = unknown_error("something went wrong")
        assert err.error_code == ErrorCode.UNKNOWN_ERROR
        assert err.error_message == "something went wrong"
        assert err.status_code == 500


class TestErrorResponse:
    def test_error_response_model(self) -> None:
        resp = ErrorResponse(
            code="TEST_ERROR",
            message="Test message",
            details={"key": "value"},
            trace_id="abc-123",
        )
        assert resp.code == "TEST_ERROR"
        assert resp.message == "Test message"
        assert resp.details == {"key": "value"}
        assert resp.trace_id == "abc-123"

    def test_error_response_minimal(self) -> None:
        resp = ErrorResponse(code="TEST", message="msg")
        assert resp.code == "TEST"
        assert resp.message == "msg"
        assert resp.details is None
        assert resp.trace_id is None


class TestErrorResponseFormat:
    def test_invalid_url_response_format(self) -> None:
        client = _client()
        r = client.post(
            "/v1/page_source",
            json={"url": "not-a-url"},
            headers={"Authorization": "Bearer test_token"},
        )
        assert r.status_code == 422
        body = r.json()
        assert "code" in body
        assert "message" in body
        assert "trace_id" in body
        assert body["code"] == "INVALID_URL"

    def test_ssrf_blocked_response_format(self) -> None:
        client = _client()
        r = client.post(
            "/v1/page_source",
            json={"url": "http://192.168.1.1/"},
            headers={"Authorization": "Bearer test_token"},
        )
        assert r.status_code == 403
        body = r.json()
        assert body["code"] == "SSRF_BLOCKED"
        assert "message" in body
        assert "trace_id" in body

    def test_error_response_excludes_none_details(self) -> None:
        client = _client()
        r = client.post(
            "/v1/page_source",
            json={"url": ""},
            headers={"Authorization": "Bearer test_token"},
        )
        body = r.json()
        # details should not be present if None
        assert "details" not in body or body.get("details") is None
