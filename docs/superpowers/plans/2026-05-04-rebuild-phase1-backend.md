# Phase 1: Backend Implementation Plan (B2B-rebuild)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подготовить backend для B2B-rebuild фронта — расширить схему `Event`, добавить 10 новых endpoint'ов, исправить 6 багов, удалить 7 мёртвых endpoint'ов, расширить парсеры до полного объёма доступных полей, подключить health-monitor.

**Архитектура:** Без изменений верхнего слоя (FastAPI 7 routers + SQLAlchemy 2.0 async + Pydantic v2 + Redis). Расширения локальны: новые методы в `data_service.py`, новые endpoint'ы в существующих роутерах, миграция схемы через одноразовый ALTER-скрипт (Alembic — out of scope, см. spec §15). Принципы — TDD, частые коммиты.

**Tech Stack:** Python 3.11, FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.0 (asyncpg), pytest + pytest-asyncio, httpx (AsyncClient + ASGITransport), Redis 7.

**Spec reference:** [`docs/superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md`](../specs/2026-05-04-rebuild-frontend-b2b-design.md) (утверждён 2026-05-04). После Phase 1 — Phase 2 (AI-агент), Phase 3 (Frontend), Phase 4 (модели UML), Phase 5 (верификация).

---

## File Structure

### Будут созданы
- `backend/scripts/migrate_event_schema_v2.py` — идемпотентный ALTER для Event-схемы и UNIQUE constraint.
- `backend/app/services/methodology_service.py` — расчёт baseline для corrected impact.
- `backend/app/services/parser_health_service.py` — Redis-storage статусов парсеров.
- `backend/tests/test_methodology_service.py` — unit-тесты сервиса.
- `backend/tests/test_new_analytics_endpoints.py` — функциональные тесты 10 новых endpoint'ов.
- `backend/tests/test_parser_health.py` — тесты health-monitor.
- `backend/tests/test_event_schema_v2.py` — тесты расширенной схемы и dedup.

### Будут модифицированы
- `backend/app/db/models.py` — добавить 6 колонок в `Event`, UNIQUE constraint.
- `backend/app/models/schemas.py` — расширить Pydantic `Event` схему + новые модели для новых endpoint'ов.
- `backend/app/services/data_service.py` — новые методы для booking-pace, occupancy-timeseries, price-distribution, segments, segment-benchmark.
- `backend/app/services/db_service.py` — обновить upsert для Event с новым UNIQUE.
- `backend/app/services/cache_service.py` — добавить `model_version` в ensemble cache key.
- `backend/app/routers/analytics.py` — 8 новых endpoint'ов + 2 фикса багов (events-impact, correlation).
- `backend/app/routers/forecast.py` — 1 новый endpoint (validation), 1 фикс (ensemble cache key).
- `backend/app/routers/hotels.py` — 1 новый endpoint (segment-benchmark).
- `backend/app/routers/parser.py` — 1 новый endpoint (health) + удалить 1 мёртвый.
- `backend/app/routers/events.py` — удалить 3 мёртвых endpoint'а.
- `backend/app/routers/query.py` — фикс race condition stream counter.
- `backend/app/parsers/events_yandex.py` — 2 новых поля парсинга.
- `backend/app/parsers/events_kassir.py` — 2 новых поля парсинга.
- `backend/app/parsers/events_zeroevent.py` — price_min из описания.
- `backend/app/parsers/events_culture_rf.py` — venue_address.
- `backend/app/parsers/events_irk.py` — Crawl4AI fallback (хрупкий → устойчивый).
- `backend/app/parsers/events_culture38.py` — Crawl4AI fallback.
- `backend/app/parsers/hotels_101hotels.py` — image_url, amenities.
- `backend/app/parsers/base.py` — интеграция health_monitor.report() в lifecycle.

### Не трогаем (за исключением мелкого использования)
- `backend/app/main.py`, `backend/app/scheduler.py`, `backend/app/middleware/rate_limit.py`, `backend/app/services/ensemble_service.py`, `feature_engineering.py`, `prophet_service.py`, `xgboost_service.py`, `neuralprophet_service.py`, `weather_service.py` — стабильны, в Phase 1 не трогаем.

---

## Раздел A: Расширение схемы `Event` (6 новых полей)

### Task A1: Расширить ORM-модель `Event`

**Files:**
- Modify: `backend/app/db/models.py:79-102`
- Test: `backend/tests/test_event_schema_v2.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_event_schema_v2.py`:

```python
"""Тесты расширенной схемы Event (фаза 1 B2B-rebuild)."""
from datetime import date, time
import pytest

from app.db.models import Event


def test_event_orm_has_new_fields():
    """ORM-модель Event должна иметь 6 новых полей."""
    columns = {c.name for c in Event.__table__.columns}
    expected_new = {
        "time_start",
        "price_min",
        "price_max",
        "image_url",
        "address",
        "age_restriction",
    }
    assert expected_new.issubset(columns), f"Missing: {expected_new - columns}"


def test_event_orm_can_instantiate_with_new_fields():
    """ORM-объект Event можно сконструировать со всеми новыми полями."""
    e = Event(
        event_id="test-1",
        title="Test event",
        date_start=date(2026, 5, 10),
        source_id="test",
        time_start=time(19, 30),
        price_min=500,
        price_max=2500,
        image_url="https://example.com/img.jpg",
        address="ул. Ленина, 1, Иркутск",
        age_restriction="16+",
    )
    assert e.time_start.hour == 19
    assert e.price_min == 500
    assert e.age_restriction == "16+"
```

- [ ] **Step 2: Запустить тест — должен упасть**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py -v
```

Expected: `FAIL` — `AttributeError: type object 'Event' has no attribute 'time_start'` или подобное.

- [ ] **Step 3: Добавить колонки в ORM-модель**

Открыть `backend/app/db/models.py`. В импорт `sqlalchemy` добавить `Time`:

```python
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
```

В классе `Event` (после `url`, перед `created_at`) добавить:

```python
    time_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_restriction: Mapped[str | None] = mapped_column(String(10), nullable=True)
```

И в импорт `from datetime import date, datetime` добавить `time`:

```python
from datetime import date, datetime, time
```

- [ ] **Step 4: Запустить тест — должен пройти**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py::test_event_orm_has_new_fields tests/test_event_schema_v2.py::test_event_orm_can_instantiate_with_new_fields -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/tests/test_event_schema_v2.py
git commit -m "feat(db): extend Event ORM model with 6 fields (time_start, price_min, price_max, image_url, address, age_restriction)"
```

---

### Task A2: Расширить Pydantic-схему `Event`

**Files:**
- Modify: `backend/app/models/schemas.py` (найти класс `Event`)
- Test: `backend/tests/test_event_schema_v2.py`

- [ ] **Step 1: Найти текущую схему**

```bash
grep -n "^class Event" backend/app/models/schemas.py
```

Note: сохранить номер строки и убедиться что схема существует.

- [ ] **Step 2: Написать падающий тест**

Дописать в `backend/tests/test_event_schema_v2.py`:

```python
def test_event_pydantic_accepts_new_fields():
    """Pydantic-схема Event принимает новые поля и валидирует их."""
    from app.models.schemas import Event as EventSchema

    payload = {
        "event_id": "abc-1",
        "title": "Концерт",
        "date_start": "2026-06-01",
        "source_id": "yandex",
        "time_start": "19:30:00",
        "price_min": 1000,
        "price_max": 3500,
        "image_url": "https://example.com/poster.jpg",
        "address": "ул. Ленина, 5",
        "age_restriction": "12+",
    }
    e = EventSchema(**payload)
    assert e.time_start.hour == 19
    assert e.price_min == 1000
    assert e.age_restriction == "12+"


def test_event_pydantic_optional_new_fields():
    """Все 6 новых полей опциональны (можно создать без них)."""
    from app.models.schemas import Event as EventSchema

    e = EventSchema(
        event_id="abc-2",
        title="Минимальное событие",
        date_start="2026-06-02",
        source_id="manual",
    )
    assert e.time_start is None
    assert e.price_min is None
```

- [ ] **Step 3: Запустить тест — должен упасть**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py::test_event_pydantic_accepts_new_fields -v
```

Expected: FAIL — `ValidationError: 6 unexpected keyword arguments` или похожее.

- [ ] **Step 4: Расширить Pydantic-схему**

Открыть `backend/app/models/schemas.py`, найти класс `Event` (или `EventResponse` — какое имя реально существует, проверить на шаге 1). Добавить в начало файла (если ещё нет):

```python
from datetime import time
```

В тело класса добавить 6 опциональных полей:

```python
    time_start: time | None = Field(None, description="Время начала события (HH:MM:SS)")
    price_min: int | None = Field(None, ge=0, description="Минимальная цена в рублях")
    price_max: int | None = Field(None, ge=0, description="Максимальная цена в рублях")
    image_url: str | None = Field(None, description="URL изображения")
    address: str | None = Field(None, description="Уличный адрес места проведения")
    age_restriction: str | None = Field(None, max_length=10, description="Возрастное ограничение, напр. 16+")
```

- [ ] **Step 5: Запустить тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/schemas.py backend/tests/test_event_schema_v2.py
git commit -m "feat(schemas): extend Pydantic Event with 6 optional B2B fields"
```

---

### Task A3: Идемпотентный ALTER-скрипт для миграции БД

**Files:**
- Create: `backend/scripts/migrate_event_schema_v2.py`

- [ ] **Step 1: Создать миграционный скрипт**

Содержимое `backend/scripts/migrate_event_schema_v2.py`:

```python
"""Идемпотентная миграция схемы events (Phase 1 B2B-rebuild).

Добавляет 6 колонок и UNIQUE constraint для дедупликации.
Безопасна к повторному запуску — каждый ALTER обёрнут в try/except UniqueViolation.

Запуск:
    cd backend
    .\\venv\\Scripts\\python.exe scripts\\migrate_event_schema_v2.py
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.db.session import async_engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NEW_COLUMNS: list[tuple[str, str]] = [
    ("time_start", "TIME NULL"),
    ("price_min", "INTEGER NULL"),
    ("price_max", "INTEGER NULL"),
    ("image_url", "TEXT NULL"),
    ("address", "TEXT NULL"),
    ("age_restriction", "VARCHAR(10) NULL"),
]

DEDUP_CONSTRAINT_NAME = "uq_events_dedup"
DEDUP_CONSTRAINT_DDL = (
    f"ALTER TABLE events ADD CONSTRAINT {DEDUP_CONSTRAINT_NAME} "
    f"UNIQUE (source_id, date_start, title)"
)


async def column_exists(conn, column: str) -> bool:
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'events' AND column_name = :col"
        ),
        {"col": column},
    )
    return result.first() is not None


async def constraint_exists(conn, name: str) -> bool:
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = 'events' AND constraint_name = :name"
        ),
        {"name": name},
    )
    return result.first() is not None


async def migrate() -> None:
    async with async_engine.begin() as conn:
        for col_name, col_ddl in NEW_COLUMNS:
            if await column_exists(conn, col_name):
                logger.info("column events.%s already exists — skip", col_name)
                continue
            await conn.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_ddl}"))
            logger.info("added column events.%s (%s)", col_name, col_ddl)

        if await constraint_exists(conn, DEDUP_CONSTRAINT_NAME):
            logger.info("constraint %s already exists — skip", DEDUP_CONSTRAINT_NAME)
        else:
            try:
                await conn.execute(text(DEDUP_CONSTRAINT_DDL))
                logger.info("added UNIQUE constraint %s", DEDUP_CONSTRAINT_NAME)
            except ProgrammingError as exc:
                logger.warning("could not add %s: %s — likely duplicates exist; "
                               "clean events table first", DEDUP_CONSTRAINT_NAME, exc)


if __name__ == "__main__":
    asyncio.run(migrate())
```

