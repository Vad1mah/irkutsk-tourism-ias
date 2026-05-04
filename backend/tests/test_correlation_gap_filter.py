"""Корреляция должна игнорировать месяцы с малой выборкой (gap-периоды)."""
import pytest


@pytest.mark.asyncio
async def test_correlation_is_gap_flag_matches_samples_threshold(client):
    response = await client.get("/api/analytics/correlation")
    assert response.status_code == 200
    data = response.json()
    for m in data.get("months", []):
        if m.get("is_gap"):
            assert m.get("samples", 0) < 5, (
                f"Month {m.get('month')} has is_gap=True but samples={m.get('samples')}"
            )
        else:
            assert m.get("samples", 0) >= 5, (
                f"Month {m.get('month')} has is_gap=False but samples={m.get('samples')}"
            )
    # missing_periods should still be a list
    assert isinstance(data.get("missing_periods"), list)


@pytest.mark.asyncio
async def test_correlation_coefficient_in_valid_range(client):
    response = await client.get("/api/analytics/correlation")
    data = response.json()
    coeff = data.get("correlation_coefficient")
    if coeff is None:
        pytest.skip("Not enough non-gap data for correlation")
    # Pearson should be in [-1, 1]
    assert -1.0 <= coeff <= 1.0
