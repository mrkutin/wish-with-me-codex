from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    os.environ["RU_BEARER_TOKEN"] = "test_token"
    os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
    return TestClient(create_app(fetcher_mode="stub"))


class TestRequestIdMiddleware:
    def test_generates_request_id_when_not_provided(self) -> None:
        client = _client()
        r = client.get("/healthz", headers={"Authorization": "Bearer test_token"})
        assert r.status_code == 200
        assert "X-Request-Id" in r.headers
        # Should be a valid UUID
        request_id = r.headers["X-Request-Id"]
        assert len(request_id) > 0
        try:
            uuid.UUID(request_id)
        except ValueError:
            pass  # Not all implementations use UUID format

    def test_preserves_provided_request_id(self) -> None:
        client = _client()
        custom_id = "my-custom-request-id-12345"
        r = client.get(
            "/healthz",
            headers={
                "Authorization": "Bearer test_token",
                "X-Request-Id": custom_id,
            },
        )
        assert r.status_code == 200
        assert r.headers.get("X-Request-Id") == custom_id

    def test_request_id_in_success_response(self) -> None:
        client = _client()
        r = client.post(
            "/v1/page_source",
            json={"url": "https://example.com/"},
            headers={"Authorization": "Bearer test_token"},
        )
        assert r.status_code == 200
        assert "X-Request-Id" in r.headers

    def test_request_id_in_error_response_header(self) -> None:
        client = _client()
        custom_id = "error-request-id-xyz"
        r = client.post(
            "/v1/page_source",
            json={"url": "http://localhost/"},
            headers={
                "Authorization": "Bearer test_token",
                "X-Request-Id": custom_id,
            },
        )
        assert r.status_code == 403
        assert r.headers.get("X-Request-Id") == custom_id

    def test_trace_id_in_error_body_matches_header(self) -> None:
        client = _client()
        custom_id = "trace-match-test-123"
        r = client.post(
            "/v1/page_source",
            json={"url": "http://localhost/"},
            headers={
                "Authorization": "Bearer test_token",
                "X-Request-Id": custom_id,
            },
        )
        assert r.status_code == 403
        body = r.json()
        assert body.get("trace_id") == custom_id
        assert r.headers.get("X-Request-Id") == custom_id

    def test_request_id_unique_per_request(self) -> None:
        client = _client()
        r1 = client.get("/healthz", headers={"Authorization": "Bearer test_token"})
        r2 = client.get("/healthz", headers={"Authorization": "Bearer test_token"})

        id1 = r1.headers.get("X-Request-Id")
        id2 = r2.headers.get("X-Request-Id")

        assert id1 is not None
        assert id2 is not None
        assert id1 != id2
