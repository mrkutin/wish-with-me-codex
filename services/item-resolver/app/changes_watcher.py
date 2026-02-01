"""CouchDB changes feed watcher for auto-resolving pending items."""

import asyncio
import base64
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .browser_manager import BrowserManager
from .couchdb import CouchDBClient, ConflictError, DocumentNotFoundError, get_couchdb
from .html_optimizer import format_html_for_llm
from .html_parser import extract_images_from_html, format_images_for_llm
from .image_utils import crop_screenshot_to_content, image_data_url
from .llm import LLMClient
from .scrape import PageCaptureConfig, capture_page_source, looks_like_interstitial_or_challenge, storage_state_path
from .ssrf import validate_public_http_url
from .errors import ResolverError

logger = logging.getLogger(__name__)

# Instance identification and lease configuration
INSTANCE_ID = os.environ.get("INSTANCE_ID") or os.environ.get("HOSTNAME") or socket.gethostname()
LEASE_DURATION_SECONDS = int(os.environ.get("LEASE_DURATION_SECONDS", "300"))  # 5 minutes
SWEEP_INTERVAL_SECONDS = int(os.environ.get("SWEEP_INTERVAL_SECONDS", "60"))  # 1 minute


def is_valid_public_url(url: str) -> bool:
    """Check if a URL is valid and publicly accessible (non-throwing)."""
    try:
        validate_public_http_url(url)
        return True
    except ResolverError:
        return False


