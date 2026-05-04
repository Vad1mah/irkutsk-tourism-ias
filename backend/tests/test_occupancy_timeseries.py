import pytest


@pytest.mark.asyncio
async def test_occupancy_timeseries_structure(client):
    response = await client.get(
        "/api/analytics/occupancy-timeseries",
        params={"district": "Иркутский", "days": 30},
    )
    assert response.status_code == 200
    data = response.json()
    assert "district" in data
    assert "days" in data
    assert "points" in data
    assert "summary" in data
    s = data["summary"]
    assert {"min", "max", "avg", "samples"}.issubset(s.keys())


@pytest.mark.asyncio
async def test_occupancy_timeseries_validates_params(client):
    response = await client.get(
        "/api/analytics/occupancy-timeseries",
        params={"district": "Иркутский", "days": 0},
    )
    assert response.status_code == 422