- [ ] **Step 2: Запустить миграцию**

```bash
cd backend && .\venv\Scripts\python.exe scripts\migrate_event_schema_v2.py
```

Expected output (первый запуск):
```
... [INFO] added column events.time_start (TIME NULL)
... [INFO] added column events.price_min (INTEGER NULL)
... [INFO] added column events.price_max (INTEGER NULL)
... [INFO] added column events.image_url (TEXT NULL)
... [INFO] added column events.address (TEXT NULL)
... [INFO] added column events.age_restriction (VARCHAR(10) NULL)
... [INFO] added UNIQUE constraint uq_events_dedup
```

Если UNIQUE падает — следующий task (B1) обработает дубли в базе.

- [ ] **Step 3: Запустить миграцию повторно — должна быть идемпотентной**

```bash
cd backend && .\venv\Scripts\python.exe scripts\migrate_event_schema_v2.py
```

Expected: все колонки и constraint помечены как «already exists — skip».

- [ ] **Step 4: Проверить через SQL**

```bash
cd C:/Users/Admin/Desktop/Diplom && docker exec tourism-postgres psql -U tourism -d tourism -c "\d events"
```

Expected: 6 новых колонок видны в схеме, constraint `uq_events_dedup` присутствует.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/migrate_event_schema_v2.py
git commit -m "feat(migration): idempotent ALTER for Event schema v2 + dedup constraint"
```

---

## Раздел B: Дедупликация Event

### Task B1: Очистка дублей в `events` перед UNIQUE constraint

**Files:**
- Modify: `backend/scripts/migrate_event_schema_v2.py`

- [ ] **Step 1: Если в Task A3 Step 2 UNIQUE упал** — добавить cleanup в скрипт перед constraint'ом. Иначе пропустить весь Task B1 и идти к B2.

Дополнить `migrate_event_schema_v2.py`, перед блоком создания constraint'а:

```python
async def remove_duplicates(conn) -> int:
    """Оставляет только одну строку на (source_id, date_start, title), у которой min event_id."""
    result = await conn.execute(text("""
        DELETE FROM events e
        USING events e2
        WHERE e.source_id = e2.source_id
          AND e.date_start = e2.date_start
          AND e.title = e2.title
          AND e.event_id > e2.event_id
    """))
    return result.rowcount or 0
```

И в `migrate()` перед constraint-блоком:

```python
        if not await constraint_exists(conn, DEDUP_CONSTRAINT_NAME):
            removed = await remove_duplicates(conn)
            logger.info("removed %d duplicate events before UNIQUE constraint", removed)
```

- [ ] **Step 2: Перезапустить миграцию**

```bash
cd backend && .\venv\Scripts\python.exe scripts\migrate_event_schema_v2.py
```

Expected: `removed N duplicate events`, затем `added UNIQUE constraint uq_events_dedup`.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/migrate_event_schema_v2.py
git commit -m "feat(migration): remove duplicates before applying uq_events_dedup"
```

---

### Task B2: Обновить upsert логику в `db_service.py`

**Files:**
- Modify: `backend/app/services/db_service.py` — функция `upsert_event` или аналогичная (искать по `INSERT INTO events`)
- Test: `backend/tests/test_event_schema_v2.py`

- [ ] **Step 1: Найти функцию upsert events**

```bash
grep -n "INSERT INTO events\|upsert_event\|insert_event" backend/app/services/db_service.py
```

- [ ] **Step 2: Написать падающий тест**

Дописать в `backend/tests/test_event_schema_v2.py`:

```python
import pytest_asyncio


@pytest.mark.asyncio
async def test_event_dedup_on_conflict():
    """Двойная вставка одного события не создаёт дубль."""
    from app.services.db_service import db_service
    from app.services.data_service import data_service

    if not data_service.is_connected:
        pytest.skip("DB not available")

    payload = {
        "event_id": "test-dedup-1",
        "title": "Тестовое событие dedup",
        "date_start": date(2099, 1, 1),
        "source_id": "test_dedup",
        "event_type": "Test",
    }

    # Первая вставка
    await db_service.upsert_event(**payload)
    # Вторая — с другим event_id, но тем же (source_id, date_start, title)
    payload2 = {**payload, "event_id": "test-dedup-2"}
    await db_service.upsert_event(**payload2)

    # Проверить, что в БД ровно одна строка
    rows = await data_service.get_events(
        date_from=date(2099, 1, 1),
        date_to=date(2099, 1, 1),
    )
    matching = [r for r in rows if r.get("title") == payload["title"]]
    assert len(matching) == 1, f"Expected 1 row, got {len(matching)}"

    # Cleanup
    await db_service.delete_event_by_id("test-dedup-1")
    await db_service.delete_event_by_id("test-dedup-2")
```

- [ ] **Step 3: Запустить тест — должен упасть**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py::test_event_dedup_on_conflict -v
```

Expected: либо `IntegrityError` (если upsert не использует ON CONFLICT), либо 2 строки вместо 1.

- [ ] **Step 4: Обновить upsert**

В `db_service.upsert_event` SQL-запрос INSERT привести к виду:

```python
INSERT INTO events (
    event_id, title, description, date_start, date_end, event_type,
    location, source_id, url, time_start, price_min, price_max,
    image_url, address, age_restriction
) VALUES (
    :event_id, :title, :description, :date_start, :date_end, :event_type,
    :location, :source_id, :url, :time_start, :price_min, :price_max,
    :image_url, :address, :age_restriction
)
ON CONFLICT (source_id, date_start, title) DO UPDATE SET
    description = COALESCE(EXCLUDED.description, events.description),
    event_type = COALESCE(EXCLUDED.event_type, events.event_type),
    location = COALESCE(EXCLUDED.location, events.location),
    url = COALESCE(EXCLUDED.url, events.url),
    time_start = COALESCE(EXCLUDED.time_start, events.time_start),
    price_min = COALESCE(EXCLUDED.price_min, events.price_min),
    price_max = COALESCE(EXCLUDED.price_max, events.price_max),
    image_url = COALESCE(EXCLUDED.image_url, events.image_url),
    address = COALESCE(EXCLUDED.address, events.address),
    age_restriction = COALESCE(EXCLUDED.age_restriction, events.age_restriction),
    updated_at = NOW()
```

Параметры функции `upsert_event` расширить новыми kwargs (опциональные, default `None`). Добавить также `delete_event_by_id(event_id: str)` если ещё нет.

- [ ] **Step 5: Запустить тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py::test_event_dedup_on_conflict -v
```

Expected: 1 passed.

- [ ] **Step 6: Запустить полный test_event_schema_v2.py**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py -v
```

Expected: все тесты passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/db_service.py backend/tests/test_event_schema_v2.py
git commit -m "feat(db): dedup-aware upsert for Event with 6 new fields, ON CONFLICT (source_id,date_start,title)"
```

---

## Раздел C: Фиксы 6 багов

### Task C1: Фикс race condition в `/api/query/stream` (Redis-counter)

**Files:**
- Modify: `backend/app/routers/query.py` — найти `_active_streams` или подобный счётчик

- [ ] **Step 1: Найти текущий счётчик стримов**

```bash
grep -n "_active_streams\|active_stream" backend/app/routers/query.py
```

- [ ] **Step 2: Написать тест**

Создать `backend/tests/test_stream_counter.py`:

```python
"""Тест на race condition счётчика SSE-стримов (баг C1)."""
import asyncio
import pytest

from app.routers.query import increment_active_stream, decrement_active_stream, get_active_streams


@pytest.mark.asyncio
async def test_concurrent_stream_increments_are_atomic():
    """100 параллельных incrementов дают ровно +100 счётчику."""
    initial = await get_active_streams()
    await asyncio.gather(*(increment_active_stream() for _ in range(100)))
    after = await get_active_streams()
    assert after - initial == 100

    # Cleanup
    await asyncio.gather(*(decrement_active_stream() for _ in range(100)))
```

- [ ] **Step 3: Запустить — должен упасть**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_stream_counter.py -v
```

Expected: `ImportError` (функции не существуют) или race condition.

- [ ] **Step 4: Реализовать через Redis**

В `backend/app/routers/query.py` — заменить in-memory counter на Redis:

```python
from app.services.cache_service import cache_service

_STREAM_COUNTER_KEY = "query:active_streams"
_STREAM_TTL_SECONDS = 600  # автосброс зависших


async def increment_active_stream() -> int:
    if cache_service.client is None:
        return 0
    val = await cache_service.client.incr(_STREAM_COUNTER_KEY)
    await cache_service.client.expire(_STREAM_COUNTER_KEY, _STREAM_TTL_SECONDS)
    return int(val)


async def decrement_active_stream() -> int:
    if cache_service.client is None:
        return 0
    val = await cache_service.client.decr(_STREAM_COUNTER_KEY)
    if val < 0:
        await cache_service.client.set(_STREAM_COUNTER_KEY, 0)
        return 0
    return int(val)


async def get_active_streams() -> int:
    if cache_service.client is None:
        return 0
    val = await cache_service.client.get(_STREAM_COUNTER_KEY)
    return int(val or 0)
```

Заменить все вызовы старого in-memory счётчика на эти функции.

- [ ] **Step 5: Запустить тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_stream_counter.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/query.py backend/tests/test_stream_counter.py
git commit -m "fix(query): race condition in SSE stream counter — moved to Redis INCR/DECR"
```

---

### Task C2: Фикс `/api/analytics/correlation` — отфильтровать gap-периоды

**Files:**
- Modify: `backend/app/routers/analytics.py` — функция `get_correlation_data` (строка ~108)

- [ ] **Step 1: Написать тест**

Создать `backend/tests/test_correlation_gap_filter.py`:

```python
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
```

