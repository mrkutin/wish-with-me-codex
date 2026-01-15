import os

from fastapi.testclient import TestClient

from app.main import create_app


def test_resolve_stub_mode_returns_shape() -> None:
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    os.environ["LLM_MODE"] = "stub"
    os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
    os.environ["LLM_MAX_CHARS"] = "1000"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.post(
        "/resolver/v1/resolve",
        json={"url": "https://example.com/"},
        headers={"Authorization": "Bearer ru_secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {
        "title",
        "description",
        "price_amount",
        "price_currency",
        "canonical_url",
        "confidence",
        "image_url",
        "image_base64",
        "image_mime",
    }
