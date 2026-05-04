import pytest


@pytest.mark.asyncio
async def test_booking_pace_structure(client):
    response = await client.get(
        "/api/analytics/booking-pace",
        params={"district": "Иркутский", "days_ahead": 14},
    )
    assert response.status_code == 200
    data = response.json()
    expected = {"district", "days_ahead", "method", "points", "summary", "methodology"}
    assert expected.issubset(data.keys())
    assert isinstance(data["points"], list)
    assert data["method"] == "daily_proxy_pickup"
    assert "trend" in data["summary"]


@pytest.mark.asyncio
async def test_booking_pace_validates_params(client):
    """Negative days_ahead должен вернуть 422."""
    response = await client.get(
        "/api/analytics/booking-pace",
        params={"district": "Иркутский", "days_ahead": -1},
    )
    assert response.status_code == 422
