from __future__ import annotations

import base64
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .auth import require_bearer_token
from .browser_manager import load_manager_from_env, open_browser
from .fetcher import PlaywrightFetcher, StubFetcher, fetcher_mode_from_env
from .image_utils import crop_screenshot_to_content, image_data_url
from .llm import load_llm_client_from_env
from .scrape import PageCaptureConfig, capture_page_source, storage_state_path
from .ssrf import validate_public_http_url


class UrlIn(BaseModel):
    url: str = Field(..., description="Target URL")


class PageSourceOut(BaseModel):
    html: str


class ImageBase64Out(BaseModel):
    content_type: str
    image_base64: str


class ResolveOut(BaseModel):
    title: str | None
    description: str | None
    price_amount: float | None
    price_currency: str | None
    canonical_url: str | None
    confidence: float
    image_url: str | None
    image_base64: str | None
    image_mime: str | None


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
    if mode == "stub":
        app.state.fetcher = StubFetcher()

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
        data_url = image_data_url(b64, content_type) or b64
        return ImageBase64Out(
            content_type=content_type,
            image_base64=data_url,
        )

    @app.post("/resolver/v1/resolve", response_model=ResolveOut, dependencies=[Depends(require_bearer_token)])
    async def resolve(payload: UrlIn) -> ResolveOut:
        validate_public_http_url(payload.url)
        fetcher = getattr(app.state, "fetcher", None)
        if fetcher is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Resolver not initialized")

        llm_client = getattr(app.state, "llm_client", None)
        if llm_client is None:
            try:
                llm_client = load_llm_client_from_env()
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"code": "UNKNOWN_ERROR", "message": str(exc)},
                ) from exc
            app.state.llm_client = llm_client

        if isinstance(fetcher, PlaywrightFetcher):
            state_path = storage_state_path(fetcher.storage_state_dir, payload.url)
            async with fetcher.manager.semaphore:
                context = await fetcher.manager.make_context(
                    fetcher.browser,
                    url=payload.url,
                    storage_state_path=state_path,
                )
                try:
                    page = await context.new_page()
                    final_url, page_title, html = await capture_page_source(page, payload.url, cfg=fetcher.cfg)
                    page_shot = await page.screenshot(full_page=True, type="jpeg", quality=75)
                    page_b64 = base64.b64encode(page_shot).decode("ascii")
                    page_mime = "image/jpeg"
                    try:
                        await context.storage_state(path=str(state_path))
                    except Exception:
                        pass
                    try:
                        llm_out = await llm_client.extract(
                            url=final_url or payload.url,
                            title=page_title,
                            html=html,
                            image_base64=page_b64,
                            image_mime=page_mime,
                        )
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail={"code": "LLM_PARSE_FAILED", "message": str(exc)},
                        ) from exc
                    except Exception as exc:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail={"code": "UNKNOWN_ERROR", "message": "LLM extraction failed"},
                        ) from exc

                    image_b64: str | None = None
                    image_mime: str | None = None
                    image_url = llm_out.image_url
                    resolved_image_url: str | None = None
                    if image_url:
                        resolved = urljoin(final_url or payload.url, image_url)
                        validate_public_http_url(resolved)
                        resolved_image_url = resolved
                        image_page = await context.new_page()
                        try:
                            await image_page.goto(
                                resolved,
                                wait_until="load",
                                timeout=fetcher.cfg.timeout_ms,
                            )
                            try:
                                await image_page.wait_for_load_state(
                                    "networkidle",
                                    timeout=fetcher.cfg.timeout_ms,
                                )
                            except Exception:
                                pass
                            image_shot = await image_page.screenshot(full_page=True, type="png")
                            cropped = crop_screenshot_to_content(image_shot)
                            image_b64 = base64.b64encode(cropped).decode("ascii")
                            image_mime = "image/jpeg"
                            try:
                                await context.storage_state(path=str(state_path))
                            except Exception:
                                pass
                        finally:
                            try:
                                await image_page.close()
                            except Exception:
                                pass
                finally:
                    try:
                        await context.close()
                    except Exception:
                        pass
        else:
            final_url, page_title, html, image_mime, screenshot_b64, _saved = await fetcher.fetch_page_snapshot(
                url=payload.url
            )
            try:
                llm_out = await llm_client.extract(
                    url=final_url or payload.url,
                    title=page_title,
                    html=html,
                    image_base64=screenshot_b64,
                    image_mime=image_mime,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"code": "LLM_PARSE_FAILED", "message": str(exc)},
                ) from exc
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"code": "UNKNOWN_ERROR", "message": "LLM extraction failed"},
                ) from exc

            image_b64 = None
            image_mime = None
            image_url = llm_out.image_url
            resolved_image_url = None
            if image_url:
                resolved = urljoin(final_url or payload.url, image_url)
                validate_public_http_url(resolved)
                resolved_image_url = resolved
                _img_final, content_type, b64 = await fetcher.fetch_image_base64(
                    url=resolved,
                    session_url=final_url or payload.url,
                )
                image_mime = content_type or None
                image_b64 = b64 or None

        confidence = llm_out.confidence if llm_out.confidence is not None else 0.0
        image_data = image_data_url(image_b64, image_mime)
        return ResolveOut(
            title=llm_out.title,
            description=llm_out.description,
            price_amount=llm_out.price_amount,
            price_currency=llm_out.price_currency,
            canonical_url=llm_out.canonical_url,
            confidence=confidence,
            image_url=resolved_image_url,
            image_base64=image_data,
            image_mime=image_mime,
        )

    return app


app = create_app()
