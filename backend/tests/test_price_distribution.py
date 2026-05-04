import pytest


@pytest.mark.asyncio
async def test_price_distribution_returns_percentiles(client):
    response = await client.get(
        "/api/analytics/price-distribution",
        params={"district": "Иркутский", "days": 30},
    )
    assert response.status_code == 200
    data = response.json()
    expected = {"district", "days", "samples", "p10", "p25", "p50", "p75", "p90"}
    assert expected.issubset(data.keys())


@pytest.mark.asyncio
async def test_price_distribution_validates_days(client):
    response = await client.get(
        "/api/analytics/price-distribution",
        params={"district": "Иркутский", "days": 0},
    )
    assert response.status_code == 422
