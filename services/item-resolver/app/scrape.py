from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


def safe_host(url: str) -> str:
    host = urlparse(url).hostname or "unknown-host"
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in host)


def registrable_domain(hostname: str) -> str:
    """
    Best-effort "site key" so that page fetches and image fetches share storage_state.
    Avoids adding new dependencies; pragmatic eTLD+1 heuristic.
    """
    h = (hostname or "").strip().lower().rstrip(".")
    if not h:
        return "unknown-host"

    # IPs should stay as-is.
    parts = [p for p in h.split(".") if p]
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return h

    if len(parts) <= 2:
        return h

    multipart_suffixes = {
        "co.uk",
        "com.au",
        "co.jp",
        "com.br",
        "com.tr",
        "com.cn",
    }
    suffix2 = ".".join(parts[-2:])
    suffix3 = ".".join(parts[-3:])
    if suffix2 in multipart_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    if suffix3 in multipart_suffixes and len(parts) >= 4:
        return ".".join(parts[-4:])
    return ".".join(parts[-2:])


def _state_merge(a: dict, b: dict) -> dict:
    """
    Merge two Playwright storage_state dicts.
    - cookies merged by (name, domain, path), b overrides a
    - origins merged by origin; localStorage merged by name, b overrides a
    """
    out: dict = {"cookies": [], "origins": []}

    cookies_map: dict[tuple[str, str, str], dict] = {}
    for src in (a, b):
        for ck in (src.get("cookies") or []):
            if not isinstance(ck, dict):
                continue
            key = (str(ck.get("name", "")), str(ck.get("domain", "")), str(ck.get("path", "")))
            cookies_map[key] = ck
    out["cookies"] = list(cookies_map.values())

    origins_map: dict[str, dict] = {}
    for src in (a, b):
        for origin_obj in (src.get("origins") or []):
            if not isinstance(origin_obj, dict):
                continue
            origin = str(origin_obj.get("origin", "") or "")
            if not origin:
                continue
            cur = origins_map.get(origin) or {"origin": origin, "localStorage": []}

            ls_map: dict[str, dict] = {
                str(x.get("name", "")): x
                for x in (cur.get("localStorage") or [])
                if isinstance(x, dict) and str(x.get("name", "") or "")
            }
            for entry in (origin_obj.get("localStorage") or []):
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "") or "")
                if not name:
                    continue
                ls_map[name] = entry
            cur["localStorage"] = list(ls_map.values())
            origins_map[origin] = cur

    out["origins"] = list(origins_map.values())
    return out


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"cookies": [], "origins": []}


def _write_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def storage_state_path(storage_state_dir: Path, url: str) -> Path:
    storage_state_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # Shared storage by registrable domain so that page requests and image requests share state.
    site_key = registrable_domain(hostname)
    base_path = storage_state_dir / f"{safe_host('https://' + site_key)}.json"

    # Migration: merge any legacy per-host file into the shared file.
    legacy_path = storage_state_dir / f"{safe_host(url)}.json"
    if legacy_path != base_path and legacy_path.exists():
        base_state = _read_state(base_path) if base_path.exists() else {"cookies": [], "origins": []}
        legacy_state = _read_state(legacy_path)
        merged = _state_merge(base_state, legacy_state)
        try:
            _write_state(base_path, merged)
            # Best-effort cleanup: prevent continuing to fork state by subdomain.
            try:
                legacy_path.unlink()
            except Exception:
                pass
        except Exception:
            # If merge/write fails, fall back to legacy file to avoid breaking requests.
            return legacy_path

    return base_path


def looks_like_interstitial_or_challenge(title: str, html: str) -> bool:
    s = (title + "\n" + html).lower()
    needles = [
        # generic
        "captcha",
        "verify you are human",
        "verify that you are",
        "access denied",
        "forbidden",
        "too many requests",
        "rate limit",
        "robot check",
        "checking your browser",
        "checking device",
        "security check",
        "bot detection",
        "anti-bot",
        "challenge",
        # russian
        "доступ ограничен",
        "подтвердите, что вы не робот",
        "проверка браузера",
        "проверка устройства",
        "почти готово",
        "проверка",
    ]
    return any(n in s for n in needles)


async def wait_for_network_quiet(page, *, quiet_ms: int, timeout_ms: int) -> None:
    """
    Wait until there are no in-flight requests and there has been no request activity for `quiet_ms`.
    Copied/adapted from repo `run.py` for pages that long-poll (networkidle is unreliable).
    """
    loop = asyncio.get_running_loop()
    inflight = 0
    last_activity = loop.time()

    def bump() -> None:
        nonlocal last_activity
        last_activity = loop.time()

    def on_request(_req) -> None:
        nonlocal inflight
        inflight += 1
        bump()

    def on_done(_req) -> None:
        nonlocal inflight
        inflight = max(0, inflight - 1)
        bump()

    page.on("request", on_request)
    page.on("requestfinished", on_done)
    page.on("requestfailed", on_done)
    try:
        start = loop.time()
        quiet_s = quiet_ms / 1000.0
        timeout_s = timeout_ms / 1000.0
        while True:
            now = loop.time()
            if now - start > timeout_s:
                return
            if inflight == 0 and (now - last_activity) >= quiet_s:
                return
            await asyncio.sleep(0.05)
    finally:
        try:
            page.remove_listener("request", on_request)
        except Exception:
            pass
        try:
            page.remove_listener("requestfinished", on_done)
        except Exception:
            pass
        try:
            page.remove_listener("requestfailed", on_done)
        except Exception:
            pass