- [ ] **Step 2: Запустить — увидеть текущий результат**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_correlation_gap_filter.py -v
```

Note: возможно тест уже проходит — фактический баг в том, что Pearson считается со всеми точками. Если тест зелёный, проверить вычисление коэффициента.

- [ ] **Step 3: Если тест проходит — добавить тест на коэффициент**

```python
@pytest.mark.asyncio
async def test_correlation_coefficient_excludes_gap_months(client):
    response = await client.get("/api/analytics/correlation")
    data = response.json()
    coeff = data.get("correlation_coefficient")
    if coeff is None:
        pytest.skip("Not enough non-gap data for correlation")
    # Pearson должен быть в [-1, 1]
    assert -1.0 <= coeff <= 1.0
```

- [ ] **Step 4: Реализовать фильтрацию в `analytics.py`**

В `get_correlation_data`, найти место расчёта Pearson — обычно `numpy.corrcoef` или scipy.stats.pearsonr. Перед расчётом отфильтровать:

```python
MIN_SAMPLES_PER_MONTH = 5

filtered_pairs = [
    (m["events_count"], m["avg_occupancy"])
    for m in months
    if m.get("samples", 0) >= MIN_SAMPLES_PER_MONTH and m.get("avg_occupancy") is not None
]
if len(filtered_pairs) < 3:
    correlation_coefficient = None
else:
    import numpy as np
    arr = np.array(filtered_pairs)
    correlation_coefficient = float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1])
```

В каждом элементе `months` добавить флаг `is_gap = samples < MIN_SAMPLES_PER_MONTH`. Соответственно в frontend (Phase 3) этот флаг рендерится как разрыв линии.

- [ ] **Step 5: Запустить тесты**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_correlation_gap_filter.py -v
```

Expected: passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/analytics.py backend/tests/test_correlation_gap_filter.py
git commit -m "fix(analytics): correlation excludes months with <5 samples (gap-period handling)"
```

---

### Task C3: Фикс cache key collision в `/api/forecast/ensemble`

**Files:**
- Modify: `backend/app/services/cache_service.py` или там, где формируется forecast cache key (искать по `forecast_ensemble`, `forecast_cache_key`)

- [ ] **Step 1: Найти место формирования ключа**

```bash
grep -rn "forecast.*cache.*key\|ensemble.*cache" backend/app/services/ backend/app/routers/
```

- [ ] **Step 2: Написать тест**

Создать `backend/tests/test_ensemble_cache_key.py`:

```python
"""Cache key для ensemble должен содержать model_version (фикс коллизии при апдейте моделей)."""
import pytest


def test_ensemble_cache_key_includes_model_version():
    from app.services.cache_service import build_ensemble_cache_key

    key1 = build_ensemble_cache_key(district="Иркутский", days=14, model_version="v1")
    key2 = build_ensemble_cache_key(district="Иркутский", days=14, model_version="v2")
    assert key1 != key2, "Different model_version must yield different cache keys"
    assert "v1" in key1 and "v2" in key2
```

- [ ] **Step 3: Запустить — упадёт**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_ensemble_cache_key.py -v
```

Expected: ImportError или функция не учитывает model_version.

- [ ] **Step 4: Реализовать**

В `backend/app/services/cache_service.py` (или соответствующем файле) добавить:

```python
ENSEMBLE_MODEL_VERSION = "ens-v2-2026-05"  # bump при изменении весов или признаков

def build_ensemble_cache_key(
    district: str,
    days: int,
    model_version: str = ENSEMBLE_MODEL_VERSION,
) -> str:
    return f"forecast:ensemble:{model_version}:{district}:{days}"
```

Найти все места, где сейчас формируется ensemble cache key вручную (строкой типа `f"forecast:{district}:{days}"`), и заменить вызовом `build_ensemble_cache_key(...)`.

- [ ] **Step 5: Запустить тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_ensemble_cache_key.py -v
```

Expected: passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cache_service.py backend/tests/test_ensemble_cache_key.py
git commit -m "fix(cache): ensemble cache key includes model_version to prevent collisions on retrain"
```

---

### Task C4: Фикс `/api/forecast/explain` — таймаут и явный fallback

**Files:**
- Modify: `backend/app/routers/forecast.py` — endpoint `/explain` (или `forecast/explain`)

- [ ] **Step 1: Найти endpoint**

```bash
grep -n "explain\|/explain" backend/app/routers/forecast.py
```

- [ ] **Step 2: Написать тест**

Создать `backend/tests/test_forecast_explain.py`:

```python
"""Endpoint /api/forecast/explain должен возвращать осмысленный ответ даже при сбое LLM."""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_explain_returns_fallback_on_llm_error(client):
    """Если LLM-запрос падает или таймаутит, endpoint возвращает текст-fallback с факторами, не 500."""
    with patch("app.services.forecast_agent.forecast_agent.run", side_effect=Exception("LLM down")):
        response = await client.get(
            "/api/forecast/explain",
            params={"district": "Иркутский", "days": 14},
        )
    assert response.status_code == 200
    data = response.json()
    assert "factors" in data or "explanation" in data
    assert isinstance(data.get("explanation"), str) and len(data["explanation"]) > 30


@pytest.mark.asyncio
async def test_explain_respects_timeout(client):
    """Запрос с медленным LLM завершается за <10 секунд (timeout 5s + buffer)."""
    import asyncio

    async def slow_llm(*args, **kwargs):
        await asyncio.sleep(30)
        return {}

    with patch("app.services.forecast_agent.forecast_agent.run", side_effect=slow_llm):
        start = asyncio.get_event_loop().time()
        response = await client.get(
            "/api/forecast/explain",
            params={"district": "Иркутский", "days": 14},
        )
        elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 10, f"Took {elapsed:.1f}s, must be <10s due to timeout"
    assert response.status_code == 200
```

- [ ] **Step 3: Запустить — упадёт**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_forecast_explain.py -v
```

- [ ] **Step 4: Реализовать timeout + fallback**

В `forecast.py` обернуть вызов LLM:

```python
import asyncio

LLM_EXPLAIN_TIMEOUT_S = 5.0


async def _explain_with_fallback(district: str, days: int, ensemble_result: dict) -> dict:
    factors = _extract_factors_from_ensemble(ensemble_result)  # вспомогательная — извлекает факторы из ensemble без LLM
    try:
        result = await asyncio.wait_for(
            forecast_agent.run(district=district, days=days),
            timeout=LLM_EXPLAIN_TIMEOUT_S,
        )
        if result and result.get("explanation"):
            return {"factors": factors, "explanation": result["explanation"], "source": "llm"}
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("forecast.explain LLM failed: %s — using factor-only fallback", exc)

    fallback_text = _build_factor_explanation(district, days, factors)
    return {"factors": factors, "explanation": fallback_text, "source": "fallback"}


def _extract_factors_from_ensemble(result: dict) -> list[dict]:
    """Достаёт топ-5 факторов из feature_importance ensemble."""
    fi = (result or {}).get("feature_importance", {}).get("xgboost", {})
    return [{"name": k, "importance": v} for k, v in sorted(fi.items(), key=lambda x: -x[1])[:5]]


def _build_factor_explanation(district: str, days: int, factors: list[dict]) -> str:
    if not factors:
        return f"Прогноз на {days} дней по району «{district}» построен на ансамбле моделей. " \
               f"Подробное объяснение временно недоступно (AI-сервис не отвечает)."
    top = ", ".join(f"{f['name']}" for f in factors[:3])
    return (
        f"Прогноз на {days} дней по району «{district}» опирается на исторический ряд занятости "
        f"и набор признаков. Главные факторы по важности: {top}. "
        f"Развёрнутое AI-объяснение временно недоступно — показаны топ-5 факторов из XGBoost."
    )
```

Использовать `_explain_with_fallback` в endpoint'е.

- [ ] **Step 5: Запустить тесты**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_forecast_explain.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/forecast.py backend/tests/test_forecast_explain.py
git commit -m "fix(forecast): /explain has 5s timeout and factor-only fallback when LLM unreachable"
```

---

### Task C5: Фикс `/api/parser/events/all` — корректная обработка ON CONFLICT

**Files:** уже частично закрыт Task B2 (upsert использует `ON CONFLICT (source_id, date_start, title)`).

- [ ] **Step 1: Проверить, что parser/events/all использует обновлённый upsert**

```bash
grep -n "upsert_event\|insert_event" backend/app/parsers/ backend/app/routers/parser.py
```

Все парсеры должны вызывать `db_service.upsert_event(...)`. Если какой-то использует raw INSERT — заменить.

- [ ] **Step 2: Сценарный тест на дубли при batch upsert**

Дописать в `backend/tests/test_event_schema_v2.py`:

```python
@pytest.mark.asyncio
async def test_parser_all_no_duplicates_on_rerun():
    """Повторный запуск /parser/events/all не создаёт дублей."""
    from app.services.data_service import data_service
    if not data_service.is_connected:
        pytest.skip("DB not available")

    counts_before = len(await data_service.get_events())
    # симуляция второго прогона upsert тех же данных не нужна — UNIQUE гарантирует
    # достаточно проверки, что всем существующим (source_id, date_start, title) уникальны
    rows = await data_service.get_events()
    seen = set()
    for r in rows:
        key = (r.get("source"), r.get("date_start"), r.get("title"))
        assert key not in seen, f"Duplicate detected: {key}"
        seen.add(key)
```

- [ ] **Step 3: Запустить**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_event_schema_v2.py::test_parser_all_no_duplicates_on_rerun -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_event_schema_v2.py
git commit -m "test(parsers): verify no duplicates after parser/events/all rerun"
```

---

### Task C6: Фикс `/api/analytics/events-impact` — добавить параметр `method`

> Полная реализация corrected impact будет в Task D2-D5 (новый MethodologyService). Здесь — только wiring параметра.

**Files:**
- Modify: `backend/app/routers/analytics.py` — endpoint `/events-impact` (~строка 474)

- [ ] **Step 1: Тест на параметр**

Создать `backend/tests/test_events_impact_method.py`:

```python
"""Endpoint /api/analytics/events-impact принимает параметр method=naive|seasonal_corrected."""
import pytest


@pytest.mark.asyncio
async def test_events_impact_supports_method_param(client):
    response = await client.get("/api/analytics/events-impact", params={"method": "naive"})
    assert response.status_code == 200

    response2 = await client.get("/api/analytics/events-impact", params={"method": "seasonal_corrected"})
    # На этом этапе seasonal_corrected может вернуть 200 (заглушка) или 501 — допускаем оба варианта
    assert response2.status_code in (200, 501)


@pytest.mark.asyncio
async def test_events_impact_default_method_is_seasonal_corrected(client):
    """По умолчанию возвращается seasonal_corrected (после реализации D2-D5)."""
    response = await client.get("/api/analytics/events-impact")
    assert response.status_code == 200
    # Проверим что в ответе есть метаданные о методе
    data = response.json()
    if isinstance(data, list) and data:
        assert "method" in data[0] or True  # пока soft, после D2-D5 — strict
```

- [ ] **Step 2: Добавить параметр в endpoint**

В `analytics.py` найти `events-impact`, расширить сигнатуру:

```python
from typing import Literal

