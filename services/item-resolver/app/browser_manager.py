from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Dict, List, Literal, Optional, Tuple, Union
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright
from playwright_stealth import Stealth


# Keep aligned with repo defaults (RU locale).
STEALTH = Stealth(navigator_languages_override=("ru-RU", "ru", "en-US", "en"))
LOGGER = logging.getLogger(__name__)

WaitUntil = Literal["domcontentloaded", "load", "networkidle"]


@dataclass(frozen=True)
class BrowserProfile:
    user_agent: str
    viewport: Dict[str, int]
    locale: str = "ru-RU"
    timezone_id: str = "Europe/Moscow"
    is_mobile: bool = False
    has_touch: bool = False
    geolocation: Optional[Dict[str, float]] = None


DEFAULT_PROFILE = BrowserProfile(
    user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    viewport={"width": 1920, "height": 1080},
    geolocation={"latitude": 55.7558, "longitude": 37.6173, "accuracy": 100.0},
)


def default_headers() -> Dict[str, str]:
    return {
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


def cookies_for_host(hostname: str) -> List[Dict[str, str]]:
    now = str(int(time.time()))
    cookies: List[Dict[str, str]] = []

    if hostname.endswith("market.yandex.ru") or hostname.endswith("yandex.ru"):
        cookies.extend(
            [
                {"name": "_ym_uid", "value": now, "domain": ".market.yandex.ru", "path": "/"},
                {"name": "_ym_d", "value": now, "domain": ".market.yandex.ru", "path": "/"},
                {"name": "yandexuid", "value": now, "domain": ".yandex.ru", "path": "/"},
                {"name": "yuidss", "value": str(random.randint(1, 1_000_000_000)), "domain": ".yandex.ru", "path": "/"},
                {"name": "i", "value": now, "domain": ".yandex.ru", "path": "/"},
                {"name": "yandex_gid", "value": "213", "domain": ".yandex.ru", "path": "/"},
                {"name": "_ym_isad", "value": "2", "domain": ".market.yandex.ru", "path": "/"},
            ]
        )

    if hostname.endswith("aliexpress.ru"):
        cookies.append(
            {
                "name": "aep_usuc_f",
                "value": "site=rus&c_tp=RUB&region=RU&b_locale=ru_RU",
                "domain": ".aliexpress.ru",
                "path": "/",
            }
        )
    return cookies


def chromium_launch_args() -> List[str]:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins",
        "--disable-site-isolation-trials",
        "--window-size=1920,1080",
    ]
    if (os.environ.get("PROXY_IGNORE_CERT_ERRORS") or "").strip().lower() in ("1", "true", "yes"):
        # Some proxies MITM TLS; allow invalid proxy certs when explicitly enabled.
        args.append("--ignore-certificate-errors")
    return args


def proxy_from_env() -> Optional[Dict[str, str]]:
    server = (os.environ.get("PROXY_SERVER") or "").strip()
    if not server:
        return None

    proxy: Dict[str, str] = {"server": server}
    username = (os.environ.get("PROXY_USERNAME") or "").strip()
    password = (os.environ.get("PROXY_PASSWORD") or "").strip()
    bypass = (os.environ.get("PROXY_BYPASS") or "").strip()
    if username:
        proxy["username"] = username
    if password:
        proxy["password"] = password
    if bypass:
        proxy["bypass"] = bypass
    return proxy


async def new_context(
    browser: Browser,
    url: str,
    *,
    profile: BrowserProfile = DEFAULT_PROFILE,
    extra_headers: Optional[Dict[str, str]] = None,
    storage_state_path: Optional[Union[str, Path]] = None,
) -> BrowserContext:
    storage_state: Optional[str] = None
    if storage_state_path is not None:
        p = Path(storage_state_path)
        if p.exists():
            storage_state = str(p)

    ctx_kwargs: Dict[str, object] = {
        "user_agent": profile.user_agent,
        "viewport": profile.viewport,
        "locale": profile.locale,
        "timezone_id": profile.timezone_id,
        "is_mobile": bool(profile.is_mobile),
        "has_touch": bool(profile.has_touch),
        "ignore_https_errors": True,
        "storage_state": storage_state,
    }
    if profile.geolocation:
        ctx_kwargs["geolocation"] = profile.geolocation

    ctx = await browser.new_context(**ctx_kwargs)

    headers = default_headers()
    if extra_headers:
        headers.update(extra_headers)
    await ctx.set_extra_http_headers(headers)

    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    ck = cookies_for_host(hostname)
    if ck:
        await ctx.add_cookies(ck)

    if profile.geolocation and hostname:
        scheme = parsed.scheme or "https"
        origin = f"{scheme}://{hostname}"
        try:
            await ctx.grant_permissions(["geolocation"], origin=origin)
        except Exception:
            pass

    return ctx


class BrowserManager:
    def __init__(
        self,
        *,
        channel: Literal["chromium", "chrome"],
        headless: bool,
        max_concurrency: int,
    ) -> None:
        self._channel = channel
        self._headless = headless
        self._sema = asyncio.Semaphore(max(1, int(max_concurrency)))

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._sema

    @property
    def channel(self) -> Literal["chromium", "chrome"]:
        return self._channel

    @property
    def headless(self) -> bool:
        return bool(self._headless)

    async def make_context(self, browser: Browser, *, url: str, storage_state_path: Path) -> BrowserContext:
        return await new_context(
            browser,
            url,
            profile=DEFAULT_PROFILE,
            extra_headers=None,
            storage_state_path=storage_state_path,
        )


@asynccontextmanager
async def open_browser(
    *,
    headless: bool,
    channel: Literal["chromium", "chrome"],
) -> AsyncIterator[Tuple[Playwright, Browser]]:
    """
    Lifespan-friendly Playwright launcher.
    Copied/adapted from repo `parser/browser.py`.
    """
    async with STEALTH.use_async(async_playwright()) as pw:
        args = chromium_launch_args()
        launch_kwargs: dict = {"headless": bool(headless), "args": args}
        proxy = proxy_from_env()
        if proxy:
            server = str(proxy.get("server") or "")
            parsed = urlparse(server)
            if not parsed.scheme or not parsed.netloc:
                LOGGER.warning("Playwright proxy server looks invalid: %s", server)
            LOGGER.info(
                "Playwright proxy enabled: server=%s username=%s bypass=%s",
                server,
                "set" if proxy.get("username") else "none",
                proxy.get("bypass") or "none",
            )
            launch_kwargs["proxy"] = proxy
        else:
            LOGGER.info("Playwright proxy disabled")
        if channel == "chrome":
            launch_kwargs["channel"] = "chrome"
            launch_kwargs["ignore_default_args"] = ["--enable-automation"]
            if "--disable-infobars" not in args:
                args.append("--disable-infobars")

        browser = await pw.chromium.launch(**launch_kwargs)
        try:
            yield pw, browser
        finally:
            await browser.close()


def load_manager_from_env() -> BrowserManager:
    channel = (os.environ.get("BROWSER_CHANNEL") or "chromium").strip().lower()
    if channel not in ("chromium", "chrome"):
        channel = "chromium"

    headless = (os.environ.get("HEADLESS") or "true").strip().lower() not in ("0", "false", "no")
    max_concurrency = int(os.environ.get("MAX_CONCURRENCY") or "2")

    return BrowserManager(channel=channel, headless=headless, max_concurrency=max_concurrency)
