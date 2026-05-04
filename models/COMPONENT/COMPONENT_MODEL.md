# Диаграмма компонентов (Component Model)

## Назначение

Диаграмма компонентов описывает программную архитектуру ИАС мониторинга и прогнозирования туристической активности Иркутской области. Система организована как **B2B-инструмент** для трёх профильных сегментов: отельеры, региональная администрация, исследователи.

Текстовое описание сопровождает drawio-диаграммы (`component_diagrams.drawio`) и фиксирует логические группы компонентов, их зависимости и группировку B2B-эндпоинтов.

## Файлы

- `component_diagrams.drawio` — диаграммы компонентов и подсистем (БП1 Фоновый сбор, БП2 Обработка запроса, БП3 Администрирование)
- `deployment_diagrams.drawio` — диаграмма размещения (Docker Compose: backend + frontend + PostgreSQL + Redis + ChromaDB)
- `COMPONENT_MODEL.md` — этот файл

## Группировка компонентов

### 1. Frontend (React 18 + Vite 7)

| Компонент | Назначение | Адресат (B2B) |
|-----------|------------|---------------|
| Командный центр (Home) | Сводка KPI, прогноз 14 дней, ближайшие события с impact, RevPAR/ADR/Pickup | Все 3 сегмента |
| Региональная карта (Map) | ECharts GeoMap с кластеризацией средств размещения | Администратор региона |
| Аналитика рынка (Analytics) | Heatmap, Pickup/Pace, RevPAR, события с impact, экспорт CSV | Отельер, Администратор региона |
| Прогноз спроса (Forecast) | Ensemble прогноз с CI-bands, сравнение моделей | Отельер, Администратор региона, Исследователь |
| События и спрос (Events) | Календарь и таблица событий с impact | Все 3 сегмента |
| Объект размещения (HotelDetail) | Карточка отеля с RMS-метриками, динамикой бронирований и ценами | Отельер |
| AI-помощник (Chat) | SSE-стриминг ответов LangGraph агента (B2B system prompt) | Отельер, Администратор региона |
| О системе (About) | Описание архитектуры и B2B-функционала | Все 3 сегмента |

**Стек фронтенда:** React 18, TypeScript 5.9, Tailwind CSS 4, Vite 7, Recharts (графики), ECharts (GeoMap + scatter).

### 2. API-слой (FastAPI, 7 роутеров, 59 endpoints)

#### 2.1. B2B-эндпоинты (основные для целевых сегментов)

| Эндпоинт | Описание | UC | FR |
|----------|----------|----|----|
| `GET /api/analytics/revenue-summary` | RevPAR / ADR / Occupancy % за период (с фильтром по hotel_id или district) | UC10 | FR3.6 |
| `GET /api/analytics/pickup-pace` | Pickup и Pace кривая бронирований за 30 дней до даты заезда | UC10 | FR3.6 |
| `GET /api/analytics/weekday-heatmap` | Матрица 7×12 (дни недели × месяцы) средней загрузки | UC10, UC5 | FR3.7 |
| `GET /api/analytics/events-impact` | Топ событий с расчётом Δ Occupancy | UC3 | FR4.7 |
| `GET /api/analytics/heatmap` | Тепловая карта загрузки по районам и месяцам | UC5 | FR1.5 |
| `GET /api/analytics/revenue-summary` | Сводка RevPAR / ADR / Occupancy по районам | UC5 | FR1.5 |
| `GET /api/analytics/districts` | Сводка по 15 районам | UC5 | FR1.5 |
| `GET /api/analytics/export` | CSV-выгрузка `type=occupancy\|events\|hotels` с фильтрами `date_from`, `date_to`, `district` | UC9 | FR6.1 |
| `GET /api/forecast/ensemble` | Ensemble прогноз (лучшая взвешенная модель) | UC1 | FR4.2 |
| `GET /api/forecast/compare-all` | Сравнение всех моделей с метриками RMSE/MAE/R² | UC4 | FR3.5 |
| `GET /api/analytics/price-recommendation` | Рекомендация цены на основе прогноза и Pickup | UC10 | FR3.6 |

#### 2.2. Общие эндпоинты (используются всеми сценариями)

| Эндпоинт | Описание | UC |
|----------|----------|-----|
| `POST /api/query` | AI-агент (RAG + 6 tools) | UC1, UC3 |
| `POST /api/query/stream` | AI-агент SSE streaming | UC1, UC3 |
| `GET /api/hotels` | Реестр объектов размещения по району | UC2, UC5 |
| `GET /api/hotels/{id}` | Карточка объекта | UC2 |
| `GET /api/events` | Календарь событий | UC3 |
| `GET /api/analytics/kpi` | KPI дашборд | UC1 |
| `GET /api/analytics/hotels-map` | Данные для GeoMap карты отелей | UC5 |
| `GET /api/analytics/correlation` | Корреляции между метриками | UC3, UC5 |
| `GET /health` | Health-check агрегатор | UC7 |