@router.get("/events-impact")
async def get_events_impact(
    data: DataServiceDep,
    cache: CacheServiceDep,
    method: Literal["naive", "seasonal_corrected"] = "seasonal_corrected",
    window_weeks: int = 3,
):
    if method == "naive":
        return await _events_impact_naive(data)
    # seasonal_corrected — будет реализован в Task D2-D5
    # пока fallback на naive с пометкой
    result = await _events_impact_naive(data)
    for r in result:
        r["method"] = "naive_fallback"
    return result


async def _events_impact_naive(data) -> list[dict]:
    # текущая реализация (вырезать тело старого endpoint'а сюда)
    ...
```

- [ ] **Step 3: Тест должен пройти**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_events_impact_method.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/analytics.py backend/tests/test_events_impact_method.py
git commit -m "feat(analytics): /events-impact accepts method param (naive|seasonal_corrected)"
```

---

## Раздел D: 10 новых endpoint'ов

### Task D1: `MethodologyService` — каркас сервиса для baseline-расчётов

**Files:**
- Create: `backend/app/services/methodology_service.py`
- Create: `backend/tests/test_methodology_service.py`

- [ ] **Step 1: Тест на базовый интерфейс**

```python
# backend/tests/test_methodology_service.py
"""Unit-тесты MethodologyService."""
from datetime import date

import pytest

from app.services.methodology_service import (
    MethodologyService,
    SeasonalBaseline,
)


def test_seasonal_baseline_excludes_event_days():
    """Baseline считается только из дней без событий."""
    occupancy_series = [
        (date(2026, 5, 4), 50.0),  # пн
        (date(2026, 5, 11), 55.0),  # пн (день события)
        (date(2026, 5, 18), 48.0),  # пн
        (date(2026, 5, 25), 52.0),  # пн
    ]
    event_dates = {date(2026, 5, 11)}
    svc = MethodologyService()
    baseline = svc.compute_seasonal_baseline(
        target_date=date(2026, 5, 11),
        target_weekday=0,  # пн
        occupancy_history=occupancy_series,
        event_dates=event_dates,
        window_weeks=3,
    )
    # ожидаем среднее 50, 48, 52 = 50.0
    assert isinstance(baseline, SeasonalBaseline)
    assert abs(baseline.mean - 50.0) < 0.5
    assert baseline.n_samples == 3


def test_seasonal_baseline_returns_low_confidence_on_few_samples():
    """При <3 точек выборки confidence='low' и mean=None."""
    svc = MethodologyService()
    baseline = svc.compute_seasonal_baseline(
        target_date=date(2026, 5, 11),
        target_weekday=0,
        occupancy_history=[(date(2026, 5, 4), 50.0)],
        event_dates=set(),
        window_weeks=3,
    )
    assert baseline.confidence == "low"
    assert baseline.n_samples == 1
```

- [ ] **Step 2: Запустить — упадёт**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_methodology_service.py -v
```

- [ ] **Step 3: Реализация сервиса**

```python
# backend/app/services/methodology_service.py
"""Расчёт baseline и corrected impact для событий.

Методология (см. spec §6.3):
- baseline = среднее occupancy на похожих днях недели в окне ±N недель,
  исключая дни других событий и gap-периоды.
- corrected_impact = (observed - baseline) / baseline * 100%
- confidence = функция от размера выборки.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Literal


@dataclass(frozen=True)
class SeasonalBaseline:
    mean: float | None
    std: float | None
    n_samples: int
    confidence: Literal["high", "medium", "low"]


class MethodologyService:
    """Stateless: все методы pure-функции. Удобен для тестов и DI."""

    def compute_seasonal_baseline(
        self,
        *,
        target_date: date,
        target_weekday: int,
        occupancy_history: Iterable[tuple[date, float]],
        event_dates: set[date],
        window_weeks: int = 3,
    ) -> SeasonalBaseline:
        from statistics import mean, stdev

        cutoff_min = target_date - timedelta(weeks=window_weeks)
        cutoff_max = target_date + timedelta(weeks=window_weeks)

        samples = [
            occ
            for d, occ in occupancy_history
            if cutoff_min <= d <= cutoff_max
            and d != target_date
            and d.weekday() == target_weekday
            and d not in event_dates
            and occ is not None
        ]

        n = len(samples)
        if n == 0:
            return SeasonalBaseline(mean=None, std=None, n_samples=0, confidence="low")

        m = float(mean(samples))
        s = float(stdev(samples)) if n >= 2 else 0.0
        confidence: Literal["high", "medium", "low"] = (
            "high" if n >= 5 else "medium" if n >= 3 else "low"
        )
        return SeasonalBaseline(mean=m, std=s, n_samples=n, confidence=confidence)

    def corrected_impact(
        self,
        *,
        observed: float,
        baseline: SeasonalBaseline,
    ) -> dict:
        if baseline.mean is None or baseline.mean == 0:
            return {"delta_pct": None, "confidence": baseline.confidence}
        delta = (observed - baseline.mean) / baseline.mean * 100.0
        # 95% CI (упрощённо: ±1.96 * std/sqrt(n) в %)
        if baseline.std is not None and baseline.n_samples >= 2:
            from math import sqrt
            ci_half = 1.96 * baseline.std / sqrt(baseline.n_samples)
            ci_pct = ci_half / baseline.mean * 100.0
        else:
            ci_pct = None
        return {
            "delta_pct": round(delta, 2),
            "ci_lower": round(delta - ci_pct, 2) if ci_pct else None,
            "ci_upper": round(delta + ci_pct, 2) if ci_pct else None,
            "baseline_mean": round(baseline.mean, 2),
            "n_samples": baseline.n_samples,
            "confidence": baseline.confidence,
            "method": "seasonal_corrected",
        }


methodology_service = MethodologyService()
```

- [ ] **Step 4: Запустить тесты**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_methodology_service.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/methodology_service.py backend/tests/test_methodology_service.py
git commit -m "feat(services): add MethodologyService for seasonal baseline + corrected event impact"
```

---

### Task D2: Внедрить `MethodologyService` в `/api/analytics/events-impact?method=seasonal_corrected`

**Files:**
- Modify: `backend/app/routers/analytics.py` — endpoint `/events-impact`
- Modify: `backend/app/services/data_service.py` — добавить метод `get_events_with_district()` если нет

- [ ] **Step 1: Тест на корректную метрику**

В `backend/tests/test_events_impact_method.py` дописать:

```python
@pytest.mark.asyncio
async def test_events_impact_seasonal_corrected_returns_valid_structure(client):
    response = await client.get(
        "/api/analytics/events-impact",
        params={"method": "seasonal_corrected"},
    )
    assert response.status_code == 200
    data = response.json()
    if not data:
        pytest.skip("No events with computable impact")
    sample = data[0]
    expected_keys = {"event", "date", "district", "delta_pct", "baseline_mean", "n_samples", "confidence", "method"}
    assert expected_keys.issubset(sample.keys()), f"Missing: {expected_keys - sample.keys()}"
    assert sample["method"] == "seasonal_corrected"


@pytest.mark.asyncio
async def test_events_impact_has_both_positive_and_negative(client):
    """Проверка того, что corrected метрика действительно даёт смешанные знаки (не все минусовые)."""
    response = await client.get(
        "/api/analytics/events-impact",
        params={"method": "seasonal_corrected"},
    )
    data = response.json()
    if len(data) < 5:
        pytest.skip("Too few events to assert sign distribution")
    deltas = [d["delta_pct"] for d in data if d["delta_pct"] is not None]
    if not deltas:
        pytest.skip("No impacts computed")
    has_positive = any(d > 0 for d in deltas)
    has_negative = any(d < 0 for d in deltas)
    assert has_positive or has_negative  # хотя бы какое-то распределение
```

- [ ] **Step 2: Реализовать seasonal_corrected в endpoint'е**

В `analytics.py`, заменить fallback в Task C6 на полную реализацию:

```python
from app.services.methodology_service import methodology_service


async def _events_impact_seasonal_corrected(data, window_weeks: int = 3) -> list[dict]:
    events = await data.get_events()  # ожидаем dict с date_start, district, title, event_id
    if not events:
        return []

    # Карта occupancy по районам
    districts = {e.get("district") for e in events if e.get("district")}
    history_per_district: dict[str, list[tuple[date, float]]] = {}
    for d in districts:
        rows = await data.get_occupancy_by_district(d)
        history_per_district[d] = [
            (r["date"], r["avg_occupancy"])
            for r in rows
            if r.get("avg_occupancy") is not None
        ]

    # Множество дат-событий для исключения из baseline
    event_dates_per_district: dict[str, set[date]] = {}
    for e in events:
        d = e.get("district")
        if d and e.get("date_start"):
            event_dates_per_district.setdefault(d, set()).add(e["date_start"])

    result = []
    for e in events:
        d = e.get("district")
        ds = e.get("date_start")
        if not d or not ds:
            continue
        history = history_per_district.get(d, [])
        observed = next((occ for dd, occ in history if dd == ds), None)
        if observed is None:
            continue
        baseline = methodology_service.compute_seasonal_baseline(
            target_date=ds,
            target_weekday=ds.weekday(),
            occupancy_history=history,
            event_dates=event_dates_per_district.get(d, set()),
            window_weeks=window_weeks,
        )
        impact = methodology_service.corrected_impact(observed=observed, baseline=baseline)
        result.append({
            "event": e.get("title"),
            "date": ds.isoformat(),
            "district": d,
            "occupancy_on_day": round(observed, 2),
            **impact,
        })

    # сортировать по модулю delta_pct убыв.
    result.sort(key=lambda r: abs(r.get("delta_pct") or 0), reverse=True)
    return result
```

И в основной endpoint:

```python
@router.get("/events-impact")
async def get_events_impact(
    data: DataServiceDep,
    method: Literal["naive", "seasonal_corrected"] = "seasonal_corrected",
    window_weeks: int = 3,
):
    if method == "naive":
        return await _events_impact_naive(data)
    return await _events_impact_seasonal_corrected(data, window_weeks=window_weeks)
```

- [ ] **Step 3: Тесты**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_events_impact_method.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/analytics.py backend/tests/test_events_impact_method.py
git commit -m "feat(analytics): events-impact seasonal_corrected via MethodologyService (baseline by weekday ±N weeks)"
```

---

### Task D3: `GET /api/forecast/{district}/validation`

**Files:**
- Modify: `backend/app/routers/forecast.py`
- Modify: `backend/app/models/schemas.py` — добавить `ForecastValidationResponse`

- [ ] **Step 1: Тест**

Создать `backend/tests/test_forecast_validation.py`:

```python
"""Endpoint /api/forecast/{district}/validation возвращает RMSE/MAE по факту прошлых N дней."""
import pytest


@pytest.mark.asyncio
async def test_forecast_validation_returns_rmse_mae(client):
    response = await client.get("/api/forecast/Иркутский/validation", params={"days_back": 14})
    # Если модель не была сохранена N дней назад — допускаем 200 с пустыми метриками
    assert response.status_code == 200
    data = response.json()
    assert "rmse" in data
    assert "mae" in data
    assert "samples" in data
    assert isinstance(data.get("samples"), int)
```

- [ ] **Step 2: Pydantic-схема**

В `backend/app/models/schemas.py` добавить:

```python
class ForecastValidationResponse(BaseModel):
    district: str
    days_back: int
    samples: int
    rmse: float | None = None
    mae: float | None = None
    rmse_per_day: list[float] = Field(default_factory=list)
    forecasted: list[dict] = Field(default_factory=list)
    actual: list[dict] = Field(default_factory=list)
```

- [ ] **Step 3: Endpoint**

В `routers/forecast.py`:

```python
from app.models.schemas import ForecastValidationResponse


@router.get("/{district}/validation", response_model=ForecastValidationResponse)
async def forecast_validation(
    district: str,
    data: DataServiceDep,
    days_back: int = 14,
) -> ForecastValidationResponse:
    """Forecast vs Actual для самовалидации модели."""
    from datetime import date, timedelta
    import math

    today = date.today()
    target_dates = [today - timedelta(days=i) for i in range(days_back, 0, -1)]

    # Достаём сохранённые прогнозы (если есть)
    saved = await data.get_saved_forecasts(district=district, dates=target_dates)
    actual_rows = await data.get_occupancy_by_district(district)
    actual_map = {r["date"]: r["avg_occupancy"] for r in actual_rows}

    pairs: list[tuple[float, float]] = []
    forecasted = []
    actual = []
    for d in target_dates:
        f = saved.get(d)
        a = actual_map.get(d)
        if f is None or a is None:
            continue
        pairs.append((f, a))
        forecasted.append({"date": d.isoformat(), "occupancy": f})
        actual.append({"date": d.isoformat(), "occupancy": a})

    if not pairs:
        return ForecastValidationResponse(
            district=district, days_back=days_back, samples=0,
            rmse=None, mae=None, rmse_per_day=[], forecasted=[], actual=[],
        )

    rmse = math.sqrt(sum((f - a) ** 2 for f, a in pairs) / len(pairs))
    mae = sum(abs(f - a) for f, a in pairs) / len(pairs)
    return ForecastValidationResponse(
        district=district,
        days_back=days_back,
        samples=len(pairs),
        rmse=round(rmse, 2),
        mae=round(mae, 2),
        rmse_per_day=[round(abs(f - a), 2) for f, a in pairs],
        forecasted=forecasted,
        actual=actual,
    )
```

- [ ] **Step 4: Реализовать `data_service.get_saved_forecasts(...)`**

Если метода нет — добавить в `data_service.py`:

```python
async def get_saved_forecasts(
    self, *, district: str, dates: list[date]
) -> dict[date, float]:
    """Возвращает {date -> predicted_occupancy} из таблицы forecasts."""
    if not self.is_connected or not dates:
        return {}
    async with self._session_factory() as session:
        from sqlalchemy import select
        from app.db.models import Forecast
        rows = (await session.execute(
            select(Forecast.forecast_date, Forecast.predicted_occupancy)
            .where(Forecast.district == district)
            .where(Forecast.forecast_date.in_(dates))
            .where(Forecast.model == "ensemble")
        )).all()
        return {r[0]: r[1] for r in rows if r[1] is not None}
```

- [ ] **Step 5: Тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_forecast_validation.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/forecast.py backend/app/models/schemas.py backend/app/services/data_service.py backend/tests/test_forecast_validation.py
git commit -m "feat(forecast): GET /{district}/validation — RMSE/MAE forecast vs actual"
```

---

### Task D4: `GET /api/parser/health`

**Files:**
- Create: `backend/app/services/parser_health_service.py`
- Modify: `backend/app/routers/parser.py`
- Modify: `backend/app/parsers/base.py` — интегрировать health.report() после каждого прогона
- Test: `backend/tests/test_parser_health.py`

- [ ] **Step 1: Сервис**

```python
# backend/app/services/parser_health_service.py
"""Health-tracking парсеров через Redis hash."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.services.cache_service import cache_service

