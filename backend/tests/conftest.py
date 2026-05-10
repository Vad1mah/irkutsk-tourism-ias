"""Pytest fixtures для тестирования.

Все async fixtures и тесты выполняются на session-scoped event loop'е
(см. pytest.ini → asyncio_default_*_loop_scope = session). Это нужно,
потому что asyncpg pool создаётся в setup_services один раз на сессию
и связан с loop'ом своего создания — function-loop'ы вызывают
RuntimeError: Task attached to a different loop.
"""
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.data_service import data_service
from app.services.cache_service import cache_service


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_services():
    """Инициализация сервисов перед тестами (session-wide)."""
    try:
        await data_service.connect()
    except Exception:
        pass  # БД может быть недоступна в CI

    try:
        await cache_service.connect()
    except Exception:
        pass  # Redis может быть недоступен в CI

    yield

    try:
        await cache_service.close()
    except Exception:
        pass

    try:
        await data_service.close()
    except Exception:
        pass


@pytest_asyncio.fixture(loop_scope="session")
async def client(setup_services) -> AsyncGenerator[AsyncClient, None]:
    """HTTP клиент для тестирования API на session loop'е."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_history_data():
    """Мок данных истории для тестирования прогнозов."""
    from datetime import date, timedelta
    import random

    random.seed(42)
    base_date = date.today() - timedelta(days=90)
    history = []

    for i in range(90):
        d = base_date + timedelta(days=i)
        # Базовая загруженность с сезонностью
        base = 45 + 15 * (1 + 0.5 * (d.month in [6, 7, 8, 12, 1]))
        # Выходные выше
        weekend_boost = 15 if d.weekday() >= 5 else 0
        # Случайный шум
        noise = random.uniform(-10, 10)
        occupancy = max(20, min(95, base + weekend_boost + noise))

        history.append({"date": d, "occupancy": round(occupancy, 1)})

    return history


@pytest.fixture
def mock_weather_data():
    """Мок данных погоды для тестирования."""
    from datetime import date, timedelta

    weather = {}
    base_date = date.today()

    for i in range(14):
        d = base_date + timedelta(days=i)
        weather[d] = {
            "temperature_max": -5 + i % 5,
            "temperature_min": -15 + i % 3,
            "precipitation": 0.5 if i % 3 == 0 else 0.0,
        }

    return weather


@pytest.fixture
def mock_events_data():
    """Мок данных событий для тестирования."""
    from datetime import date, timedelta

    base_date = date.today()
    events = []

    event_names = [
        "Байкальский ледяной марафон",
        "Фестиваль зимней рыбалки",
        "Новогодние гуляния",
        "Масленица на Байкале",
    ]

    for i, name in enumerate(event_names):
        events.append({
            "date_start": base_date + timedelta(days=i * 7),
            "title": name,
            "event_type": "Спорт" if i == 0 else "Фестиваль",
        })

    return events