#### 2.3. Служебные эндпоинты (Технический администратор, защищены `X-API-Key`)

| Эндпоинт | Описание | UC |
|----------|----------|-----|
| `POST /api/parser/hotels` | Запуск парсера 101Hotels по требованию | UC6 |
| `POST /api/parser/events` | Запуск парсеров событий | UC6 |
| `POST /api/parser/weather` | Запуск парсера Open-Meteo | UC6 |
| `POST /api/parser/reindex` | Переиндексация ChromaDB | UC6 |
| `GET /api/parser/health` | Состояние парсеров (HealthMonitor) | UC7 |
| `GET /api/documents/...` | Управление документами в RAG | UC6 |

### 3. Сервисный слой (16 сервисов)

| Сервис | Назначение | Используется компонентами |
|--------|------------|---------------------------|
| `ensemble_service` | Async Ensemble прогноз (Prophet + NeuralProphet + XGBoost), Redis-кэш | forecast.py, main_agent |
| `prophet_service` | Prophet (sync, через `executor.run_sync`) | ensemble_service |
| `neuralprophet_service` | NeuralProphet (sync, через `executor.run_sync`) | ensemble_service |
| `xgboost_service` | XGBoost с quantile regression для CI | ensemble_service |
| `feature_engineering` | 38 признаков: calendar, holidays, lags, rolling, weather, events, trend, prices | xgboost_service |
| `main_agent` | LangGraph MainAgent + 6 tools + MemorySaver (B2B system prompt) | query.py |
| `forecast_agent` | LangGraph ForecastAgent (объяснимые прогнозы) | main_agent |
| `llm_service` | 6 LLM провайдеров (Mistral основной + GigaChat / Groq / DeepSeek / OpenRouter / Gemini) | main_agent, forecast_agent |
| `data_service` | Доменный фасад БД: get_occupancy_by_district, get_hotels, get_events, get_revenue_summary | роутеры, agent tools |
| `db_service` | Низкоуровневый: пул соединений, create_all, lifespan | main.py, data_service |
| `chroma_service` | RAG-поиск через ChromaDB (GigaChat Embeddings) | main_agent |
| `cache_service` | Redis-кэш с TTL и graceful fallback | ensemble_service, analytics |
| `weather_service` | Open-Meteo API (текущая + прогноз) | parsers, main_agent |
| `holidays_service` | Государственные и региональные праздники РФ | feature_engineering |
| `poi_service` | Точки притяжения (POI) для feature engineering | feature_engineering |
| `protocols.py` | Type protocols для DI и тестирования | все сервисы |

### 4. Парсеры (~14 файлов)

| Парсер | Источник | Расписание |
|--------|----------|------------|
| `parsers/base.py` | Базовый класс + AIExtractor + AntiDetection + HealthMonitor | — |
| `events_irk.py` | irk.ru/afisha | 6ч |
| `events_culture38.py` | culture38.ru | 6ч |
| `events_zeroevent.py` | zeroevent.ru | 6ч |
| `events_kassir.py` | kassir.ru (Crawl4AI + Jina Reader fallback) | 6ч |
| `events_yandex_afisha.py` | afisha.yandex.ru | 6ч |
| `events_culture_ru.py` | culture.ru | 6ч |
| `events_telegram.py` | Telegram-каналы (Telethon) | 1ч |
| `events_sluda.py` | Региональные источники | 6ч |
| `hotels_101hotels.py` | 101Hotels API | 2ч |
| `hotels_xotelo.py` | Xotelo / TripAdvisor cross-reference | 2ч |
| `weather_openmeteo.py` | Open-Meteo API | 3ч |

### 5. Фоновая инфраструктура

| Компонент | Назначение |
|-----------|------------|
| `scheduler` (APScheduler / AsyncIOScheduler) | Запуск парсеров по расписанию |
| `executor` (ThreadPoolExecutor) | Общий пул для sync ML-вызовов через `executor.run_sync(...)` |
| `middleware/rate_limit` | Redis sliding window: 10 req/min для `/api/query`, 5 req/min для `/api/parser` + in-memory fallback |
| `dependencies/auth` | API-key validation для `/api/parser/...` |
| `lifespan` (main.py) | Инициализация PostgreSQL, Redis, Chroma, LLM, APScheduler, прогрев `_warmup_forecast_cache` |

### 6. Хранилища данных

| Хранилище | Назначение | Основные таблицы / коллекции |
|-----------|------------|------------------------------|
| **PostgreSQL 16** (asyncpg + SQLAlchemy 2.0) | Основное хранилище | `hotels`, `hotel_statistics`, `events`, `weather`, `query_log` |
| **Redis 7** | Кэш прогнозов + RMS-агрегатов + rate limiting | TTL 30 мин для прогнозов |
| **ChromaDB** | Векторный индекс для RAG | 629+ документов с GigaChat Embeddings |