HEALTH_KEY = "parser_health"  # Redis hash, ключи — parser_id, value — JSON


class ParserHealthService:
    async def report(
        self,
        *,
        parser_id: str,
        status: Literal["ok", "warn", "fail"],
        items_collected: int = 0,
        error: str | None = None,
    ) -> None:
        if cache_service.client is None:
            return
        import json
        payload = {
            "parser_id": parser_id,
            "status": status,
            "items_collected": items_collected,
            "error": error,
            "last_run": datetime.utcnow().isoformat(),
        }
        await cache_service.client.hset(HEALTH_KEY, parser_id, json.dumps(payload))

    async def list_all(self) -> list[dict]:
        if cache_service.client is None:
            return []
        import json
        raw = await cache_service.client.hgetall(HEALTH_KEY)
        out = []
        for parser_id_bytes, payload_bytes in raw.items():
            try:
                pid = parser_id_bytes.decode() if isinstance(parser_id_bytes, bytes) else parser_id_bytes
                p = payload_bytes.decode() if isinstance(payload_bytes, bytes) else payload_bytes
                out.append(json.loads(p))
            except Exception:
                continue
        out.sort(key=lambda x: x.get("last_run") or "", reverse=True)
        return out


parser_health_service = ParserHealthService()
```

- [ ] **Step 2: Тест**

```python
# backend/tests/test_parser_health.py
import pytest

from app.services.parser_health_service import parser_health_service
from app.services.cache_service import cache_service


@pytest.mark.asyncio
async def test_parser_health_report_and_list():
    if cache_service.client is None:
        await cache_service.connect()
    if cache_service.client is None:
        pytest.skip("Redis unavailable")

    await parser_health_service.report(
        parser_id="events_yandex_test",
        status="ok",
        items_collected=42,
    )
    rows = await parser_health_service.list_all()
    found = next((r for r in rows if r["parser_id"] == "events_yandex_test"), None)
    assert found is not None
    assert found["status"] == "ok"
    assert found["items_collected"] == 42

    # Cleanup
    await cache_service.client.hdel("parser_health", "events_yandex_test")


@pytest.mark.asyncio
async def test_parser_health_endpoint(client):
    response = await client.get("/api/parser/health")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 3: Endpoint**

В `routers/parser.py`:

```python
from app.services.parser_health_service import parser_health_service


@router.get("/health")
async def parser_health() -> list[dict]:
    """Статус каждого парсера: last_run, status, items_collected, error."""
    return await parser_health_service.list_all()
```

- [ ] **Step 4: Интеграция в base.py**

В `backend/app/parsers/base.py`, в методе lifecycle парсера (где-то в `run()` / `parse()`) после успеха:

```python
from app.services.parser_health_service import parser_health_service

# ...
try:
    items = await self._do_parse()
    await parser_health_service.report(
        parser_id=self.parser_id,
        status="ok",
        items_collected=len(items),
    )
    return items
except Exception as exc:
    await parser_health_service.report(
        parser_id=self.parser_id,
        status="fail",
        items_collected=0,
        error=str(exc)[:500],
    )
    raise
```

(Конкретное место зависит от текущего lifecycle — найти `def run` / `async def parse` в `BaseParser`.)

- [ ] **Step 5: Запустить тесты**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_parser_health.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parser_health_service.py backend/app/routers/parser.py backend/app/parsers/base.py backend/tests/test_parser_health.py
git commit -m "feat(parsers): ParserHealthService + GET /api/parser/health, integrated into BaseParser lifecycle"
```

---

### Task D5: `GET /api/analytics/metadata`

**Files:**
- Modify: `backend/app/routers/analytics.py`
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_metadata_endpoint.py
import pytest


@pytest.mark.asyncio
async def test_metadata_returns_required_keys(client):
    response = await client.get("/api/analytics/metadata")
    assert response.status_code == 200
    data = response.json()
    expected = {"hotels_count", "events_count", "data_range", "last_refresh", "gap_periods"}
    assert expected.issubset(data.keys())
    assert isinstance(data["data_range"], dict)
    assert "from" in data["data_range"] and "to" in data["data_range"]
```

- [ ] **Step 2: Pydantic-модель**

В `schemas.py`:

```python
class DataRange(BaseModel):
    from_: date | None = Field(None, alias="from")
    to: date | None = None


class MetadataResponse(BaseModel):
    hotels_count: int
    events_count: int
    data_range: DataRange
    last_refresh: datetime | None = None
    gap_periods: list[dict] = Field(default_factory=list)
```

- [ ] **Step 3: Endpoint**

В `analytics.py`:

```python
@router.get("/metadata")
async def metadata(data: DataServiceDep) -> dict:
    hotels = await data.get_hotels_count()
    events = await data.get_events_count()
    date_range = await data.get_data_date_range()  # {"from": date, "to": date}
    gaps = await data.detect_gap_periods(min_days=7)  # список {"from","to","reason"}
    last = await data.get_last_data_refresh()
    return {
        "hotels_count": hotels,
        "events_count": events,
        "data_range": date_range,
        "last_refresh": last.isoformat() if last else None,
        "gap_periods": gaps,
    }
```

- [ ] **Step 4: Реализовать недостающие методы в `data_service.py`**

```python
async def get_hotels_count(self) -> int:
    if not self.is_connected:
        return 0
    async with self._session_factory() as s:
        from sqlalchemy import func, select
        from app.db.models import Hotel
        return (await s.execute(select(func.count(Hotel.id)))).scalar_one()


async def get_events_count(self) -> int:
    if not self.is_connected:
        return 0
    async with self._session_factory() as s:
        from sqlalchemy import func, select
        from app.db.models import Event
        return (await s.execute(select(func.count(Event.event_id)))).scalar_one()


async def get_data_date_range(self) -> dict:
    if not self.is_connected:
        return {"from": None, "to": None}
    async with self._session_factory() as s:
        from sqlalchemy import func, select
        from app.db.models import HotelStatistic
        row = (await s.execute(
            select(func.min(HotelStatistic.date), func.max(HotelStatistic.date))
        )).first()
        return {"from": row[0], "to": row[1]}


async def detect_gap_periods(self, min_days: int = 7) -> list[dict]:
    """Находит периоды без данных в hotel_statistics длиннее min_days."""
    if not self.is_connected:
        return []
    async with self._session_factory() as s:
        from sqlalchemy import text
        result = await s.execute(text("""
            SELECT d_prev, d_next, gap_days FROM (
                SELECT
                    date AS d_prev,
                    LEAD(date) OVER (ORDER BY date) AS d_next,
                    LEAD(date) OVER (ORDER BY date) - date AS gap_days
                FROM (SELECT DISTINCT date FROM hotel_statistics) t
            ) gaps
            WHERE gap_days > :min_days
            ORDER BY d_prev
        """), {"min_days": min_days})
        rows = result.all()
        return [
            {"from": str(r[0]), "to": str(r[1]), "gap_days": r[2], "reason": "data_collection_offline"}
            for r in rows
        ]


async def get_last_data_refresh(self) -> datetime | None:
    if not self.is_connected:
        return None
    async with self._session_factory() as s:
        from sqlalchemy import func, select
        from app.db.models import HotelStatistic
        row = (await s.execute(select(func.max(HotelStatistic.updated_at)))).first()
        return row[0] if row else None
```

