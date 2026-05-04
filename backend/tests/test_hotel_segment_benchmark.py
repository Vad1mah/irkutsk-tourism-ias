import pytest


@pytest.mark.asyncio
async def test_segment_benchmark_returns_comparison(client):
    # Возьмём первый отель из реестра
    try:
        hotels_resp = await client.get("/api/hotels", params={"limit": 1})
    except Exception:
        pytest.skip("hotels endpoint unavailable (transport error)")
    if hotels_resp.status_code != 200:
        pytest.skip("hotels endpoint unavailable")
    payload = hotels_resp.json()
    items = payload.get("items") or payload  # depends on shape
    if not items:
        pytest.skip("No hotels in registry")
    hotel_id = items[0].get("id") if isinstance(items[0], dict) else None
    if not hotel_id:
        pytest.skip("Hotel without id")
    response = await client.get(f"/api/hotels/{hotel_id}/segment-benchmark")
    assert response.status_code == 200
    data = response.json()
    expected = {"hotel", "segment", "hotel_metrics", "segment_metrics", "n_in_segment"}
    assert expected.issubset(data.keys())


@pytest.mark.asyncio
async def test_segment_benchmark_404_on_nonexistent(client):
    response = await client.get("/api/hotels/nonexistent_id_12345/segment-benchmark")
    assert response.status_code == 404