async def try_claim_item(couchdb: CouchDBClient, doc: dict) -> bool:
    """
    Attempt to claim an item for processing using optimistic locking.

    Uses CouchDB's _rev field for conflict detection. Only the first instance
    to successfully update the document will proceed with processing.

    Returns True if claim succeeded, False if another instance claimed it.
    """
    item_id = doc["_id"]
    current_rev = doc["_rev"]
    now = datetime.now(timezone.utc)
    lease_expires = now + timedelta(seconds=LEASE_DURATION_SECONDS)

    claim_doc = {
        **doc,
        "_rev": current_rev,
        "status": "in_progress",
        "claimed_by": INSTANCE_ID,
        "claimed_at": now.isoformat(),
        "lease_expires_at": lease_expires.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        await couchdb.put(claim_doc)
        logger.info(f"Claimed item {item_id} (lease expires: {lease_expires.isoformat()})")
        return True
    except ConflictError:
        # Another instance claimed it first - this is expected behavior
        logger.debug(f"Item {item_id} already claimed by another instance")
        return False


class ChangesWatcher:
    """Watches CouchDB changes feed for pending items and resolves them."""

    def __init__(
        self,
        couchdb: CouchDBClient,
        llm_client: LLMClient,
        manager: BrowserManager,
        browser,
        storage_state_dir: str,
    ):
        self.couchdb = couchdb
        self.llm_client = llm_client
        self.manager = manager
        self.browser = browser
        self.storage_state_dir = storage_state_dir
        self.cfg = PageCaptureConfig()
        self._running = False
        self._task: asyncio.Task | None = None
        self._sweep_task: asyncio.Task | None = None
        self._last_seq: str = "now"
        # Limit concurrent resolutions to avoid overwhelming resources
        max_concurrent = int(os.environ.get("COUCHDB_WATCHER_MAX_CONCURRENT", "3"))
        self._resolve_semaphore = asyncio.Semaphore(max_concurrent)
        self._pending_tasks: set[asyncio.Task] = set()
        logger.info(f"ChangesWatcher initialized with instance_id={INSTANCE_ID}, lease={LEASE_DURATION_SECONDS}s, sweep={SWEEP_INTERVAL_SECONDS}s")

    async def start(self) -> None:
        """Start watching for changes and stale lease sweep."""
        if self._running:
            logger.warning("Changes watcher already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        self._sweep_task = asyncio.create_task(self._sweep_loop())
        logger.info(f"Started CouchDB changes watcher (instance: {INSTANCE_ID})")

    async def stop(self) -> None:
        """Stop watching for changes and sweep loop."""
        self._running = False

        # Stop watch task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Stop sweep task
        if self._sweep_task:
            self._sweep_task.cancel()
            try:
                await self._sweep_task
            except asyncio.CancelledError:
                pass
            self._sweep_task = None

        # Cancel and wait for any pending resolution tasks
        for task in list(self._pending_tasks):
            task.cancel()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()

        logger.info("Stopped CouchDB changes watcher")

    async def _watch_loop(self) -> None:
        """Main watch loop with automatic reconnection."""
        reconnect_delay = 1  # Start with 1 second
        max_reconnect_delay = 60  # Max 60 seconds

        while self._running:
            try:
                await self._watch_changes()
                # Reset delay on successful connection
                reconnect_delay = 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Changes watcher error: {e}", exc_info=True)

                if not self._running:
                    break

                # Exponential backoff for reconnection
                logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    async def _sweep_loop(self) -> None:
        """Background loop for sweeping stale leases."""
        while self._running:
            try:
                await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
                if self._running:
                    await self._sweep_stale_leases()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Sweep loop error: {e}", exc_info=True)

    async def _sweep_stale_leases(self) -> None:
        """Find and reset items with expired leases."""
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Find items where lease has expired
            stale_items = await self.couchdb.find(
                selector={
                    "type": "item",
                    "status": "in_progress",
                    "lease_expires_at": {"$lt": now},
                },
                limit=100,
            )

            for item in stale_items:
                item_id = item["_id"]
                claimed_by = item.get("claimed_by", "unknown")

                logger.warning(
                    f"Resetting stale item {item_id} (was claimed by {claimed_by}, lease expired)"
                )

                # Reset to pending for re-processing
                item["status"] = "pending"
                item["claimed_by"] = None
                item["claimed_at"] = None
                item["lease_expires_at"] = None
                item["updated_at"] = datetime.now(timezone.utc).isoformat()

                try:
                    await self.couchdb.put(item)
                    logger.info(f"Reset stale item {item_id} to pending")
                except ConflictError:
                    # Another process already handled it
                    logger.debug(f"Conflict resetting item {item_id}, already handled")
        except Exception as e:
            logger.error(f"Error sweeping stale leases: {e}")

    async def _watch_changes(self) -> None:
        """Watch the changes feed for pending items."""
        logger.info(f"Connecting to changes feed from seq: {self._last_seq} (instance: {INSTANCE_ID})")

        # Filter for pending items only
        selector = {
            "type": "item",
            "status": "pending",
        }

        async for change in self.couchdb.changes(
            since=self._last_seq,
            filter_selector=selector,
            include_docs=True,
            heartbeat=30000,
        ):
            if not self._running:
                break

            # Update last sequence for reconnection
            if "seq" in change:
                self._last_seq = change["seq"]

            # Skip deletions
            if change.get("deleted"):
                continue

            doc = change.get("doc")
            if not doc:
                continue

            # Double-check it's a pending item
            if doc.get("type") != "item" or doc.get("status") != "pending":
                continue

            item_id = doc.get("_id", "unknown")
            source_url = doc.get("source_url")

            if not source_url:
                logger.warning(f"Item {item_id} has no source_url, skipping")
                continue

            # Try to claim the item before processing
            claimed = await try_claim_item(self.couchdb, doc)
            if not claimed:
                # Another instance claimed it, skip
                continue

            logger.info(f"Processing claimed item: {item_id} from {source_url}")

            # Process in background to not block the feed, with concurrency limit
            task = asyncio.create_task(self._resolve_item_with_semaphore(doc))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

    async def _resolve_item_with_semaphore(self, doc: dict) -> None:
        """Wrapper to limit concurrent resolutions."""
        async with self._resolve_semaphore:
            await self._resolve_item(doc)

    async def _resolve_item(self, doc: dict) -> None:
        """Resolve a pending item and update CouchDB."""
        item_id = doc.get("_id", "unknown")
        source_url = doc.get("source_url", "")

        try:
            # Validate URL
            if not is_valid_public_url(source_url):
                logger.warning(f"Item {item_id} has invalid URL: {source_url}")
                await self._update_item_status(doc, "error", error="Invalid or private URL")
                return

            # Resolve the URL
            resolved = await self._resolve_url(source_url)

            if resolved is None:
                logger.error(f"Failed to resolve item {item_id}")
                await self._update_item_status(doc, "error", error="Resolution failed")
                return

            # Update item with resolved data
            await self._update_item_resolved(doc, resolved)
            logger.info(f"Successfully resolved item {item_id}")

        except Exception as e:
            logger.exception(f"Error resolving item {item_id}: {e}")
            try:
                await self._update_item_status(doc, "error", error=str(e)[:200])
            except Exception:
                pass

    async def _resolve_url(self, url: str) -> dict | None:
        """Resolve a URL to extract product metadata."""
        state_path = storage_state_path(Path(self.storage_state_dir), url)

        async with self.manager.semaphore:
            context = await self.manager.make_context(
                self.browser,
                url=url,
                storage_state_path=state_path,
            )
            try:
                page = await context.new_page()
                try:
                    final_url, page_title, html = await capture_page_source(page, url, cfg=self.cfg)
                except PlaywrightTimeoutError:
                    logger.warning(f"Page load timed out: {url}")
                    return None
                except asyncio.TimeoutError:
                    logger.warning(f"Page load timed out: {url}")
                    return None

                # Check for challenge pages
                if looks_like_interstitial_or_challenge(page_title, html):
                    body_text_len = len(html) if html else 0
                    has_product_indicators = any(ind in html.lower() for ind in [
                        'price', 'цена', 'корзин', 'cart', 'buy', 'купить', 'добавить',
                        'product', 'товар', '₽', 'руб', 'rub'
                    ]) if html else False

                    if body_text_len < 5000 and not has_product_indicators:
                        logger.warning(f"Page appears blocked: {url}")
                        return None

                # Take screenshot
                page_shot = await page.screenshot(full_page=False, type="jpeg", quality=75)
                page_b64 = base64.b64encode(page_shot).decode("ascii")
                page_mime = "image/jpeg"

                # Save storage state
                try:
                    await context.storage_state(path=str(state_path))
                except Exception:
                    pass

                # Extract images from HTML
                images = extract_images_from_html(html, base_url=final_url or url)
                image_candidates = format_images_for_llm(images, max_images=20)

                # Format HTML for LLM
                max_chars = int(os.environ.get("LLM_MAX_CHARS") or 50000)
                html_content = format_html_for_llm(
                    html=html,
                    url=final_url or url,
                    title=page_title,
                    max_chars=max_chars,
                )

                # Call LLM for extraction
                try:
                    llm_out = await self.llm_client.extract(
                        url=final_url or url,
                        title=page_title,
                        image_candidates=image_candidates,
                        image_base64=page_b64,
                        image_mime=page_mime,
                        html_content=html_content,
                    )
                except Exception as e:
                    logger.exception(f"LLM extraction failed for {url}: {e}")
                    return None

                # Fetch product image if available
                image_b64: str | None = None
                image_mime: str | None = None
                resolved_image_url: str | None = None

                if llm_out.image_url:
                    resolved = urljoin(final_url or url, llm_out.image_url)
                    if is_valid_public_url(resolved):
                        resolved_image_url = resolved
                        image_page = await context.new_page()
                        try:
                            try:
                                await image_page.goto(
                                    resolved,
                                    wait_until="load",
                                    timeout=self.cfg.timeout_ms,
                                )
                                await image_page.wait_for_load_state(
                                    "networkidle",
                                    timeout=self.cfg.timeout_ms,
                                )
                            except PlaywrightTimeoutError:
                                logger.warning(f"Image load timed out: {resolved}")
                            else:
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

                return {
                    "title": llm_out.title,
                    "description": llm_out.description,
                    "price_amount": llm_out.price_amount,
                    "price_currency": llm_out.price_currency,
                    "canonical_url": llm_out.canonical_url,
                    "confidence": llm_out.confidence if llm_out.confidence is not None else 0.0,
                    "image_url": resolved_image_url,
                    "image_base64": image_data_url(image_b64, image_mime),
                }

            finally:
                try:
                    await context.close()
                except Exception:
                    pass

    async def _update_item_resolved(self, doc: dict, resolved: dict, retries: int = 0) -> None:
        """Update item document with resolved data."""
        MAX_RETRIES = 3
        now = datetime.now(timezone.utc).isoformat()

        # Re-fetch document to get latest revision
        try:
            current_doc = await self.couchdb.get(doc["_id"])
        except DocumentNotFoundError:
            logger.warning(f"Item {doc['_id']} no longer exists")
            return

        # Don't update if already resolved (race condition)
        if current_doc.get("status") == "resolved":
            logger.info(f"Item {doc['_id']} already resolved, skipping")
            return

        # Check if still owned by us (guard against lease expiration during processing)
        if current_doc.get("claimed_by") != INSTANCE_ID:
            logger.warning(f"Item {doc['_id']} no longer owned by us (owned by {current_doc.get('claimed_by')}), skipping update")
            return

        # Update fields
        current_doc["status"] = "resolved"
        current_doc["updated_at"] = now

        # Clear claim fields
        current_doc["claimed_by"] = None
        current_doc["claimed_at"] = None
        current_doc["lease_expires_at"] = None

        if resolved.get("title"):
            current_doc["title"] = resolved["title"]
        if resolved.get("description"):
            current_doc["description"] = resolved["description"]
        if resolved.get("price_amount") is not None:
            current_doc["price"] = resolved["price_amount"]
        if resolved.get("price_currency"):
            current_doc["currency"] = resolved["price_currency"]
        if resolved.get("canonical_url"):
            current_doc["source_url"] = resolved["canonical_url"]
        if resolved.get("image_url"):
            current_doc["image_url"] = resolved["image_url"]
        if resolved.get("image_base64"):
            current_doc["image_base64"] = resolved["image_base64"]

        current_doc["resolve_confidence"] = resolved.get("confidence", 0.0)
        current_doc["resolved_at"] = now
        current_doc["resolved_by"] = INSTANCE_ID

        try:
            await self.couchdb.put(current_doc)
        except ConflictError:
            if retries >= MAX_RETRIES:
                logger.error(f"Max retries exceeded updating item {doc['_id']}")
                return
            logger.warning(f"Conflict updating item {doc['_id']}, retry {retries + 1}")
            await self._update_item_resolved(doc, resolved, retries + 1)

    async def _update_item_status(
        self,
        doc: dict,
        status: str,
        error: str | None = None,
        retries: int = 0,
    ) -> None:
        """Update item status (for errors)."""
        MAX_RETRIES = 3
        now = datetime.now(timezone.utc).isoformat()

        try:
            current_doc = await self.couchdb.get(doc["_id"])
        except DocumentNotFoundError:
            return

        # Check if still owned by us (guard against lease expiration during processing)
        if current_doc.get("claimed_by") != INSTANCE_ID:
            logger.warning(f"Item {doc['_id']} no longer owned by us, skipping status update")
            return

        current_doc["status"] = status
        current_doc["updated_at"] = now

        # Clear claim fields
        current_doc["claimed_by"] = None
        current_doc["claimed_at"] = None
        current_doc["lease_expires_at"] = None

        if error:
            current_doc["resolve_error"] = error
            current_doc["resolved_by"] = INSTANCE_ID

        try:
            await self.couchdb.put(current_doc)
        except ConflictError:
            if retries >= MAX_RETRIES:
                logger.error(f"Max retries exceeded updating status for item {doc['_id']}")
                return
            logger.warning(f"Conflict updating status for item {doc['_id']}, retry {retries + 1}")
            await self._update_item_status(doc, status, error, retries + 1)


# Global watcher instance
_watcher: ChangesWatcher | None = None


async def start_watcher(
    llm_client: LLMClient,
    manager: BrowserManager,
    browser,
    storage_state_dir: str,
) -> ChangesWatcher:
    """Start the global changes watcher."""
    global _watcher

    if _watcher is not None:
        await _watcher.stop()

    couchdb = get_couchdb()
    _watcher = ChangesWatcher(
        couchdb=couchdb,
        llm_client=llm_client,
        manager=manager,
        browser=browser,
        storage_state_dir=storage_state_dir,
    )
    await _watcher.start()
    return _watcher


async def stop_watcher() -> None:
    """Stop the global changes watcher."""
    global _watcher

    if _watcher is not None:
        await _watcher.stop()
        _watcher = None

    from .couchdb import close_couchdb
    await close_couchdb()
