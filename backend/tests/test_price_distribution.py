import pytest

from app.routers.analytics import _percentile_linear


def test_percentile_linear_interpolates_not_max():
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert _percentile_linear(vals, 50) == 55   # медиана чётной выборки, не p60
    assert _percentile_linear(vals, 90) == 91   # НЕ 100 — старый int(n*p/100) давал max
    assert _percentile_linear(vals, 10) == 19
    assert _percentile_linear(vals, 100) == 100  # верхняя граница
    assert _percentile_linear(vals, 0) == 10     # нижняя граница


def test_percentile_linear_single_value():
    assert _percentile_linear([777], 90) == 777


def test_percentile_linear_small_sample_p90_not_max():
    # n=3: старый int(3*90/100)=2 → выдавал максимум (900). Новый интерполирует.
    vals = [100, 200, 900]
    assert _percentile_linear(vals, 90) == 760   # 200 + (900-200)*0.8
    assert _percentile_linear(vals, 90) != 900


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
