# План миграции YDB → PostgreSQL

**Дата:** 22.02.2026
**Статус:** ЗАВЕРШЕНО (22.02.2026)
**Приоритет:** Высокий

## Причины миграции

1. **Зависимость от Yandex Cloud** — YDB Serverless требует интернет и авторизацию через SA
2. **Удобство разработки** — PostgreSQL работает локально, без VPN, без cloud-зависимостей
3. **Стандарт отрасли** — PostgreSQL широко используется, хорошо документирован
4. **Инструментарий** — pgAdmin, DBeaver, SQLAlchemy, Alembic миграции
5. **Защита ВКР** — демонстрация работает автономно, без интернета

## Текущая схема (YDB)

### Таблица `af_all_2024` (отели)

| Колонка | Тип YDB | Описание |
|---------|---------|----------|
| id | Utf8 (PK) | ID отеля (строка) |
| name | Utf8 | Название |
| city | Utf8 | Город |
| district | Utf8 | Район |
| lat | Double | Широта |
| lon | Double | Долгота |

### Таблица `hotels_statistics` (статистика загрузки)

| Колонка | Тип YDB | Описание |
|---------|---------|----------|
| id | Utf8 (PK) | ID отеля (FK) |
| date | Date (PK) | Дата |
| rooms_num | Int64 | Всего номеров |
| free_rooms_amount | Int64 | Свободных номеров |
| available_rooms_percent | Double | % свободных (0-100) |
| min_price | Int64 | Мин. цена (руб.) |
| max_capacity | Int64 | Макс. вместимость |

### Таблица `events` (события)

| Колонка | Тип YDB | Описание |
|---------|---------|----------|
| event_id | Utf8 (PK) | ID события |
| title | Utf8 | Название |
| description | Utf8 | Описание |
| date_start | Date | Дата начала |
| date_end | Optional<Date> | Дата окончания |
| event_type | Utf8 | Тип события |
| location | Utf8 | Место проведения |
| source_id | Utf8 | Источник (zeroevent, culture38...) |
| url | Utf8 | URL |
| created_at | Datetime | Дата создания записи |

## Целевая схема (PostgreSQL)

### SQL-миграция

```sql
CREATE TABLE hotels (
    id VARCHAR(64) PRIMARY KEY,
    name TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    district VARCHAR(100),
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    rating DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_hotels_city ON hotels(city);
CREATE INDEX idx_hotels_district ON hotels(district);

CREATE TABLE hotel_statistics (
    id VARCHAR(64) NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    rooms_num INT,
    free_rooms_amount INT,
    available_rooms_percent DOUBLE PRECISION,
    min_price INT,
    max_capacity INT,
    PRIMARY KEY (id, date)
);

CREATE INDEX idx_statistics_date ON hotel_statistics(date);
CREATE INDEX idx_statistics_id_date ON hotel_statistics(id, date);

CREATE TABLE events (
    event_id VARCHAR(128) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    date_start DATE NOT NULL,
    date_end DATE,
    event_type VARCHAR(50),
    location TEXT,
    source_id VARCHAR(50) NOT NULL,
    url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_date ON events(date_start);
CREATE INDEX idx_events_source ON events(source_id);
CREATE INDEX idx_events_type ON events(event_type);

CREATE TABLE query_history (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    response TEXT,
    provider VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE forecasts (
    id SERIAL PRIMARY KEY,
    district VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    predicted_occupancy DOUBLE PRECISION,
    model VARCHAR(50) NOT NULL,
    confidence_lower DOUBLE PRECISION,
    confidence_upper DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_forecasts_district_date ON forecasts(district, date);
```

## План реализации

### Этап 1: Инфраструктура (1 день)

1. Добавить PostgreSQL в `docker-compose.yml`
2. Установить `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
3. Создать `backend/app/db/session.py` (async engine + session)
4. Создать `backend/app/db/models.py` (SQLAlchemy ORM)
5. Инициализировать Alembic

### Этап 2: Миграция сервиса (2 дня)

1. Создать `backend/app/services/db_service.py` — новый сервис с тем же интерфейсом
2. Реализовать все методы `ydb_service` через SQLAlchemy:
   - `get_hotels()` → `SELECT * FROM hotels`
   - `get_hotel_statistics()` → `SELECT * FROM hotel_statistics`
   - `get_events()` → `SELECT * FROM events`
   - `get_occupancy_by_district()` → JOIN + AVG
   - `insert_event()` → INSERT ON CONFLICT
   - `delete_events_by_source()` → DELETE WHERE source_id
   - `save_hotels_to_ydb()` → INSERT ON CONFLICT
   - `save_statistics_to_ydb()` → INSERT ON CONFLICT
3. Обновить импорты во всех роутерах и сервисах

### Этап 3: Перенос данных (1 день)

1. Скрипт экспорта из YDB → JSON/CSV
2. Скрипт импорта в PostgreSQL
3. Проверка целостности данных

### Этап 4: Обновление конфигурации (0.5 дня)

1. Обновить `config.py` — добавить `database_url`
2. Обновить `.env.example`
3. Обновить `docker-compose.yml` (PostgreSQL + Redis)
4. Обновить `main.py` lifespan

## Маппинг типов

| YDB | PostgreSQL | SQLAlchemy |
|-----|------------|------------|
| Utf8 | TEXT/VARCHAR | String |
| Date | DATE | Date |
| Datetime | TIMESTAMP | DateTime |
| Int64 | BIGINT | BigInteger |
| Double | DOUBLE PRECISION | Float |
| Optional<T> | NULLABLE | nullable=True |

## Риски

1. **Потеря данных** — митигация: экспорт в JSON перед миграцией
2. **Несовместимость запросов** — митигация: тесты для всех методов
3. **Производительность** — митигация: индексы, connection pooling
4. **Время** — митигация: сохранить ydb_service как fallback

## Docker Compose (целевой)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: tourism-postgres
    environment:
      POSTGRES_DB: tourism
      POSTGRES_USER: tourism
      POSTGRES_PASSWORD: tourism_pass
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: tourism-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

volumes:
  pg_data:
  redis_data:
```

## Обратная совместимость

Реализовано через фабрику `data_service.py`:

```python
# backend/app/services/data_service.py
def get_data_service():
    if settings.db_backend == "postgresql":
        from app.services.db_service import db_service
        return db_service
    from app.services.ydb_service import ydb_service
    return ydb_service

data_service = get_data_service()
```

Все роутеры и сервисы импортируют `data_service` вместо `ydb_service`.

## Результаты миграции (22.02.2026)

| Метрика | Значение |
|---------|----------|
| Отелей перенесено | 648 |
| Записей статистики | 34 739 |
| Событий | 129 |
| API endpoint'ов протестировано | hotels, events, analytics/kpi, districts, correlation, hotels-by-city |
| Все тесты | Пройдены |

### Созданные файлы

- `backend/app/db/models.py` — 5 SQLAlchemy ORM моделей
- `backend/app/db/session.py` — async engine + session factory
- `backend/app/services/db_service.py` — PostgreSQL-совместимый сервис (15+ методов)
- `backend/app/services/data_service.py` — фабрика переключения backend'а
- `backend/scripts/migrate_ydb_to_pg.py` — скрипт миграции данных
