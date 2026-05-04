"""Тесты для GET /api/analytics/metadata."""
import pytest


@pytest.mark.asyncio
async def test_metadata_returns_required_keys(client):
    response = await client.get("/api/analytics/metadata")
    assert response.status_code == 200
    data = response.json()
    expected = {"hotels_count", "events_count", "data_range", "last_refresh", "gap_periods"}
    assert expected.issubset(data.keys()), f"Missing: {expected - data.keys()}"
    assert isinstance(data["data_range"], dict)
    assert "from" in data["data_range"] or "from_" in data["data_range"]
    assert "to" in data["data_range"]
    assert isinstance(data["gap_periods"], list)
