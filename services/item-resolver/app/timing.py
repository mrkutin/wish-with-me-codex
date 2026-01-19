from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from .middleware import get_request_id

logger = logging.getLogger(__name__)


class TimingStats:
    def __init__(self) -> None:
        self.timings: dict[str, float] = {}
        self.start_time = time.perf_counter()

    def record(self, operation: str, duration: float) -> None:
        self.timings[operation] = duration

    def total_time(self) -> float:
        return time.perf_counter() - self.start_time

    def log_summary(self, url: str) -> None:
        total = self.total_time()
        trace_id = get_request_id()

        logger.info(
            "Request timing summary for %s (trace_id=%s): total=%.2fs %s",
            url,
            trace_id,
            total,
            " ".join(f"{k}={v:.2f}s" for k, v in sorted(self.timings.items())),
        )


@asynccontextmanager
async def measure_time(stats: TimingStats, operation: str) -> AsyncIterator[None]:
    """Context manager to measure and record operation duration."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        stats.record(operation, duration)
        logger.debug("Operation '%s' took %.2fs", operation, duration)