### 7. AI-агент (LangGraph)

LangGraph StateGraph с MemorySaver (thread_id-based context) и Command pattern:

**Системный промпт:** B2B-аналитик информационной системы для отельеров, региональной администрации и исследователей туристического рынка Иркутской области.

**6 tools:**
| Tool | Описание | Backend |
|------|----------|---------|
| `search_hotels` | Реестр объектов размещения региона (PostgreSQL + ChromaDB RAG) | data_service + chroma_service |
| `search_events` | События, влияющие на спрос на размещение | data_service |
| `get_weather` | Текущая / прогнозная погода как фактор спроса | weather_service |
| `forecast_occupancy` | Ensemble прогноз с акцентом на RevPAR / Pickup | ensemble_service |
| `get_statistics` | KPI рынка средств размещения | data_service |
| `get_revenue_metrics` | RevPAR / ADR / Occupancy % (с прокси через `min_price`, если revenue отсутствует) | data_service |

## Зависимости между компонентами

### Поток обработки B2B-запроса

```
Frontend (React)
   │  HTTP / SSE
   ▼
FastAPI Router (analytics / forecast / query)
   │
   ├─→ middleware/rate_limit  (Redis sliding window)
   ├─→ dependencies/auth      (X-API-Key для parser endpoints)
   │
   ▼
Сервисный слой (data_service, ensemble_service, main_agent)
   │
   ├─→ executor.run_sync(...)   (Prophet, NeuralProphet, XGBoost — sync через ThreadPool)
   ├─→ cache_service            (Redis: чтение/запись, TTL 30 мин)
   ├─→ chroma_service           (RAG: top-k поиск по эмбеддингам)
   ├─→ llm_service              (Mistral / fallback)
   │
   ▼
Хранилища (PostgreSQL / Redis / ChromaDB)
```

### Поток фонового сбора

```
APScheduler (cron: события 6ч, отели 2ч, погода 3ч, Telegram 1ч)
   │
   ▼
parsers/{events_*.py | hotels_*.py | weather_*.py}
   │
   ├─→ AIExtractor       (LLM-нормализация для JS-heavy сайтов)
   ├─→ AntiDetection     (rate limiting, headers rotation)
   ├─→ HealthMonitor     (счётчики ошибок по источникам)
   │
   ▼
data_service.upsert_*  (PostgreSQL ON CONFLICT DO UPDATE)
   │
   ▼
chroma_service.reindex (обновление векторного индекса)
```

### Поток экспорта (UC9)

```
Frontend → GET /api/analytics/export?type=...
   │
   ▼
analytics router (валидация параметров: type, date_from, date_to, district)
   │
   ▼
data_service.export_to_csv(type, filters)
   │
   ▼
PostgreSQL → StreamingResponse(text/csv)
   │
   ▼
Browser (download)
```

## Связь с другими моделями

| Модель | Связь |
|--------|-------|
| Use Case | Каждый UC реализуется одним или несколькими компонентами (UC1 → forecast router + ensemble_service; UC9 → analytics router + data_service; UC10 → analytics router + data_service) |
| Domain | Сущности предметной области (Средство размещения, Событие, RMS-метрика и др.) хранятся в PostgreSQL + ChromaDB, обслуживаются сервисами data_service и chroma_service |
| Requirements | Каждое FR покрывается компонентом: FR1 → parsers/hotels_* + data_service, FR2 → parsers/events_* + data_service, FR3.6 → analytics router (revenue-summary) + data_service, FR4.2 → ensemble_service, FR4.7 → analytics router (events-impact), FR6 → analytics router (export) + data_service |
| BP | Компоненты участвуют в трёх процессах: 1) Сбор и обновление данных (parsers + scheduler), 2) Обслуживание B2B-запросов (API + сервисы), 3) Администрирование (parser routes + monitoring) |
| Deployment | Все компоненты упакованы в Docker-образы (`backend`, `frontend`), оркестрация через `docker-compose.yml` с профилем `full` |

## Технологический стек (сводно)

- **Backend:** FastAPI, Pydantic v2, async/await, SQLAlchemy 2.0 + asyncpg
- **Database:** PostgreSQL 16 (Docker)
- **Cache:** Redis 7 (с аутентификацией)
- **Vector DB:** ChromaDB
- **ML:** Prophet, NeuralProphet, XGBoost, LightGBM, Ensemble (weighted average)
- **LLM:** Mistral Large (основной), GigaChat / Groq / DeepSeek / OpenRouter / Gemini (fallback)
- **AI Agents:** LangGraph (MainAgent + ForecastAgent, 6 tools, MemorySaver, Command pattern)
- **Frontend:** React 18, TypeScript 5.9, Tailwind CSS 4, Vite 7
- **Визуализация:** Recharts (графики, KPI), ECharts (GeoMap, scatter, heatmap)
- **Инфраструктура:** Docker Compose, APScheduler, ThreadPoolExecutor, Redis sliding window rate limit