async def dismiss_common_popups(page, *, timeout_ms: int = 5000) -> int:
    """
    Attempt to dismiss common popups/overlays that block content.
    Returns the number of popups dismissed.

    Targets:
    - Cookie consent dialogs
    - City/location selectors
    - Newsletter/subscription modals
    - Age verification
    """
    dismissed = 0

    # Common button texts for dismissal (Russian and English)
    dismiss_texts = [
        # Cookie consent
        "Понятно", "Принять", "Согласен", "Принять все", "Accept", "Accept all",
        "OK", "Ок", "Хорошо", "Закрыть", "Close", "Got it",
        # City confirmation
        "Да", "Да, верно", "Все верно", "Подтвердить", "Yes", "Confirm",
        # Generic close
        "×", "✕", "✖",
    ]

    # Try clicking buttons with these texts
    for text in dismiss_texts:
        try:
            # Look for visible buttons/links with this text
            locator = page.locator(f"button:visible:text-is('{text}'), a:visible:text-is('{text}'), [role='button']:visible:text-is('{text}')")
            count = await locator.count()
            if count > 0:
                # Click the first matching element
                await locator.first.click(timeout=1000)
                dismissed += 1
                # Brief wait for UI to update
                await asyncio.sleep(0.3)
        except Exception:
            pass

    # Try clicking common close button selectors
    close_selectors = [
        "[class*='close']:visible", "[class*='Close']:visible",
        "[class*='dismiss']:visible", "[class*='Dismiss']:visible",
        "[aria-label='Close']:visible", "[aria-label='Закрыть']:visible",
        "[data-testid*='close']:visible", "[data-testid*='Close']:visible",
        ".modal-close:visible", ".popup-close:visible",
    ]

    for selector in close_selectors:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > 0:
                # Only click if it looks like a close button (small element)
                box = await locator.first.bounding_box()
                if box and box['width'] < 100 and box['height'] < 100:
                    await locator.first.click(timeout=1000)
                    dismissed += 1
                    await asyncio.sleep(0.3)
        except Exception:
            pass

    return dismissed


