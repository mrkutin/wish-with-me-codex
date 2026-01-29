from __future__ import annotations

import asyncio
import base64
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin

from fastapi import Depends, FastAPI
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field

from .auth import require_bearer_token
from .browser_manager import load_manager_from_env, open_browser
from .changes_watcher import start_watcher, stop_watcher
from .errors import blocked_or_unavailable, llm_parse_failed, timeout, unknown_error
from .fetcher import PlaywrightFetcher, StubFetcher, fetcher_mode_from_env
from .html_optimizer import format_html_for_llm
from .html_parser import extract_images_from_html, format_images_for_llm
from .image_utils import crop_screenshot_to_content, image_data_url
from .llm import load_llm_client_from_env
from .logging_config import configure_logging
from .middleware import setup_middleware
from .scrape import PageCaptureConfig, capture_page_source, looks_like_interstitial_or_challenge, storage_state_path
from .ssrf import validate_public_http_url
from .timing import TimingStats, measure_time


class UrlIn(BaseModel):
    url: str = Field(..., description="Target URL")


class PageSourceOut(BaseModel):
    html: str


class ImageBase64Out(BaseModel):
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


logger = logging.getLogger(__name__)


def _storage_dir() -> Path:
    return Path(os.environ.get("STORAGE_STATE_DIR") or "storage_state")


