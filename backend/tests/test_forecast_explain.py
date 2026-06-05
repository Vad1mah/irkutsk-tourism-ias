"""Endpoint /api/forecast/explain должен возвращать осмысленный ответ даже при сбое LLM."""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_explain_returns_fallback_on_llm_error(client):
    """Если LLM-запрос падает, endpoint возвращает текст-fallback с факторами, не 500."""
    with patch(
        "app.services.forecast_agent.forecast_agent.run",
        side_effect=Exception("LLM down"),
    ):
        response = await client.get(
            "/api/forecast/explain",
            params={"district": "Иркутский", "days_ahead": 14},
        )
    assert response.status_code == 200
    data = response.json()
    assert "factors" in data or "explanation" in data
    assert isinstance(data.get("explanation"), str) and len(data["explanation"]) > 30
    assert data.get("source") == "llm_error"


@pytest.mark.asyncio
async def test_explain_respects_timeout(client):
    """Медленный LLM обрывается по LLM_EXPLAIN_TIMEOUT_S, endpoint не висит дольше."""
    from app.routers.forecast import LLM_EXPLAIN_TIMEOUT_S

    async def slow_llm(*args, **kwargs):
        await asyncio.sleep(LLM_EXPLAIN_TIMEOUT_S + 30)
        return {}

    with patch(
        "app.services.forecast_agent.forecast_agent.run",
        new=slow_llm,
    ):
        start = asyncio.get_running_loop().time()
        response = await client.get(
            "/api/forecast/explain",
            params={"district": "Иркутский", "days_ahead": 14},
        )
        elapsed = asyncio.get_running_loop().time() - start
    assert elapsed < LLM_EXPLAIN_TIMEOUT_S + 5, (
        f"Took {elapsed:.1f}s, must abort near {LLM_EXPLAIN_TIMEOUT_S}s timeout"
    )
    assert response.status_code == 200
    assert response.json().get("source") == "llm_timeout"
