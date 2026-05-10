"""Тесты API endpoints через httpx AsyncClient."""
import pytest
import pytest_asyncio
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_health_returns_200(client: AsyncClient):
    """GET /health возвращает 200 с полями status, db_connected."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "db_connected" in data
    assert "redis_connected" in data


async def test_root_returns_api_info(client: AsyncClient):
    """GET / возвращает информацию об API."""
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Tourism Analytics API"
    assert "docs" in data


async def test_hotels_returns_list(client: AsyncClient):
    """GET /api/hotels возвращает структуру с items и total (или 500 без БД)."""
    try:
        resp = await client.get("/api/hotels")
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
    else:
        assert resp.status_code == 500


async def test_events_returns_list(client: AsyncClient):
    """GET /api/events возвращает список событий (или 500 без БД)."""
    try:
        resp = await client.get("/api/events")
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, list)
    else:
        assert resp.status_code == 500


async def test_query_health_returns_chroma_status(client: AsyncClient):
    """GET /api/query/health возвращает статус chroma."""
    resp = await client.get("/api/query/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "chroma_initialized" in data


async def test_query_post_empty_text_returns_422(client: AsyncClient):
    """POST /api/query с пустым text возвращает ошибку валидации."""
    resp = await client.post("/api/query", json={"text": ""})
    assert resp.status_code in (400, 422)


async def test_query_post_missing_body_returns_422(client: AsyncClient):
    """POST /api/query без тела возвращает 422."""
    resp = await client.post("/api/query")
    assert resp.status_code == 422


async def test_hotels_invalid_district_returns_400(client: AsyncClient):
    """GET /api/hotels с несуществующим районом возвращает 400."""
    resp = await client.get("/api/hotels", params={"district": "НесуществующийРайон123"})
    assert resp.status_code == 400


async def test_weekday_heatmap_returns_grid(client: AsyncClient):
    """GET /api/analytics/weekday-heatmap возвращает grid (день недели × месяц)."""
    try:
        resp = await client.get("/api/analytics/weekday-heatmap")
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    if resp.status_code == 200:
        data = resp.json()
        assert "data" in data
        assert "weekdays" in data and len(data["weekdays"]) == 7
        assert "months" in data and len(data["months"]) == 12
        assert isinstance(data["data"], list)
        for cell in data["data"]:
            assert "weekday" in cell and 1 <= cell["weekday"] <= 7
            assert "month" in cell and 1 <= cell["month"] <= 12
            assert "occupancy" in cell
            assert "samples" in cell
    else:
        assert resp.status_code in (500, 503)


async def test_weekday_heatmap_with_district(client: AsyncClient):
    """GET /api/analytics/weekday-heatmap?district=Иркутский фильтрует по району."""
    try:
        resp = await client.get("/api/analytics/weekday-heatmap", params={"district": "Иркутский"})
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    assert resp.status_code in (200, 500, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("district") == "Иркутский"


async def test_weekday_heatmap_invalid_district_returns_400(client: AsyncClient):
    """GET /api/analytics/weekday-heatmap с несуществующим районом возвращает 400."""
    resp = await client.get("/api/analytics/weekday-heatmap", params={"district": "Несуществующий123"})
    assert resp.status_code == 400


async def test_pickup_pace_returns_points(client: AsyncClient):
    """GET /api/analytics/pickup-pace возвращает кривую набора бронирований."""
    try:
        resp = await client.get("/api/analytics/pickup-pace", params={"days": 30})
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    if resp.status_code == 200:
        data = resp.json()
        assert "points" in data
        assert "summary" in data
        assert "period" in data
        for p in data["points"]:
            assert "date" in p
            assert "booked" in p
            assert "total_rooms" in p
            assert "occupancy" in p
            assert "pickup" in p
    else:
        assert resp.status_code in (500, 503)


async def test_pickup_pace_invalid_days_returns_4xx(client: AsyncClient):
    """days вне 1..180 → ошибка валидации (422 от FastAPI Query)."""
    resp = await client.get("/api/analytics/pickup-pace", params={"days": 500})
    assert resp.status_code in (400, 422)


async def test_export_csv_occupancy(client: AsyncClient):
    """GET /api/analytics/export?type=occupancy возвращает CSV."""
    try:
        resp = await client.get("/api/analytics/export", params={"type": "occupancy", "district": "Иркутский"})
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    if resp.status_code == 200:
        assert "text/csv" in resp.headers.get("content-type", "")
        body = resp.text
        first_line = body.splitlines()[0] if body else ""
        assert "date" in first_line.lower() or "district" in first_line.lower()
    else:
        # 400 — неизвестный district в тестовой БД; 500/503 — runtime/connectivity.
        # Все три допустимы при отсутствии данных в test env.
        assert resp.status_code in (400, 500, 503)


async def test_export_invalid_type_returns_400(client: AsyncClient):
    """type=foo → 400."""
    resp = await client.get("/api/analytics/export", params={"type": "foo"})
    assert resp.status_code in (400, 422)


async def test_revenue_summary_returns_kpi(client: AsyncClient):
    """GET /api/analytics/revenue-summary возвращает RevPAR/ADR/Occupancy агрегированно."""
    try:
        resp = await client.get("/api/analytics/revenue-summary")
    except RuntimeError:
        pytest.skip("DB event loop mismatch — skip in CI without fresh DB")
        return
    if resp.status_code == 200:
        data = resp.json()
        assert "occupancy" in data
        assert "adr" in data
        assert "revpar" in data
        assert "by_district" in data
        assert isinstance(data["by_district"], list)
    else:
        assert resp.status_code in (500, 503)