def create_app(*, fetcher_mode: str | None = None) -> FastAPI:
    configure_logging()
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

            # Start CouchDB changes watcher if enabled
            watcher_enabled = os.environ.get("COUCHDB_WATCHER_ENABLED", "true").lower() == "true"
            if watcher_enabled:
                try:
                    llm_client = load_llm_client_from_env()
                    app.state.llm_client = llm_client
                    await start_watcher(
                        llm_client=llm_client,
                        manager=manager,
                        browser=browser,
                        storage_state_dir=str(storage_dir),
                    )
                    logger.info("CouchDB changes watcher started")
                except Exception as e:
                    logger.warning(f"Failed to start CouchDB watcher: {e}")

            try:
                yield
            finally:
                # Stop watcher on shutdown
                if watcher_enabled:
                    await stop_watcher()
                    logger.info("CouchDB changes watcher stopped")

    app = FastAPI(title="item-resolver", version="0.1.0", lifespan=lifespan)
    setup_middleware(app)
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
            raise unknown_error("Fetcher not initialized")
        try:
            _final_url, _title, html, _saved = await fetcher.fetch_page_source(url=payload.url)
        except PlaywrightTimeoutError as exc:
            raise timeout(f"Page load timed out: {payload.url}") from exc
        except asyncio.TimeoutError as exc:
            raise timeout(f"Page load timed out: {payload.url}") from exc
        except Exception as exc:
            logger.exception("Failed to fetch page source for %s", payload.url)
            raise unknown_error(f"Failed to fetch page: {exc}") from exc
        return PageSourceOut(html=html)

    @app.post("/v1/image_base64", response_model=ImageBase64Out, dependencies=[Depends(require_bearer_token)])
    async def image_base64(payload: UrlIn) -> ImageBase64Out:
        validate_public_http_url(payload.url)
        fetcher = getattr(app.state, "fetcher", None)
        if fetcher is None:
            raise unknown_error("Fetcher not initialized")
        try:
            _final_url, content_type, b64 = await fetcher.fetch_image_base64(url=payload.url)
        except PlaywrightTimeoutError as exc:
            raise timeout(f"Image load timed out: {payload.url}") from exc
        except asyncio.TimeoutError as exc:
            raise timeout(f"Image load timed out: {payload.url}") from exc
        except Exception as exc:
            logger.exception("Failed to fetch image for %s", payload.url)
            raise unknown_error(f"Failed to fetch image: {exc}") from exc
        data_url = image_data_url(b64, content_type) or b64
        return ImageBase64Out(image_base64=data_url)

    @app.post("/resolver/v1/resolve", response_model=ResolveOut, dependencies=[Depends(require_bearer_token)])
    async def resolve(payload: UrlIn) -> ResolveOut:
        stats = TimingStats()

        async with measure_time(stats, "url_validation"):
            validate_public_http_url(payload.url)

        fetcher = getattr(app.state, "fetcher", None)
        if fetcher is None:
            raise unknown_error("Resolver not initialized")

        llm_client = getattr(app.state, "llm_client", None)
        if llm_client is None:
            try:
                llm_client = load_llm_client_from_env()
            except RuntimeError as exc:
                raise unknown_error(str(exc)) from exc
            app.state.llm_client = llm_client

        if isinstance(fetcher, PlaywrightFetcher):
            state_path = storage_state_path(fetcher.storage_state_dir, payload.url)
            async with fetcher.manager.semaphore:
                async with measure_time(stats, "browser_context_create"):
                    context = await fetcher.manager.make_context(
                        fetcher.browser,
                        url=payload.url,
                        storage_state_path=state_path,
                    )
                try:
                    page = await context.new_page()
                    try:
                        async with measure_time(stats, "page_navigation"):
                            final_url, page_title, html = await capture_page_source(page, payload.url, cfg=fetcher.cfg)
                    except PlaywrightTimeoutError as exc:
                        raise timeout(f"Page load timed out: {payload.url}") from exc
                    except asyncio.TimeoutError as exc:
                        raise timeout(f"Page load timed out: {payload.url}") from exc

                    # Check for challenge pages but be lenient if there's actual content
                    if looks_like_interstitial_or_challenge(page_title, html):
                        # Check if there's actually substantial content despite challenge indicators
                        # Some sites leave challenge traces in the HTML even after loading real content
                        body_text_len = len(html) if html else 0
                        has_product_indicators = any(ind in html.lower() for ind in [
                            'price', 'цена', 'корзин', 'cart', 'buy', 'купить', 'добавить',
                            'product', 'товар', '₽', 'руб', 'rub'
                        ]) if html else False

                        if body_text_len < 5000 and not has_product_indicators:
                            logger.warning("Page appears blocked or shows challenge: %s (html_len=%d)", payload.url, body_text_len)
                            raise blocked_or_unavailable(f"Page blocked or requires verification: {payload.url}")
                        else:
                            logger.info("Challenge indicators found but page has content, proceeding: %s (html_len=%d)", payload.url, body_text_len)

                    async with measure_time(stats, "page_screenshot"):
                        page_shot = await page.screenshot(full_page=False, type="jpeg", quality=75)
                        page_b64 = base64.b64encode(page_shot).decode("ascii")
                        page_mime = "image/jpeg"

                    try:
                        await context.storage_state(path=str(state_path))
                    except Exception:
                        pass

                    async with measure_time(stats, "image_extraction"):
                        images = extract_images_from_html(html, base_url=final_url or payload.url)
                        image_candidates = format_images_for_llm(images, max_images=20)

                    async with measure_time(stats, "html_optimization"):
                        html_content = format_html_for_llm(
                            html=html,
                            url=final_url or payload.url,
                            title=page_title,
                            max_chars=int(os.environ.get("LLM_MAX_CHARS") or 50000),
                        )

                    try:
                        async with measure_time(stats, "llm_extraction"):
                            llm_out = await llm_client.extract(
                                url=final_url or payload.url,
                                title=page_title,
                                image_candidates=image_candidates,
                                image_base64=page_b64,
                                image_mime=page_mime,
                                html_content=html_content,
                            )
                    except ValueError as exc:
                        raise llm_parse_failed(str(exc)) from exc
                    except Exception as exc:
                        logger.exception("LLM extraction failed for %s", payload.url)
                        raise unknown_error("LLM extraction failed") from exc

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
                            try:
                                async with measure_time(stats, "image_navigation"):
                                    await image_page.goto(
                                        resolved,
                                        wait_until="load",
                                        timeout=fetcher.cfg.timeout_ms,
                                    )
                                    await image_page.wait_for_load_state(
                                        "networkidle",
                                        timeout=fetcher.cfg.timeout_ms,
                                    )
                            except PlaywrightTimeoutError:
                                logger.warning("Image load timed out: %s", resolved)
                            else:
                                async with measure_time(stats, "image_screenshot"):
                                    image_shot = await image_page.screenshot(full_page=True, type="png")

                                async with measure_time(stats, "image_crop"):
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
            try:
                async with measure_time(stats, "page_snapshot"):
                    final_url, page_title, html, image_mime, screenshot_b64, _saved = await fetcher.fetch_page_snapshot(
                        url=payload.url
                    )
            except PlaywrightTimeoutError as exc:
                raise timeout(f"Page load timed out: {payload.url}") from exc
            except asyncio.TimeoutError as exc:
                raise timeout(f"Page load timed out: {payload.url}") from exc

            async with measure_time(stats, "image_extraction"):
                images = extract_images_from_html(html, base_url=final_url or payload.url)
                image_candidates = format_images_for_llm(images, max_images=20)

            async with measure_time(stats, "html_optimization"):
                html_content = format_html_for_llm(
                    html=html,
                    url=final_url or payload.url,
                    title=page_title,
                    max_chars=int(os.environ.get("LLM_MAX_CHARS") or 50000),
                )

            try:
                async with measure_time(stats, "llm_extraction"):
                    llm_out = await llm_client.extract(
                        url=final_url or payload.url,
                        title=page_title,
                        image_candidates=image_candidates,
                        image_base64=screenshot_b64,
                        image_mime=image_mime,
                        html_content=html_content,
                    )
            except ValueError as exc:
                raise llm_parse_failed(str(exc)) from exc
            except Exception as exc:
                logger.exception("LLM extraction failed for %s", payload.url)
                raise unknown_error("LLM extraction failed") from exc

            image_b64 = None
            image_mime = None
            image_url = llm_out.image_url
            resolved_image_url = None
            if image_url:
                resolved = urljoin(final_url or payload.url, image_url)
                validate_public_http_url(resolved)
                resolved_image_url = resolved
                try:
                    async with measure_time(stats, "image_fetch"):
                        _img_final, content_type, b64 = await fetcher.fetch_image_base64(
                            url=resolved,
                            session_url=final_url or payload.url,
                        )
                        image_mime = content_type or None
                        image_b64 = b64 or None
                except Exception:
                    logger.warning("Failed to fetch image: %s", resolved, exc_info=True)

        stats.log_summary(payload.url)

        async with measure_time(stats, "response_preparation"):
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
        )

    return app


app = create_app()
