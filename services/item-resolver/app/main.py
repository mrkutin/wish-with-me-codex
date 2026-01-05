from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .auth import require_bearer_token
from .browser_manager import load_manager_from_env, open_browser
from .fetcher import PlaywrightFetcher, StubFetcher, fetcher_mode_from_env
from .scrape import PageCaptureConfig
from .ssrf import validate_public_http_url


class UrlIn(BaseModel):
    url: str = Field(..., description="Target URL")


class PageSourceOut(BaseModel):
    html: str


class ImageBase64Out(BaseModel):
    content_type: str
    image_base64: str


def _storage_dir() -> Path:
    return Path(os.environ.get("STORAGE_STATE_DIR") or "storage_state")


def _configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    level = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    logging.basicConfig(level=level)


def create_app(*, fetcher_mode: str | None = None) -> FastAPI:
    _configure_logging()
    mode = (fetcher_mode or fetcher_mode_from_env()).strip().lower()
    mode = "stub" if mode == "stub" else "playwright"
    manager = load_manager_from_env()
    cfg = PageCaptureConfig()
    storage_dir = _storage_dir()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if mode == "stub":
            app.state.fetcher = StubFetcher()
            yield
            return

        async with open_browser(headless=manager.headless, channel=manager.channel) as (_pw, browser):
            app.state.fetcher = PlaywrightFetcher(manager=manager, browser=browser, storage_state_dir=storage_dir, cfg=cfg)
            yield

    app = FastAPI(title="item-resolver", version="0.1.0", lifespan=lifespan)

    @app.get("/healthz", dependencies=[Depends(require_bearer_token)])
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/v1/page_source", response_model=PageSourceOut, dependencies=[Depends(require_bearer_token)])
    async def page_source(payload: UrlIn) -> PageSourceOut:
        validate_public_http_url(payload.url)
        fetcher = getattr(app.state, "fetcher", None)
        if fetcher is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Fetcher not initialized")
        _final_url, _title, html, _saved = await fetcher.fetch_page_source(url=payload.url)
        return PageSourceOut(
            html=html,
        )

    @app.post("/v1/image_base64", response_model=ImageBase64Out, dependencies=[Depends(require_bearer_token)])
    async def image_base64(payload: UrlIn) -> ImageBase64Out:
        validate_public_http_url(payload.url)
        fetcher = getattr(app.state, "fetcher", None)
        if fetcher is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Fetcher not initialized")
        _final_url, content_type, b64 = await fetcher.fetch_image_base64(url=payload.url)
        return ImageBase64Out(
            content_type=content_type,
            image_base64=b64,
        )

    return app


app = create_app()