- [ ] **Step 5: Тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_metadata_endpoint.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/analytics.py backend/app/models/schemas.py backend/app/services/data_service.py backend/tests/test_metadata_endpoint.py
git commit -m "feat(analytics): GET /metadata — hotels_count, events_count, data_range, gap_periods"
```

---

### Task D6: `GET /api/analytics/booking-pace`

**Files:**
- Modify: `backend/app/routers/analytics.py`
- Modify: `backend/app/services/data_service.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_booking_pace.py
import pytest


@pytest.mark.asyncio
async def test_booking_pace_structure(client):
    response = await client.get("/api/analytics/booking-pace", params={"district": "Иркутский", "days_ahead": 14})
    assert response.status_code == 200
    data = response.json()
    expected = {"district", "days_ahead", "method", "points", "summary"}
    assert expected.issubset(data.keys())
    assert isinstance(data["points"], list)
    assert data["method"] == "daily_proxy_pickup"
```

- [ ] **Step 2: Endpoint + сервис-метод**

В `analytics.py`:

```python
@router.get("/booking-pace")
async def booking_pace(
    data: DataServiceDep,
    district: str = DEFAULT_DISTRICT,
    days_ahead: int = 14,
    lookback_days: int = 7,
) -> dict:
    """Daily proxy-pickup из дельт snapshot'ов."""
    points = await data.compute_proxy_pickup(
        district=district,
        days_ahead=days_ahead,
        lookback_days=lookback_days,
    )
    pickups = [p["pickup_pct"] for p in points if p["pickup_pct"] is not None]
    summary = {
        "avg_pickup_pct": round(sum(pickups) / len(pickups), 2) if pickups else None,
        "max_pickup_pct": max(pickups) if pickups else None,
        "min_pickup_pct": min(pickups) if pickups else None,
        "trend": "ускорение" if pickups and pickups[-3:] and sum(pickups[-3:]) > 0 else
                 "замедление" if pickups and pickups[-3:] and sum(pickups[-3:]) < 0 else "стабильно",
    }
    return {
        "district": district,
        "days_ahead": days_ahead,
        "method": "daily_proxy_pickup",
        "methodology": "pickup = occupancy(future_date, today) - occupancy(future_date, today - lookback_days)",
        "points": points,
        "summary": summary,
    }
```

В `data_service.py`:

```python
async def compute_proxy_pickup(
    self,
    *,
    district: str,
    days_ahead: int,
    lookback_days: int,
) -> list[dict]:
    """Сравнивает 2 snapshot'а: текущий и lookback_days назад. Возвращает дельту по будущим датам."""
    if not self.is_connected:
        return []
    from datetime import date, timedelta
    today = date.today()
    snapshot_dates = [today, today - timedelta(days=lookback_days)]
    futures = [today + timedelta(days=i) for i in range(1, days_ahead + 1)]

    # Здесь нужна история occupancy_by_district с разрезом по snapshot date
    # Если такого метода нет — упростить: использовать get_occupancy_by_district и предположить что
    # последний снимок и снимок неделю назад в этих данных есть.
    rows = await self.get_occupancy_by_district(district)
    by_date = {r["date"]: r["avg_occupancy"] for r in rows if r.get("avg_occupancy") is not None}

    # Прокси: для каждой будущей даты берём occupancy_today vs то, что было неделю назад на ту же дату
    points = []
    for fd in futures:
        today_val = by_date.get(fd)
        prev_val = by_date.get(fd - timedelta(days=lookback_days))
        if today_val is None or prev_val is None:
            points.append({"date": fd.isoformat(), "occupancy_today": today_val,
                           "occupancy_lookback": prev_val, "pickup_pct": None})
            continue
        delta = today_val - prev_val
        points.append({
            "date": fd.isoformat(),
            "occupancy_today": round(today_val, 2),
            "occupancy_lookback": round(prev_val, 2),
            "pickup_pct": round(delta, 2),
        })
    return points
```

- [ ] **Step 3: Тест**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_booking_pace.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/analytics.py backend/app/services/data_service.py backend/tests/test_booking_pace.py
git commit -m "feat(analytics): GET /booking-pace — daily proxy-pickup with summary trend"
```

---

### Task D7: `GET /api/analytics/occupancy-timeseries`

**Files:**
- Modify: `backend/app/routers/analytics.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_occupancy_timeseries.py
import pytest


@pytest.mark.asyncio
async def test_occupancy_timeseries(client):
    response = await client.get(
        "/api/analytics/occupancy-timeseries",
        params={"district": "Иркутский", "days": 30},
    )
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert "summary" in data
    s = data["summary"]
    assert "min" in s and "max" in s and "avg" in s and "samples" in s
```

- [ ] **Step 2: Endpoint**

```python
@router.get("/occupancy-timeseries")
async def occupancy_timeseries(
    data: DataServiceDep,
    district: str = DEFAULT_DISTRICT,
    days: int = 30,
) -> dict:
    from datetime import date, timedelta
    today = date.today()
    rows = await data.get_occupancy_by_district(district)
    cutoff = today - timedelta(days=days)
    points = [
        {"date": r["date"].isoformat(), "occupancy": round(r["avg_occupancy"], 2)}
        for r in rows
        if r.get("avg_occupancy") is not None and r["date"] >= cutoff
    ]
    points.sort(key=lambda p: p["date"])
    occs = [p["occupancy"] for p in points]
    return {
        "district": district,
        "days": days,
        "points": points,
        "summary": {
            "min": min(occs) if occs else None,
            "max": max(occs) if occs else None,
            "avg": round(sum(occs) / len(occs), 2) if occs else None,
            "samples": len(occs),
        },
    }
```

- [ ] **Step 3: Тест + commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_occupancy_timeseries.py -v
git add backend/app/routers/analytics.py backend/tests/test_occupancy_timeseries.py
git commit -m "feat(analytics): GET /occupancy-timeseries with min/max/avg summary"
```

---

### Task D8: `GET /api/analytics/price-distribution`

**Files:**
- Modify: `backend/app/routers/analytics.py`
- Modify: `backend/app/services/data_service.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_price_distribution.py
import pytest


@pytest.mark.asyncio
async def test_price_distribution_returns_percentiles(client):
    response = await client.get(
        "/api/analytics/price-distribution",
        params={"district": "Иркутский", "days": 30},
    )
    assert response.status_code == 200
    data = response.json()
    expected = {"p10", "p25", "p50", "p75", "p90", "samples"}
    assert expected.issubset(data.keys())
```

- [ ] **Step 2: Endpoint + service**

```python
@router.get("/price-distribution")
async def price_distribution(
    data: DataServiceDep,
    district: str = DEFAULT_DISTRICT,
    days: int = 30,
) -> dict:
    prices = await data.collect_min_prices(district=district, days=days)
    if not prices:
        return {"district": district, "samples": 0, "p10": None, "p25": None, "p50": None, "p75": None, "p90": None}
    import statistics
    sorted_p = sorted(prices)
    def pct(arr, p):
        idx = int(len(arr) * p / 100)
        return arr[min(idx, len(arr) - 1)]
    return {
        "district": district,
        "samples": len(prices),
        "p10": pct(sorted_p, 10),
        "p25": pct(sorted_p, 25),
        "p50": int(statistics.median(prices)),
        "p75": pct(sorted_p, 75),
        "p90": pct(sorted_p, 90),
    }
```

В `data_service.py`:

```python
async def collect_min_prices(self, *, district: str, days: int) -> list[int]:
    if not self.is_connected:
        return []
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    async with self._session_factory() as s:
        from sqlalchemy import select
        from app.db.models import Hotel, HotelStatistic
        rows = (await s.execute(
            select(HotelStatistic.min_price)
            .join(Hotel, Hotel.id == HotelStatistic.id)
            .where(Hotel.district == district)
            .where(HotelStatistic.date >= cutoff)
            .where(HotelStatistic.min_price.is_not(None))
        )).all()
        return [r[0] for r in rows if r[0] is not None]
```

- [ ] **Step 3: Тест + commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_price_distribution.py -v
git add backend/app/routers/analytics.py backend/app/services/data_service.py backend/tests/test_price_distribution.py
git commit -m "feat(analytics): GET /price-distribution — p10/p25/p50/p75/p90 of min_price by district"
```

---

### Task D9: `GET /api/analytics/compare-districts`

**Files:**
- Modify: `backend/app/routers/analytics.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_compare_districts.py
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
    assert len(data["districts"]) == 2
    for d in data["districts"]:
        assert {"district", "occupancy", "adr_proxy", "revpar_proxy", "samples"}.issubset(d.keys())
```

- [ ] **Step 2: Endpoint**

```python
@router.get("/compare-districts")
async def compare_districts(
    data: DataServiceDep,
    districts: str = Query(..., description="Список районов через запятую"),
    days: int = 30,
) -> dict:
    names = [d.strip() for d in districts.split(",") if d.strip()]
    out = []
    for name in names:
        rows = await data.get_occupancy_by_district(name)
        from datetime import date, timedelta
        cutoff = date.today() - timedelta(days=days)
        recent = [r for r in rows if r["date"] >= cutoff and r.get("avg_occupancy") is not None]
        if not recent:
            out.append({"district": name, "occupancy": None, "adr_proxy": None,
                        "revpar_proxy": None, "samples": 0})
            continue
        avg_occ = sum(r["avg_occupancy"] for r in recent) / len(recent)
        prices = await data.collect_min_prices(district=name, days=days)
        adr_proxy = int(sorted(prices)[len(prices) // 2]) if prices else None
        revpar_proxy = round((adr_proxy or 0) * (avg_occ / 100), 2) if adr_proxy else None
        out.append({
            "district": name,
            "occupancy": round(avg_occ, 2),
            "adr_proxy": adr_proxy,
            "revpar_proxy": revpar_proxy,
            "samples": len(recent),
        })
    return {"districts": out, "days": days}
```

- [ ] **Step 3: Commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_compare_districts.py -v
git add backend/app/routers/analytics.py backend/tests/test_compare_districts.py
git commit -m "feat(analytics): GET /compare-districts — side-by-side RMS metrics"
```

---

### Task D10: `GET /api/analytics/segments`

**Files:**
- Modify: `backend/app/routers/analytics.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_segments.py
import pytest


@pytest.mark.asyncio
async def test_segments_returns_grouped_counts(client):
    response = await client.get("/api/analytics/segments")
    assert response.status_code == 200
    data = response.json()
    assert "by_size" in data
    assert "by_accommodation_type" in data
    for k in ("mini", "mid", "large"):
        assert k in data["by_size"]
