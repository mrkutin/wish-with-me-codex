from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from playwright.async_api import Browser

from .browser_manager import BrowserManager
from .scrape import PageCaptureConfig, capture_page_source, storage_state_path


class PageSourceFetcher(Protocol):
    async def fetch_page_source(self, *, url: str) -> tuple[str, str, str, bool]:
        """Returns (final_url, title, html, storage_state_saved)."""

    async def fetch_page_snapshot(self, *, url: str) -> tuple[str, str, str, str, str, bool]:
        """Returns (final_url, title, html, image_mime, image_base64, storage_state_saved)."""

    async def fetch_image_base64(self, *, url: str, session_url: str | None = None) -> tuple[str, str, str]:
        """Returns (final_url, content_type, image_base64)."""


@dataclass
class StubFetcher:
    async def fetch_page_source(self, *, url: str) -> tuple[str, str, str, bool]:
        return url, "", "", False

    async def fetch_page_snapshot(self, *, url: str) -> tuple[str, str, str, str, str, bool]:
        return url, "", "", "image/jpeg", "", False

    async def fetch_image_base64(self, *, url: str, session_url: str | None = None) -> tuple[str, str, str]:
        _ = session_url
        return url, "", ""


@dataclass
class PlaywrightFetcher:
    manager: BrowserManager
    browser: Browser
    storage_state_dir: Path
    cfg: PageCaptureConfig

    async def fetch_page_source(self, *, url: str) -> tuple[str, str, str, bool]:
        state_path = storage_state_path(self.storage_state_dir, url)

        async with self.manager.semaphore:
            context = await self.manager.make_context(self.browser, url=url, storage_state_path=state_path)
            page = await context.new_page()
            try:
                final_url, title, html = await capture_page_source(page, url, cfg=self.cfg)
                try:
                    await context.storage_state(path=str(state_path))
                    saved = True
                except Exception:
                    saved = False
                return final_url, title, html, saved
            finally:
                try:
                    await context.close()
                except Exception:
                    pass

    async def fetch_page_snapshot(self, *, url: str) -> tuple[str, str, str, str, str, bool]:
        state_path = storage_state_path(self.storage_state_dir, url)

        async with self.manager.semaphore:
            context = await self.manager.make_context(self.browser, url=url, storage_state_path=state_path)
            page = await context.new_page()
            try:
                final_url, title, html = await capture_page_source(page, url, cfg=self.cfg)
                screenshot = await page.screenshot(full_page=True, type="jpeg", quality=75)
                b64 = base64.b64encode(screenshot).decode("ascii")
                try:
                    await context.storage_state(path=str(state_path))
                    saved = True
                except Exception:
                    saved = False
                return final_url, title, html, "image/jpeg", b64, saved
            finally:
                try:
                    await context.close()
                except Exception:
                    pass

    async def fetch_image_base64(self, *, url: str, session_url: str | None = None) -> tuple[str, str, str]:
        # Reuse the page session when provided (some CDNs gate by cookies).
        state_path = storage_state_path(self.storage_state_dir, session_url or url)

        async with self.manager.semaphore:
            context = await self.manager.make_context(self.browser, url=url, storage_state_path=state_path)
            page = await context.new_page()
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=self.cfg.timeout_ms)
                if resp is None:
                    return page.url, "", ""
                content_type = (resp.headers or {}).get("content-type", "") or ""
                body = await resp.body()
                b64 = base64.b64encode(body).decode("ascii")
                try:
                    await context.storage_state(path=str(state_path))
                except Exception:
                    pass
                return page.url, content_type, b64
            finally:
                try:
                    await context.close()
                except Exception:
                    pass


def fetcher_mode_from_env() -> Literal["playwright", "stub"]:
    mode = (os.environ.get("RU_FETCHER_MODE") or "playwright").strip().lower()
    return "stub" if mode == "stub" else "playwright"
