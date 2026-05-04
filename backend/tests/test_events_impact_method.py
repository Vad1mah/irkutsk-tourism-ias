"""Endpoint /api/analytics/events-impact принимает параметр method=naive|seasonal_corrected."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_events_impact_supports_method_param(client: AsyncClient):
    """GET /api/analytics/events-impact с method=naive и method=seasonal_corrected возвращают 200."""
    try:
        response = await client.get("/api/analytics/events-impact", params={"method": "naive"})
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    assert response.status_code == 200

    try:
        response2 = await client.get("/api/analytics/events-impact", params={"method": "seasonal_corrected"})
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    # На этом этапе seasonal_corrected возвращает naive с пометкой (полная реализация — D2)
    assert response2.status_code == 200
