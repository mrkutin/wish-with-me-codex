import os

from fastapi.testclient import TestClient

from app.main import create_app


def test_missing_body_is_422() -> None:
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.post("/v1/page_source", headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 422


def test_response_shape_page_source() -> None:
    os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.post(
        "/v1/page_source",
        json={"url": "https://example.com/"},
        headers={"Authorization": "Bearer ru_secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"html"}


def test_response_shape_image_base64() -> None:
    os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.post(
        "/v1/image_base64",
        json={"url": "https://example.com/image.jpg"},
        headers={"Authorization": "Bearer ru_secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"content_type", "image_base64"}
    assert body["image_base64"].startswith("data:") or body["image_base64"] == ""
