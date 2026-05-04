import pytest


@pytest.mark.asyncio
async def test_compare_districts_returns_side_by_side(client):
    response = await client.get(
        "/api/analytics/compare-districts",
        params={"districts": "Иркутский,Ольхонский", "days": 30},
    )
    assert response.status_code == 200
    data = response.json()
    assert "districts" in data
    assert "days" in data
    assert len(data["districts"]) == 2
    for d in data["districts"]:
        assert {"district", "occupancy", "adr_proxy", "revpar_proxy", "samples"}.issubset(d.keys())


@pytest.mark.asyncio
async def test_compare_districts_validates_params(client):
    response = await client.get(
        "/api/analytics/compare-districts",
        params={"districts": "", "days": 30},
    )
    assert response.status_code in (200, 422)  # empty list → 200 with empty districts OR 422
    if response.status_code == 200:
        assert response.json()["districts"] == []
