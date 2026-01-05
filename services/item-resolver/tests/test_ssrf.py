from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    return TestClient(create_app(fetcher_mode="stub"))


def test_rejects_localhost() -> None:
    c = _client()
    r = c.post("/v1/page_source", json={"url": "http://localhost/"}, headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 403


def test_rejects_loopback_ipv4() -> None:
    c = _client()
    r = c.post("/v1/page_source", json={"url": "http://127.0.0.1/"}, headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 403


def test_rejects_loopback_ipv6() -> None:
    c = _client()
    r = c.post("/v1/page_source", json={"url": "http://[::1]/"}, headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 403


def test_rejects_dot_local() -> None:
    c = _client()
    r = c.post("/v1/page_source", json={"url": "http://printer.local/"}, headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 403


def test_accepts_public_host_example_dot_com() -> None:
    # We don't want network access in unit tests, so allowlist this host to bypass DNS.
    os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
    c = _client()
    r = c.post("/v1/page_source", json={"url": "https://example.com/"}, headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 200

