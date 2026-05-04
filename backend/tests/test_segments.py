import pytest


@pytest.mark.asyncio
async def test_segments_returns_grouped_counts(client):
    response = await client.get("/api/analytics/segments")
    assert response.status_code == 200
    data = response.json()
    assert "by_size" in data
    assert "by_accommodation_type" in data
    assert "size_thresholds" in data
    # by_size может содержать любые из {mini, mid, large} или быть пустым
    assert isinstance(data["by_size"], dict)
    assert isinstance(data["by_accommodation_type"], dict)
    # thresholds always present
    assert data["size_thresholds"] == {"mini_max": 15, "mid_max": 50}