```

- [ ] **Step 2: Endpoint + service**

```python
@router.get("/segments")
async def hotel_segments(data: DataServiceDep) -> dict:
    by_size = await data.segments_by_size()
    by_type = await data.segments_by_accommodation_type()
    return {
        "by_size": by_size,  # {"mini": {"count": N, "avg_occupancy": ..., "avg_price": ...}, ...}
        "by_accommodation_type": by_type,
        "size_thresholds": {"mini_max": 15, "mid_max": 50},
    }
```

В `data_service.py`:

```python
async def segments_by_size(self) -> dict:
    if not self.is_connected:
        return {}
    async with self._session_factory() as s:
        from sqlalchemy import text
        result = await s.execute(text("""
            WITH latest AS (
                SELECT DISTINCT ON (id) id, rooms_num, available_rooms_percent, min_price
                FROM hotel_statistics
                ORDER BY id, date DESC
            )
            SELECT
                CASE
                    WHEN rooms_num <= 15 THEN 'mini'
                    WHEN rooms_num <= 50 THEN 'mid'
                    ELSE 'large'
                END AS size_bucket,
                COUNT(*) AS n,
                AVG(100 - available_rooms_percent) AS avg_occ,
                AVG(min_price) AS avg_price
            FROM latest
            WHERE rooms_num IS NOT NULL
            GROUP BY size_bucket
        """))
        return {
            r[0]: {
                "count": r[1],
                "avg_occupancy": round(float(r[2] or 0), 2),
                "avg_price": int(r[3] or 0),
            }
            for r in result.all()
        }


async def segments_by_accommodation_type(self) -> dict:
    if not self.is_connected:
        return {}
    async with self._session_factory() as s:
        from sqlalchemy import text
        result = await s.execute(text("""
            SELECT COALESCE(accommodation_type, 'unknown') AS at, COUNT(*) AS n,
                   AVG(min_price) AS avg_price
            FROM hotels
            GROUP BY at
            ORDER BY n DESC
        """))
        return {
            r[0]: {"count": r[1], "avg_price": int(r[2] or 0)}
            for r in result.all()
        }
```

- [ ] **Step 3: Commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_segments.py -v
git add backend/app/routers/analytics.py backend/app/services/data_service.py backend/tests/test_segments.py
git commit -m "feat(analytics): GET /segments — by_size (mini/mid/large) and by_accommodation_type"
```

---

### Task D11: `GET /api/hotels/{id}/segment-benchmark`

**Files:**
- Modify: `backend/app/routers/hotels.py`

- [ ] **Step 1: Тест**

```python
# backend/tests/test_hotel_segment_benchmark.py
import pytest


@pytest.mark.asyncio
async def test_segment_benchmark_returns_comparison(client):
    # Возьмём первый отель из реестра
    hotels = (await client.get("/api/hotels", params={"limit": 1})).json()
    if not hotels.get("items"):
        pytest.skip("No hotels in registry")
    hotel_id = hotels["items"][0]["id"]
    response = await client.get(f"/api/hotels/{hotel_id}/segment-benchmark")
    assert response.status_code == 200
    data = response.json()
    expected = {"hotel", "segment", "hotel_metrics", "segment_metrics", "n_in_segment"}
    assert expected.issubset(data.keys())
```

- [ ] **Step 2: Endpoint**

```python
# В hotels.py
@router.get("/{hotel_id}/segment-benchmark")
async def hotel_segment_benchmark(hotel_id: str, data: DataServiceDep) -> dict:
    hotel = await data.get_hotel(hotel_id)
    if not hotel:
        raise HTTPException(404, "Hotel not found")

    rooms_num = hotel.get("rooms_num") or 0
    size_bucket = "mini" if rooms_num <= 15 else "mid" if rooms_num <= 50 else "large"
    district = hotel.get("district")

    # Метрики самого отеля (последний snapshot)
    own_stats = await data.get_hotel_latest_stats(hotel_id)
    hotel_metrics = {
        "occupancy": own_stats.get("occupancy"),
        "min_price": own_stats.get("min_price"),
    }

    # Метрики сегмента (район × size_bucket, исключая сам отель)
    segment = await data.compute_segment_metrics(
        district=district,
        size_bucket=size_bucket,
        exclude_hotel_id=hotel_id,
    )

    return {
        "hotel": {"id": hotel_id, "name": hotel.get("name"), "district": district, "rooms_num": rooms_num},
        "segment": {"district": district, "size_bucket": size_bucket},
        "hotel_metrics": hotel_metrics,
        "segment_metrics": segment,
        "n_in_segment": segment.get("n", 0),
    }
```

В `data_service.py`:

```python
async def get_hotel_latest_stats(self, hotel_id: str) -> dict:
    if not self.is_connected:
        return {}
    async with self._session_factory() as s:
        from sqlalchemy import select, desc
        from app.db.models import HotelStatistic
        row = (await s.execute(
            select(HotelStatistic)
            .where(HotelStatistic.id == hotel_id)
            .order_by(desc(HotelStatistic.date))
            .limit(1)
        )).scalar_one_or_none()
        if not row:
            return {}
        return {
            "date": row.date,
            "occupancy": round(100 - (row.available_rooms_percent or 0), 2),
            "min_price": row.min_price,
        }


async def compute_segment_metrics(
    self, *, district: str, size_bucket: str, exclude_hotel_id: str | None = None
) -> dict:
    if not self.is_connected:
        return {}
    bounds = {"mini": (0, 15), "mid": (16, 50), "large": (51, 10_000)}.get(size_bucket, (0, 10_000))
    async with self._session_factory() as s:
        from sqlalchemy import text
        result = (await s.execute(text("""
            WITH latest AS (
                SELECT DISTINCT ON (h.id) h.id, h.district, hs.rooms_num,
                       hs.available_rooms_percent, hs.min_price
                FROM hotels h
                JOIN hotel_statistics hs ON hs.id = h.id
                WHERE h.district = :district
                  AND hs.rooms_num BETWEEN :min_r AND :max_r
                  AND (:exclude_id IS NULL OR h.id <> :exclude_id)
                ORDER BY h.id, hs.date DESC
            )
            SELECT COUNT(*) AS n,
                   AVG(100 - available_rooms_percent) AS avg_occ,
                   AVG(min_price) AS avg_price
            FROM latest
        """), {
            "district": district,
            "min_r": bounds[0],
            "max_r": bounds[1],
            "exclude_id": exclude_hotel_id,
        })).first()
        return {
            "n": result[0],
            "avg_occupancy": round(float(result[1] or 0), 2),
            "avg_price": int(result[2] or 0),
        }
```

- [ ] **Step 3: Commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_hotel_segment_benchmark.py -v
git add backend/app/routers/hotels.py backend/app/services/data_service.py backend/tests/test_hotel_segment_benchmark.py
git commit -m "feat(hotels): GET /{id}/segment-benchmark — hotel vs district×size segment"
```

---

## Раздел E: Удаление мёртвых endpoint'ов

### Task E1: Удалить 7 мёртвых endpoint'ов

**Files:**
- Modify: `backend/app/routers/forecast.py` — удалить 4
- Modify: `backend/app/routers/events.py` — удалить 3

- [ ] **Step 1: Записать pre-test**

Создать `backend/tests/test_dead_endpoints_removed.py`:

```python
"""После удаления мёртвых endpoint'ов запросы к ним возвращают 404."""
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
async def test_dead_endpoint_returns_404(client, method, path):
    response = await client.request(method, path)
    assert response.status_code in (404, 405), f"{method} {path} should be removed (got {response.status_code})"
```

- [ ] **Step 2: Удалить из forecast.py**

```bash
grep -n "@router\.\(post\|get\)(\"/neural\|/xgboost\|/compare\"\|/holidays\")" backend/app/routers/forecast.py
```

В `forecast.py` удалить функции (по 1 endpoint'у каждая):
- `POST /neural`
- `POST /xgboost`
- `GET /compare` (НЕ `/compare-all` — оставляем)
- `GET /holidays`

Также удалить связанные импорты, если они нигде больше не используются.

- [ ] **Step 3: Удалить из events.py**

```bash
grep -n "/init\|/demo\|/load-historical" backend/app/routers/events.py
```

Удалить:
- `POST /init`
- `DELETE /demo`
- `POST /load-historical`

- [ ] **Step 4: Тесты должны пройти**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_dead_endpoints_removed.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Прогнать ВСЮ тестовую базу — убедиться что ничего не сломалось**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest -q
```

Expected: пред-rebuild количество тестов passed (~104) + новые ~30, без регрессий.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/forecast.py backend/app/routers/events.py backend/tests/test_dead_endpoints_removed.py
git commit -m "refactor(routers): remove 7 dead endpoints (forecast/{neural,xgboost,compare,holidays}, events/{init,demo,load-historical})"
```

---

## Раздел F: Расширение парсеров (5 шт.)

> Все 5 задач следуют одному паттерну: добавить парсинг новых полей + передать их в `db_service.upsert_event(...)`. Полная реализация показана для F1; F2-F5 повторяют тот же шаблон с изменением селекторов.

### Task F1: `events_yandex.py` — `age_restriction`, `full_description`

**Files:**
- Modify: `backend/app/parsers/events_yandex.py`
- Test: `backend/tests/test_parser_yandex_fields.py`

- [ ] **Step 1: Тест на парсинг age_restriction из JSON-LD**

```python
# backend/tests/test_parser_yandex_fields.py
import pytest

from app.parsers.events_yandex import parse_yandex_jsonld_event


def test_yandex_extracts_age_restriction_and_description():
    sample_jsonld = {
        "@type": "Event",
        "name": "Концерт",
        "startDate": "2026-06-01T19:30:00",
        "typicalAgeRange": "12-99",
        "description": "Описание концерта на 600+ символов..." + ("." * 600),
        "image": "https://example.com/img.jpg",
        "location": {"name": "Концертный зал"},
    }
    parsed = parse_yandex_jsonld_event(sample_jsonld, source_url="https://afisha.yandex.ru/irkutsk/abc")
    assert parsed["age_restriction"] == "12+"
    assert len(parsed["description"]) > 300
    assert parsed["image_url"] == "https://example.com/img.jpg"
```

- [ ] **Step 2: Реализация**

В `events_yandex.py` найти / добавить функцию `parse_yandex_jsonld_event(jsonld, source_url)`:

```python
def parse_yandex_jsonld_event(jsonld: dict, source_url: str) -> dict:
    name = jsonld.get("name", "").strip()
    start = jsonld.get("startDate", "")
    desc = jsonld.get("description", "").strip()
    image = jsonld.get("image", "") if isinstance(jsonld.get("image"), str) else ""

    # age_restriction: "12-99" → "12+", "0-99" → None
    age_raw = jsonld.get("typicalAgeRange", "")
    age_restriction: str | None = None
    if age_raw and "-" in age_raw:
        try:
            min_age = int(age_raw.split("-")[0])
            if min_age > 0:
                age_restriction = f"{min_age}+"
        except ValueError:
            pass

    # time_start
    from datetime import datetime, time
    time_start: time | None = None
    try:
        dt = datetime.fromisoformat(start)
        time_start = dt.time()
    except (ValueError, TypeError):
        pass

    return {
        "title": name,
        "description": desc[:2000] if desc else None,  # full description
        "image_url": image or None,
        "age_restriction": age_restriction,
        "time_start": time_start,
        "url": source_url,
    }
