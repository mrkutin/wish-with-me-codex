import os

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_requires_auth() -> None:
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.get("/healthz")
    assert r.status_code == 401


def test_healthz_rejects_wrong_token() -> None:
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.get("/healthz", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_healthz_accepts_correct_token() -> None:
    os.environ["RU_BEARER_TOKEN"] = "ru_secret"
    client = TestClient(create_app(fetcher_mode="stub"))

    r = client.get("/healthz", headers={"Authorization": "Bearer ru_secret"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

