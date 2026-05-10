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
    # Пустой список районов теперь явно валидируется как 400 Bad Request
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_compare_districts_rejects_unknown_district(client):
    response = await client.get(
        "/api/analytics/compare-districts",
        params={"districts": "Иркутский,Зимбабвийский", "days": 30},
    )
    assert response.status_code == 400
    assert "Зимбабвийский" in response.json()["detail"]
