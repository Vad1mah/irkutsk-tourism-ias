"""После удаления мёртвых endpoint'ов запросы к ним возвращают 404 или 405."""
import pytest

DEAD_PATHS = [
    ("POST", "/api/forecast/neural"),
    ("POST", "/api/forecast/xgboost"),
    ("GET", "/api/forecast/compare"),
    ("GET", "/api/forecast/holidays"),
    ("POST", "/api/events/init"),
    ("DELETE", "/api/events/demo"),
    ("POST", "/api/events/load-historical"),
]


@pytest.mark.parametrize("method,path", DEAD_PATHS)
@pytest.mark.asyncio
async def test_dead_endpoint_returns_404_or_405(client, method, path):
    response = await client.request(method, path)
    assert response.status_code in (404, 405), (
        f"{method} {path} should be removed (got {response.status_code})"
    )
