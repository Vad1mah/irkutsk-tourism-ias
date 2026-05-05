"""Tests for events_culture38 Crawl4AI fallback (mirrors G1/events_irk pattern)."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_culture38_uses_fallback_when_native_returns_empty():
    from app.parsers import events_culture38
    with patch.object(events_culture38, "_parse_native_html", AsyncMock(return_value=[])):
        with patch.object(events_culture38, "_parse_via_crawl4ai", AsyncMock(return_value=[
            {"title": "Test", "date_start": "2026-06-01"}
        ])) as mock_crawl:
            events = await events_culture38.fetch_events_culture38()
            assert len(events) == 1
            mock_crawl.assert_awaited_once()


@pytest.mark.asyncio
async def test_culture38_uses_fallback_when_native_raises():
    from app.parsers import events_culture38
    with patch.object(events_culture38, "_parse_native_html", AsyncMock(side_effect=Exception("HTML changed"))):
        with patch.object(events_culture38, "_parse_via_crawl4ai", AsyncMock(return_value=[
            {"title": "Fallback", "date_start": "2026-06-02"}
        ])) as mock_crawl:
            events = await events_culture38.fetch_events_culture38()
            assert len(events) == 1
            mock_crawl.assert_awaited_once()


@pytest.mark.asyncio
async def test_culture38_skips_fallback_when_native_succeeds():
    from app.parsers import events_culture38
    with patch.object(events_culture38, "_parse_native_html", AsyncMock(return_value=[
        {"title": "Native", "date_start": "2026-06-03"}
    ])):
        with patch.object(events_culture38, "_parse_via_crawl4ai", AsyncMock()) as mock_crawl:
            events = await events_culture38.fetch_events_culture38()
            assert len(events) == 1
            mock_crawl.assert_not_awaited()
