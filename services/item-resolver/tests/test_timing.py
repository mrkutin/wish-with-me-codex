from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.timing import TimingStats, measure_time


class TestTimingStats:
    def test_timing_stats_records_operations(self) -> None:
        stats = TimingStats()
        stats.record("operation1", 1.5)
        stats.record("operation2", 2.3)

        assert stats.timings["operation1"] == 1.5
        assert stats.timings["operation2"] == 2.3
        assert stats.total_time() > 0

    def test_timing_stats_log_summary(self, caplog) -> None:
        import logging

        caplog.set_level(logging.INFO)
        stats = TimingStats()
        stats.record("test_op", 0.5)

        stats.log_summary("https://example.com")

        assert "Request timing summary" in caplog.text
        assert "example.com" in caplog.text
        assert "test_op=0.50s" in caplog.text


class TestMeasureTime:
    @pytest.mark.anyio(backends=["asyncio"])
    async def test_measure_time_records_duration(self) -> None:
        stats = TimingStats()

        async with measure_time(stats, "test_operation"):
            await asyncio.sleep(0.01)

        assert "test_operation" in stats.timings
        assert stats.timings["test_operation"] >= 0.01

    @pytest.mark.anyio(backends=["asyncio"])
    async def test_measure_time_records_on_exception(self) -> None:
        stats = TimingStats()

        try:
            async with measure_time(stats, "failing_operation"):
                await asyncio.sleep(0.01)
                raise ValueError("test error")
        except ValueError:
            pass

        assert "failing_operation" in stats.timings
        assert stats.timings["failing_operation"] >= 0.01


class TestResolveEndpointTiming:
    def test_resolve_succeeds_with_timing(self) -> None:
        """Test that resolve endpoint completes successfully with timing instrumentation."""
        os.environ["RU_BEARER_TOKEN"] = "test_secret"
        os.environ["LLM_MODE"] = "stub"
        os.environ["SSRF_ALLOWLIST_HOSTS"] = "example.com"
        os.environ["LLM_MAX_CHARS"] = "1000"

        client = TestClient(create_app(fetcher_mode="stub"))

        r = client.post(
            "/resolver/v1/resolve",
            json={"url": "https://example.com/"},
            headers={"Authorization": "Bearer test_secret"},
        )

        # Timing code should not break the endpoint
        assert r.status_code == 200
        body = r.json()
        assert "title" in body
        assert "confidence" in body
