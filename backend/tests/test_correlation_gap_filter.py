"""Корреляция должна игнорировать месяцы с малой выборкой (gap-периоды)."""
import pytest


@pytest.mark.asyncio
async def test_correlation_skips_months_with_few_samples(client):
    response = await client.get("/api/analytics/correlation")
    assert response.status_code == 200
    data = response.json()
    # Каждый возвращаемый месяц должен иметь samples >= 5 (или явный gap-flag)
    for m in data.get("months", []):
        if m.get("avg_occupancy") is not None:
            assert m.get("samples", 0) >= 5 or m.get("is_gap"), (
                f"Month {m.get('month')} has avg_occupancy but only {m.get('samples')} samples"
            )
    # Должен быть список missing_periods
    assert "missing_periods" in data


@pytest.mark.asyncio
async def test_correlation_coefficient_in_valid_range(client):
    response = await client.get("/api/analytics/correlation")
    data = response.json()
    coeff = data.get("correlation_coefficient")
    if coeff is None:
        pytest.skip("Not enough non-gap data for correlation")
    # Pearson should be in [-1, 1]
    assert -1.0 <= coeff <= 1.0
