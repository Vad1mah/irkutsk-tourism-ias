"""Endpoint /api/forecast/{district}/validation возвращает RMSE/MAE."""
import pytest


@pytest.mark.asyncio
async def test_forecast_validation_returns_rmse_mae(client):
    response = await client.get("/api/forecast/Иркутский/validation", params={"days_back": 14})
    assert response.status_code == 200
    data = response.json()
    assert "rmse" in data
    assert "mae" in data
    assert "samples" in data
    assert isinstance(data.get("samples"), int)


@pytest.mark.asyncio
async def test_forecast_validation_handles_no_data(client):
    """Endpoint работает корректно даже когда нет saved forecasts."""
    response = await client.get("/api/forecast/НесуществующийРайон/validation", params={"days_back": 14})
    assert response.status_code == 200
    data = response.json()
    assert data.get("samples") == 0
    assert data.get("rmse") is None
    assert data.get("mae") is None