async def wait_for_dom_stable(page, *, samples: int, interval_ms: int, timeout_ms: int) -> None:
    """
    Sample DOM size and wait until it stays stable for N samples.
    Copied/adapted from repo `run.py`.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()
    timeout_s = timeout_ms / 1000.0

    last = None
    stable = 0
    while True:
        if loop.time() - start > timeout_s:
            return
        try:
            cur = await page.evaluate(
                "() => ({ htmlLen: document.documentElement?.outerHTML?.length || 0, "
                "textLen: document.body?.innerText?.length || 0 })"
            )
            cur = (int(cur.get("htmlLen", 0)), int(cur.get("textLen", 0)))
        except Exception:
            cur = None

        if cur is not None and cur == last and cur != (0, 0):
            stable += 1
            if stable >= samples:
                return
        else:
            stable = 0
            last = cur

        await asyncio.sleep(interval_ms / 1000.0)


def _challenge_title_patterns() -> list[str]:
    """
    Patterns that indicate a challenge/interstitial page in the title.
    These should clear automatically when the challenge passes.
    """
    return [
        "captcha",
        "verify",
        "access denied",
        "forbidden",
        "robot",
        "checking",
        "security check",
        "bot detection",
        "anti-bot",
        "antibot",
        "challenge",
        # Russian patterns
        "проверка",
        "доступ ограничен",
        "подтвердите",
    ]


async def wait_for_challenge_to_clear(page, *, timeout_ms: int) -> bool:
    """
    Best-effort: wait for common interstitials to clear.
    Waits for either:
    1. Ozon-specific API response (indicates page loaded)
    2. Title to NOT contain any challenge-related keywords
    3. Product content to appear (price, add-to-cart button, h1 product title)
    """
    import asyncio

    loop = asyncio.get_running_loop()
    start = loop.time()
    timeout_s = timeout_ms / 1000.0

    # Build regex pattern for challenge titles
    patterns = _challenge_title_patterns()
    pattern_regex = "|".join(patterns)

    # Try Ozon-specific API first (fast path)
    try:
        resp = await page.wait_for_response(
            lambda r: (
                "/web/api/v1/settings" in (getattr(r, "url", "") or "")
                and int(getattr(r, "status", 0) or 0) == 200
            ),
            timeout=min(5000, timeout_ms),  # Short timeout for this specific check
        )
        _ = resp
        # Give extra time for page to render after API response
        await asyncio.sleep(1.0)
        return True
    except Exception:
        pass

    # Wait for title to clear of challenge keywords OR product content to appear
    while loop.time() - start < timeout_s:
        try:
            # Check if title is clean (no challenge keywords)
            title_clean = await page.evaluate(
                f"""() => {{
                    const title = (document.title || '').toLowerCase();
                    const pattern = /{pattern_regex}/i;
                    return !pattern.test(title);
                }}"""
            )

            # Check if product content is visible (any of these indicates real page)
            has_product_content = await page.evaluate(
                """() => {
                    // Check for price patterns (numbers with currency)
                    const text = document.body?.innerText || '';
                    const hasPrice = /[\\d\\s]+[₽$€]|[₽$€][\\d\\s]+|\\d+\\.\\d{2}/.test(text);

                    // Check for add-to-cart type buttons
                    const hasCartBtn = !!document.querySelector(
                        '[data-widget*="cart"], [class*="cart"], [class*="buy"], ' +
                        'button[class*="add"], [data-qa*="cart"], [data-testid*="cart"]'
                    );

                    // Check for substantial content (more than just a challenge page)
                    const hasSubstantialContent = text.length > 500;

                    return (hasPrice && hasSubstantialContent) || hasCartBtn;
                }"""
            )

            if title_clean and has_product_content:
                return True

            # If title is clean but no product content yet, wait a bit more
            if title_clean:
                # Give it a bit more time for content to load
                await asyncio.sleep(0.5)
                # Re-check for product content
                has_product_content = await page.evaluate(
                    """() => {
                        const text = document.body?.innerText || '';
                        return text.length > 500;
                    }"""
                )
                if has_product_content:
                    return True

        except Exception:
            pass

        await asyncio.sleep(0.3)

    return False


def _default_timeout_ms() -> int:
    """Get page load timeout from env, default 90 seconds."""
    return int(os.environ.get("PAGE_TIMEOUT_MS", "90000"))


@dataclass(frozen=True)
class PageCaptureConfig:
    wait_until: str = "load"  # Changed from networkidle - some sites never reach idle (keep polling)
    timeout_ms: int = 90_000  # Increased from 60s for slow sites like Yandex Market
    settle_ms: int = 5_000  # Increased from 3s - many sites load prices async via API
    max_extra_wait_ms: int = 30_000
    network_quiet_ms: int = 2_000  # Increased from 1.5s for slow API calls
    dom_sample_interval_ms: int = 500
    dom_stable_samples: int = 3
    challenge_extra_wait_ms: int = 120_000
    post_challenge_settle_ms: int = 3_000  # Extra settle after challenge clears

    @classmethod
    def from_env(cls) -> "PageCaptureConfig":
        """Create config with environment variable overrides."""
        wait_until = os.environ.get("PAGE_WAIT_UNTIL", "load")
        return cls(timeout_ms=_default_timeout_ms(), wait_until=wait_until)


async def capture_page_source(page, url: str, *, cfg: PageCaptureConfig) -> tuple[str, str, str]:
    """
    Returns: (final_url, title, html)

    Waits for JS content to load, then captures the HTML for LLM extraction.
    """
    await page.goto(url, wait_until=cfg.wait_until, timeout=cfg.timeout_ms)

    extra_budget = min(cfg.max_extra_wait_ms, cfg.timeout_ms)

    # Wait for body to have content
    try:
        await page.wait_for_function(
            "() => document.body && (document.body.innerText || '').trim().length > 0",
            timeout=min(10_000, extra_budget),
        )
    except Exception:
        pass

    # Dismiss common popups/overlays that may block content
    try:
        dismissed = await dismiss_common_popups(page, timeout_ms=5000)
        if dismissed > 0:
            await asyncio.sleep(1.0)
    except Exception:
        pass

    # Wait for network and DOM to stabilize
    await wait_for_network_quiet(page, quiet_ms=cfg.network_quiet_ms, timeout_ms=extra_budget)
    await wait_for_dom_stable(
        page,
        samples=cfg.dom_stable_samples,
        interval_ms=cfg.dom_sample_interval_ms,
        timeout_ms=extra_budget,
    )

    # Settle time for JS to finish rendering
    if cfg.settle_ms > 0:
        await asyncio.sleep(cfg.settle_ms / 1000.0)

    final_url = page.url
    html = await page.content()
    try:
        title = await page.title()
    except Exception:
        title = ""

    if looks_like_interstitial_or_challenge(title, html):
        challenge_cleared = await wait_for_challenge_to_clear(page, timeout_ms=cfg.challenge_extra_wait_ms)

        # Extra settle time after challenge clears for page to fully render
        if challenge_cleared and cfg.post_challenge_settle_ms > 0:
            await asyncio.sleep(cfg.post_challenge_settle_ms / 1000.0)

        # Wait for network and DOM to stabilize again after challenge
        await wait_for_network_quiet(page, quiet_ms=cfg.network_quiet_ms, timeout_ms=10_000)
        await wait_for_dom_stable(
            page,
            samples=cfg.dom_stable_samples,
            interval_ms=cfg.dom_sample_interval_ms,
            timeout_ms=10_000,
        )

        final_url = page.url
        html = await page.content()
        try:
            title = await page.title()
        except Exception:
            pass

    return final_url, title, html


