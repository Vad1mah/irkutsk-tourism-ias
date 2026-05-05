"""Test that events_irk falls back to Crawl4AI when native HTML fails."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_irk_uses_crawl4ai_fallback_when_native_returns_empty():
    """If native HTML parser returns [], Crawl4AI fallback is invoked."""
    from app.parsers import events_irk

    with patch.object(events_irk, "_parse_native_html", AsyncMock(return_value=[])):
        with patch.object(events_irk, "_parse_via_crawl4ai", AsyncMock(return_value=[
            {"title": "Test event", "date_start": "2026-06-01"}
        ])) as mock_crawl:
            events = await events_irk.fetch_events_irk()
            assert len(events) == 1
            assert events[0]["title"] == "Test event"
            mock_crawl.assert_awaited_once()


@pytest.mark.asyncio
async def test_irk_uses_crawl4ai_fallback_when_native_raises():
    """If native HTML parser raises, Crawl4AI fallback is invoked."""
    from app.parsers import events_irk

    with patch.object(events_irk, "_parse_native_html", AsyncMock(side_effect=Exception("HTML changed"))):
        with patch.object(events_irk, "_parse_via_crawl4ai", AsyncMock(return_value=[
            {"title": "Fallback event", "date_start": "2026-06-02"}
        ])) as mock_crawl:
            events = await events_irk.fetch_events_irk()
            assert len(events) == 1
            assert events[0]["title"] == "Fallback event"
            mock_crawl.assert_awaited_once()


@pytest.mark.asyncio
async def test_irk_skips_fallback_when_native_succeeds():
    """If native HTML returns events, Crawl4AI is NOT called."""
    from app.parsers import events_irk

    with patch.object(events_irk, "_parse_native_html", AsyncMock(return_value=[
        {"title": "Native event", "date_start": "2026-06-03"}
    ])):
        with patch.object(events_irk, "_parse_via_crawl4ai", AsyncMock()) as mock_crawl:
            events = await events_irk.fetch_events_irk()
            assert len(events) == 1
            assert events[0]["title"] == "Native event"
            mock_crawl.assert_not_awaited()