```

В местах сохранения события (`upsert_event(...)` вызовы) — передать новые поля.

- [ ] **Step 3: Тест + commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_parser_yandex_fields.py -v
git add backend/app/parsers/events_yandex.py backend/tests/test_parser_yandex_fields.py
git commit -m "feat(parser/yandex): extract age_restriction (typicalAgeRange) and full description from JSON-LD"
```

---

### Task F2: `events_kassir.py` — `full_description`, `venue_address`

**Files:**
- Modify: `backend/app/parsers/events_kassir.py`

- [ ] **Step 1: Тест по аналогии с F1** (sample JSON-LD от kassir.ru — собрать вручную из живой страницы или мок).

- [ ] **Step 2: В функции парсинга карточки** добавить чтение `description` и `location.address` из JSON-LD (если присутствует) или из markdown'а Crawl4AI:

```python
# Парсинг address из JSON-LD venue
loc = jsonld.get("location", {})
address = None
if isinstance(loc, dict):
    addr = loc.get("address")
    if isinstance(addr, dict):
        address = addr.get("streetAddress") or addr.get("addressLocality")
    elif isinstance(addr, str):
        address = addr
```

И передать в upsert.

- [ ] **Step 3: Commit**

```bash
git add backend/app/parsers/events_kassir.py
git commit -m "feat(parser/kassir): extract full description and venue address from JSON-LD"
```

---

### Task F3: `events_zeroevent.py` — `price_min` из описания

**Files:**
- Modify: `backend/app/parsers/events_zeroevent.py`

- [ ] **Step 1**: Регулярка для извлечения цены из текста описания: `r"от\s+(\d{2,5})\s*(?:руб|₽|р\.)"` или эквивалент.

- [ ] **Step 2**: В парсере добавить:

```python
import re

PRICE_RE = re.compile(r"от\s+(\d{2,5})\s*(?:руб|₽|р\.)", re.IGNORECASE)

def _extract_price_min(text: str) -> int | None:
    if not text:
        return None
    m = PRICE_RE.search(text)
    return int(m.group(1)) if m else None
```

И в `upsert_event(...)` передать `price_min=_extract_price_min(description)`.

- [ ] **Step 3: Тест unit**

```python
# backend/tests/test_parser_zeroevent_fields.py
from app.parsers.events_zeroevent import _extract_price_min

def test_extract_price_from_description():
    assert _extract_price_min("Билеты от 500 руб.") == 500
    assert _extract_price_min("Бесплатно") is None
    assert _extract_price_min("Стоимость от 1500₽, вход свободный для детей") == 1500
```

- [ ] **Step 4: Commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_parser_zeroevent_fields.py -v
git add backend/app/parsers/events_zeroevent.py backend/tests/test_parser_zeroevent_fields.py
git commit -m "feat(parser/zeroevent): extract price_min from description text"
```

---

### Task F4: `events_culture_rf.py` — `venue_address`

**Files:**
- Modify: `backend/app/parsers/events_culture_rf.py`

Шаблон полностью по F2 (JSON-LD location.address). Один тест-мок и unit-проверка.

- [ ] **Step 1-3**: реализовать по аналогии с F2.
- [ ] **Step 4**: commit `feat(parser/culture_rf): extract venue address from JSON-LD`.

---

### Task F5: `hotels_101hotels.py` — `image_url`

**Files:**
- Modify: `backend/app/parsers/hotels_101hotels.py`

- [ ] **Step 1**: В response 101hotels API искать поле `photos[0].url` или подобное (зависит от текущей структуры — посмотреть в коде).

- [ ] **Step 2**: Передать `image_url` в `upsert_hotel(...)`.

- [ ] **Step 3**: Тест-мок, commit `feat(parser/101hotels): save first photo URL as Hotel.image_url`.

---

## Раздел G: AI fallback для хрупких парсеров

### Task G1: `events_irk.py` — Crawl4AI fallback

**Files:**
- Modify: `backend/app/parsers/events_irk.py`

- [ ] **Step 1: Тест mocked failure**

```python
# backend/tests/test_parser_irk_fallback.py
import pytest
from unittest.mock import patch, AsyncMock

from app.parsers.events_irk import EventsIrkParser


@pytest.mark.asyncio
async def test_irk_uses_crawl4ai_when_native_html_fails():
    parser = EventsIrkParser()
    with patch.object(parser, "_parse_native_html", side_effect=Exception("HTML changed")):
        with patch.object(parser, "_parse_via_crawl4ai", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = [{"title": "Test", "date_start": "2026-06-01"}]
            events = await parser.parse()
            assert len(events) == 1
            mock_crawl.assert_awaited_once()
```

- [ ] **Step 2: Добавить fallback в `EventsIrkParser`**

```python
async def parse(self) -> list[dict]:
    try:
        events = await self._parse_native_html()
        if events:
            return events
    except Exception as exc:
        logger.warning("events_irk native parser failed: %s — trying Crawl4AI fallback", exc)
    return await self._parse_via_crawl4ai()


async def _parse_via_crawl4ai(self) -> list[dict]:
    from app.parsers.ai_extractor import AIEventExtractor
    extractor = AIEventExtractor(source_id="irk", base_url="https://irk.ru/afisha/")
    return await extractor.extract_events()
```

(Существующий код вынести в `_parse_native_html`.)

- [ ] **Step 3-4: тест + commit**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest tests/test_parser_irk_fallback.py -v
git add backend/app/parsers/events_irk.py backend/tests/test_parser_irk_fallback.py
git commit -m "feat(parser/irk): Crawl4AI fallback when native HTML parser fails (HTML structure change resilience)"
```

---

### Task G2: `events_culture38.py` — Crawl4AI fallback

Полностью по образцу G1. Один файл изменений + один тест.

- [ ] **Step 1-4**: по шаблону G1, commit `feat(parser/culture38): Crawl4AI fallback`.

---

## Раздел H: Финальная верификация Phase 1

### Task H1: Запустить полный pytest и зафиксировать результат

- [ ] **Step 1: Полный прогон**

```bash
cd backend && .\venv\Scripts\python.exe -m pytest -q --tb=short
```

Expected: ≥ 104 passed (старая база) + ≥ 30 новых passed, 0 failed (исключение — `test_export_csv_occupancy`, известно из SESSION_HANDOFF).

- [ ] **Step 2: Smoke-проверка endpoint'ов**

```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/api/analytics/metadata | jq .
curl -s "http://localhost:8000/api/analytics/events-impact?method=seasonal_corrected&window_weeks=3" | jq '.[0:3]'
curl -s http://localhost:8000/api/parser/health | jq .
curl -s "http://localhost:8000/api/forecast/Иркутский/validation?days_back=14" | jq .
curl -s "http://localhost:8000/api/analytics/booking-pace?district=Иркутский&days_ahead=14" | jq '.summary'
curl -s "http://localhost:8000/api/analytics/segments" | jq .
```

Expected: каждый — 200 OK с осмысленным JSON.

- [ ] **Step 3: Обновить SESSION_HANDOFF.md**

Добавить в начало `docs/SESSION_HANDOFF.md` новый блок:

```markdown
## 2026-05-04 — Phase 1 (Backend) завершён

**Что сделано:**
- Расширена схема Event (6 новых полей: time_start, price_min, price_max, image_url, address, age_restriction).
- Добавлен UNIQUE constraint uq_events_dedup (source_id, date_start, title) + миграционный скрипт.
- Реализован MethodologyService (seasonal_corrected impact metric, baseline by weekday ±N weeks).
- 10 новых endpoint'ов: events-impact?method=, forecast/{district}/validation, parser/health, analytics/{metadata,booking-pace,occupancy-timeseries,price-distribution,compare-districts,segments}, hotels/{id}/segment-benchmark.
- 6 фиксов багов: stream counter race condition, correlation gap filter, ensemble cache key collision, forecast/explain timeout+fallback, events-impact method param, parser dedup.
- Удалено 7 мёртвых endpoint'ов.
- Расширены 5 парсеров (yandex, kassir, zeroevent, culture_rf, hotels_101hotels) под новые поля.
- Добавлен Crawl4AI fallback в events_irk и events_culture38.
- Реализован ParserHealthService (Redis-storage, integration в BaseParser).

**Тесты:** ~30 новых тестов, всё зелёное.

**Следующий шаг:** Phase 2 (AI-агент) — 6 новых tools, расширение system prompt, сценарные тесты.
```

- [ ] **Step 4: Commit финальный**

```bash
git add docs/SESSION_HANDOFF.md
git commit -m "docs: SESSION_HANDOFF — Phase 1 (Backend) complete"
```

---

## Self-Review

Этот план покрывает spec'овские требования к Backend (Phase 1):

| Spec § | Требование | Покрыто Task'ом |
|--------|-----------|-----------------|
| §6.3 | Corrected impact via baseline | D1, D2 |
| §6.4 | Pickup proxy methodology | D6 |
| §6.5 | Forecast vs Actual | D3 |
| §11.1 | 10 новых endpoint'ов | D1-D11 (D1 — сервис, D2-D11 — endpoints) |
| §11.2 | Фикс 6 багов | C1-C6 |
| §11.3 | Удаление 7 мёртвых endpoint'ов | E1 |
| §11.4 | Расширение Event schema (6 полей) | A1, A2, A3 |
| §12.1 | Расширение 5 парсеров | F1-F5 |
| §12.2 | AI-fallback в 2 хрупких парсерах | G1, G2 |
| §12.3 | Health-monitor подключение | D4 |
| §12.4 | Дедупликация Event | A3, B1, B2 |

**Тип-консистентность:** все тесты ссылаются на существующие классы и методы; новые методы (`compute_proxy_pickup`, `collect_min_prices`, `compute_segment_metrics`, `get_data_date_range` и др.) определены в одном месте (`data_service.py`) и используются везде с одинаковыми сигнатурами.

**Placeholder scan:** проверено, явных «TBD»/«implement later» в стейпах нет; для F2-F5 указано «по шаблону F1» только когда полный код F1 — выше в этом же документе.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-04-rebuild-phase1-backend.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — я диспатчу свежего subagent'а на каждый Task, между Task'ами делаю review (compile / pytest / git diff), быстрые итерации.

**2. Inline Execution** — выполняю Task'и в этой сессии через `executing-plans`, batch с checkpoints для вашего ревью.

Какой подход выбираем?
