# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **СТАРТ ЛЮБОЙ СЕССИИ — ОБЯЗАТЕЛЬНО:**
> 1. Прочитай [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) — единый источник правды о текущем курсе проекта (B2B-рефокус, дедлайн 12.05.2026).
> 2. Прочитай [`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md) — где остановилась работа.
> 3. План работ — [`docs/REFOCUS_PLAN.md`](docs/REFOCUS_PLAN.md) (9 этапов с Definition of Done).
>
> **Не используй документы из [`docs/_archive/`](docs/_archive/) как руководство к действию** — там лежит старая двухсегментная концепция (B2B+B2C), от которой проект ушёл 06.04.2026 после защиты практики.
>
> **Текущий курс:** ИАС позиционируется как **B2B-инструмент** для трёх сегментов: отельеры, региональная администрация, исследователи. Без сегмента «туристы».

## Проект

ИАС мониторинга и прогнозирования туристической активности Иркутской области (ВКР). Текущая фаза — **преддипломная практика 06.04–16.05.2026, рефокус с двухсегментной модели на B2B**.

### Архитектура

```
Frontend (React + Vite)        Backend (FastAPI)              Data Sources
├── Home (Командный центр)    ├── routers/ (8 шт., 67 endpoints)
├── Chat (AI-аналитик SSE)    │   ├── forecast.py            ├── 101hotels (отели live)
├── Analytics (4 вкладки)     │   ├── events.py              ├── OSM Overpass (типы размещения)
├── Events (календарь+impact) │   ├── hotels.py              ├── OpenMeteo (погода)
├── Map (Yandex Maps)         │   ├── analytics.py (12+ B2B) ├── 8 парсеров событий
├── Forecast (3 режима)       │   ├── query.py               ├── Telegram каналы
├── HotelDetail (RMS-bench)   │   ├── parser.py              └── Xotelo/TripAdvisor (deprecated)
└── About (методология)       │   └── documents.py
                              ├── services/ (19 шт.)
                              │   ├── ensemble_service.py (async + кэш)
                              │   ├── main_agent.py (LangGraph, 12 B2B-tools)
                              │   ├── forecast_agent.py (LangGraph)
                              │   ├── llm_service.py (6 LLM, structured output)
                              │   ├── data_service.py (доменный фасад PG)
                              │   ├── db_service.py (низкоуровневый PG)
                              │   ├── methodology_service.py (seasonal_corrected baseline)
                              │   ├── parser_health_service.py (Redis hash, TTL 7d)
                              │   ├── chroma_service.py (RAG)
                              │   ├── cache_service.py (Redis)
                              │   ├── prophet_service.py
                              │   ├── neuralprophet_service.py
                              │   ├── xgboost_service.py
                              │   ├── feature_engineering.py
                              │   ├── weather_service.py
                              │   ├── holidays_service.py
                              │   ├── poi_service.py
                              │   └── protocols.py
                              ├── middleware/rate_limit.py
                              ├── dependencies/auth.py (API key)
                              ├── db/ (SQLAlchemy ORM, async session)
                              ├── models/schemas.py (Pydantic v2)
                              ├── constants.py (CITY_SLUG_TO_NAME 31 город, REGION_SLUGS, IRKUTSK_BBOX)
                              ├── executor.py (ThreadPoolExecutor для sync ML)
                              ├── scheduler.py (5 jobs: events 6h, hotels 2h, weather 3h, telegram 1h, reclassify 6h cron)
                              └── parsers/ (~16 файлов)
                                  ├── base.py (detect_event_type: 11 кат + jsonld_type, title-priority)
                                  ├── ai_extractor + anti_detection + health_monitor
                                  ├── events_*.py (8 парсеров: irk/culture38/zeroevent/yandex/kassir/culture_rf/telegram/major)
                                  ├── hotels_101hotels.py (region + city sweep + accommodation_type)
                                  ├── hotels_osm.py (Overpass fallback с auto-failover)
                                  ├── hotels_xotelo.py (public API deprecated, скрипт под рукой)
                                  └── weather_openmeteo.py
```

## Команды

### Backend
```bash
cd backend
python -m venv venv
source venv/Scripts/activate           # Git Bash на Windows
# .\venv\Scripts\Activate.ps1          # PowerShell альтернатива
pip install -r requirements.txt
cp .env.example .env                   # Настроить переменные
PYTHONIOENCODING=utf-8 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> **Windows-критично**: запускать с `PYTHONIOENCODING=utf-8`. Иначе Crawl4AI/Jina
> возвращают Markdown с символами `↓ ↑ ←` (стрелки трендов yandex/kassir),
> stdout с дефолтным cp1251 падает на encode → парсер возвращает 0 событий
> молча. На Linux/Mac не нужно. **`--reload` НЕ использовать** в dev — lifespan
> с warmup ensemble-кэша плохо переживает hot-reload.

> На старте `lifespan` поднимает PostgreSQL, Redis, Chroma, LLM, APScheduler и
> запускает фоновый прогрев ensemble-кэша (`_warmup_forecast_cache` в `main.py`).
> Если Redis недоступен — кэш отключается, но сервер продолжает работать.

### CLI-скрипты для обогащения данных

```bash
cd backend
# YDB → PG: подтянуть свежие hotel_statistics за сегодня (idempotent)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/import_from_ydb_101hotels.py

# LLM-реклассификация event_type='event' через Mistral (also запускается cron каждые 6h)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/reclassify_events.py [--dry-run] [--limit N]

# Заполнение accommodation_type через OSM Overpass (cross-ref Хаверсин 0.5 км)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/fill_hotel_types_from_osm.py [--dry-run] [--limit N]

# (deprecated) Xotelo: public API 400, скрипт остался под рукой если оживёт RapidAPI
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/fill_hotel_types_from_xotelo.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # Development (localhost:5173)
npm run build    # Production
```

### Docker (PostgreSQL + Redis)
```bash
docker compose up -d postgres redis       # Только БД
docker compose --profile full up -d       # Полный стек
```

### Тестирование
```bash
# Backend health check
curl http://localhost:8000/health

# Unit тесты (8 файлов, см. backend/tests/test_*.py)
cd backend && source venv/Scripts/activate && pytest tests/ -v

# Запуск одного файла / одного теста
pytest tests/test_routers.py -v
pytest tests/test_routers.py::test_health -v

# E2E тесты (9 сценариев, требует поднятый backend на :8000)
cd backend && python tests/e2e_test.py

# API docs (Swagger / ReDoc)
# http://localhost:8000/docs   и   http://localhost:8000/redoc
```

## Ключевые API endpoints

### Базовые
| Endpoint | Описание |
|----------|----------|
| `POST /api/query` | AI-агент (RAG + 12 tools) |
| `POST /api/query/stream` | AI-агент SSE streaming |
| `GET /api/forecast/ensemble` | Ensemble прогноз (лучшая модель) |
| `GET /api/forecast/compare-all` | Сравнение всех моделей |
| `GET /api/forecast/{district}/validation` | RMSE/MAE forecast vs actual |
| `GET /api/hotels` | Отели по району |
| `GET /api/hotels/{id}/segment-benchmark` | Сравнение объекта с сегментом (district × size_bucket) |
| `GET /api/events` | События региона (full v2-схема: time/price/image/address/age) |
| `GET /api/analytics/kpi` | KPI дашборд |
| `GET /api/analytics/hotels-map` | Данные для Yandex Maps |

### B2B endpoints (analytics)
| Endpoint | Описание |
|----------|----------|
| `GET /api/analytics/booking-pace` | Daily proxy-pickup curve |
| `GET /api/analytics/occupancy-timeseries` | День-по-день occupancy |
| `GET /api/analytics/price-distribution` | Перцентили p10/p25/p50/p75/p90 |
| `GET /api/analytics/compare-districts` | Side-by-side RMS-метрик |
| `GET /api/analytics/events-impact?method=seasonal_corrected` | Corrected impact с CI |
| `GET /api/analytics/segments` | Структура по accommodation_type + size_bucket (по всему региону) |
| `GET /api/analytics/district-segments?district=...` | Drill-down: сегменты внутри района (тип×размер с occupancy/ADR/RevPAR) |
| `GET /api/analytics/correlation` | Сезонность по месяцам, поле `confidence` (high/limited/none) |
| `GET /api/analytics/metadata` | Counts, data_range, gap_periods |
| `GET /api/parser/health` | Состояние парсеров (last_run, status, items, error) |

### Парсеры (требуют `X-API-Key`)
| Endpoint | Описание |
|----------|----------|
| `POST /api/parser/hotels?mode=region` | 2 region-slug (~250 отелей, дефолт) |
| `POST /api/parser/hotels?mode=cities_default` | 5 городов (быстрый fallback) |
| `POST /api/parser/hotels?mode=cities_full` | Все 31 город из CITY_SLUG_TO_NAME |
| `POST /api/parser/events/{src}` | irk / kassir / zeroevent / yandex / culture38 / culture_rf |
| `POST /api/parser/events/telegram?channels=baikalgora,glagol38` | Конкретные каналы (CSV); без параметра — все BAIKAL_CHANNELS, в логах per-channel breakdown |

## Технологический стек

- **Backend:** FastAPI, Pydantic v2, async/await
- **Database:** PostgreSQL 16 (SQLAlchemy 2.0 + asyncpg, Docker)
- **Cache:** Redis 7 (с аутентификацией)
- **Vector DB:** ChromaDB (RAG, ~1200 docs)
- **ML:** Prophet, NeuralProphet, XGBoost, LightGBM, Ensemble (weighted average)
- **LLM:** primary `LLM_PROVIDER=groq` (Llama 3.3 70b versatile, free-tier 100K токенов/день). **Автоматический fallback chain в `main_agent.py`**: Groq → DeepSeek → Mistral. При 429/402/401/403/5xx/timeout от текущего провайдера агент прозрачно переключается на следующего. ministral-8b используется для `reclassify_events` cron'а.
- **AI Agents:** LangGraph (main_agent + forecast_agent, **12 B2B-tools**, MemorySaver)
- **Geo data:** OpenStreetMap Overpass API (auto-failover overpass-api.de → kumi.systems)
- **Hotels:** 101hotels.com REST (region+city sweep), Xotelo TripAdvisor proxy (deprecated)
- **Frontend:** React 18, TypeScript 5.9, Tailwind CSS 4, Vite 7
- **Визуализация:** Recharts (графики), Yandex Maps (через @pbe/react-yandex-maps)
- **Утилиты frontend:** `localize.ts` (RU labels), `chartTheme.ts` (Recharts foreground), `localizeFeatures.ts` (XGBoost feature names)

## Районы Иркутской области

- `Иркутский` (больше всего данных)
- `Ольхонский`
- `Слюдянский`
- `Ангарский`
- И другие (всего 15 районов)

## Переменные окружения (.env)

```bash
# Database
DB_BACKEND=postgresql
DATABASE_URL=postgresql://user:pass@localhost:5432/tourism

# LLM (primary; fallback chain автоматически: groq → deepseek → mistral)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
MISTRAL_API_KEY=...
DEEPSEEK_API_KEY=...   # опционально, требует баланса

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis_pass

# Security
API_KEY=your-secret-key-here  # Для защиты parser endpoints
RATE_LIMIT_REQUESTS=60        # Запросов в минуту
```

## Безопасность

| Компонент | Описание |
|-----------|----------|
| Rate Limiting | Redis sliding window, 10 req/min для `/api/query`, 5 req/min для `/api/parser` |
| API Key Auth | Защита parser endpoints (`X-API-Key` header) |
| SQL Injection | Параметризованные запросы + экранирование `%` и `_` в LIKE |
| CORS | Ограниченные методы и заголовки |
| CSP/HSTS | Security headers в nginx |
| Docker | Non-root user, restricted ports, secrets через env |

### Защищённые endpoints

Parser endpoints требуют API ключ:
```bash
curl -X POST http://localhost:8000/api/parser/hotels \
  -H "X-API-Key: your-secret-key"
```

Если `API_KEY` не задан в `.env` — auth отключён (dev mode).

## Code Style

### Python
- Type hints обязательно
- Absolute imports (`from app.services import ...`)
- Pydantic модели вместо dict
- Google-style docstrings
- Приватные функции с префиксом `_`

### TypeScript
- `type` вместо `interface`
- Function declarations (не стрелочные)
- Строгая типизация, без `any`

## ML-модели прогнозирования

| Модель | Endpoint | Особенность |
|--------|----------|-------------|
| Ensemble | `/api/forecast/ensemble` | Weighted average, async, кэш |
| Prophet | `/api/forecast` | Weather regressor, holidays |
| NeuralProphet | `/api/forecast/neural` | Lagged regressors, events |
| XGBoost | `/api/forecast/xgboost` | Quantile regression (CI) |

Feature engineering: 38 признаков (календарь 8, праздники 5, лаги 5, diff 2, rolling 5, погода 4, события 3, тренд 2, цены 4).

## AI-агент (LangGraph)

**12 B2B-tools** в `main_agent.py` (после Phase 2 B2B-rebuild):

Базовые (6):
- `search_hotels` — поиск отелей (ChromaDB + PostgreSQL)
- `search_events` — поиск событий
- `get_weather` — текущая/прогнозная погода (OpenMeteo)
- `forecast_occupancy` — прогноз загрузки (Ensemble)
- `get_statistics` — KPI и статистика
- `get_revenue_metrics` — ADR/RevPAR/Occupancy для района

B2B/RMS (6):
- `get_top_events_by_impact` — топ-N событий по corrected impact (seasonal_corrected baseline)
- `get_booking_pace` — динамика бронирований (daily proxy-pickup)
- `compare_districts` — side-by-side RMS-метрик
- `compare_forecast_models` — RMSE/MAE/R² по моделям
- `get_occupancy_timeseries` — день-по-день occupancy
- `get_price_distribution` — перцентили p10..p90

Системный промпт включает 8 правил методологии: район/период/метод/база сравнения, прокси-дисклеймер для ADR/RevPAR, gap-периоды.

### Устойчивость агента (отказоустойчивость и качество)

`main_agent.py` имеет три уровня защиты от сбоев LLM-провайдера:

1. **Index-based dedup `tool_call_id`** (`_dedup_tool_call_ids`). Mistral/Groq иногда возвращают параллельные tool_calls с одинаковым ID — это баг провайдера. Каждый tool_call безусловно получает свежий uuid; ToolMessage'и матчатся по позиции (индексу). При duplicate-ID retry без tool history с `await asyncio.sleep(2.0)` backoff.
2. **Автоматический fallback chain** (`_resolve_provider_chain` + `_is_provider_unavailable_error`). При 429/402/401/403/5xx/timeout/connection error агент пробует следующего провайдера из цепочки `[primary, groq, deepseek, mistral]`. В логах: `[LLM:groq] 429, falling back to deepseek` → `[LLM:deepseek] 402, falling back to mistral` → `[LLM] Fallback succeeded on provider: mistral`. `_PROVIDER_LLM_CACHE` лениво строит и кэширует LLM per-provider.
3. **User-friendly degradation**. Если ВСЕ провайдеры упали — агент возвращает «Все AI-провайдеры сейчас перегружены. Попробуйте через минуту» вместо HTTP 500. Если упал не из-за rate-limit — «Извините, произошла ошибка...».

### SSE streaming (`/api/query/stream`)

`HEARTBEAT_INTERVAL_S = 15.0`, `HARD_TIMEOUT_S = 180.0`. Между событиями LangGraph stream'а отправляет `: keepalive\n\n` каждые 15 сек, чтобы прокси/CDN не разорвали соединение. После 180 сек без событий — error event `'AI не отвечает дольше 3 минут. Попробуйте ещё раз.'`

### `/api/forecast/explain`

`LLM_EXPLAIN_TIMEOUT_S = 30.0` (поднято с 5.0 — Mistral медленнее на сложных PydanticOutputParser-запросах). При timeout/exception возвращает factor-only fallback (`source: "llm_timeout"` / `"llm_error"`) с топ-5 факторами XGBoost — UI получает 200 OK даже при сбое LLM.

## Слои доступа к данным

Внутри `services/` сосуществуют два сервиса БД — это намеренно, не дубль:

| Сервис | Роль |
|--------|------|
| `db_service` | Низкоуровневый: пул соединений, `connect()`/`close()`, создание таблиц при старте |
| `data_service` | Доменный фасад: `get_occupancy_by_district`, `get_hotels`, `get_events` и т. п. — то, что вызывают роутеры и tools агента |

Все CPU-тяжёлые синхронные ML-вызовы (`prophet_service.forecast`, `xgboost_service.forecast`, `ensemble_service.forecast_ensemble`) ОБЯЗАНЫ идти через `app.executor.run_sync(...)`, иначе блокируют event loop. Не оборачивайте их в `asyncio.to_thread` точечно — ThreadPoolExecutor общий, чтобы не плодить пулы.

## Известные ограничения

### Пробел данных: 24.06–25.10.2025 (123 дня)
- Парсеры были временно отключены, данные не собирались. Дозабор из YDB невозможен (там тоже нет).
- R² моделей отрицательный на долгосрочных прогнозах.
- Для демо использовать краткосрочные прогнозы (3-7 дней).
- На фронте (Analytics → Сезонность) gap-периоды отображаются диагональной штриховкой; gap-aware computation в `methodology_service`.
- **Мартовские пробелы 2026 (02–12 + 17–26) восстановлены 08.05.2026** через `import_from_ydb_101hotels.py --from ... --to ...` (3287 строк). В `/api/analytics/metadata` остался только июнь–октябрь 2025.

### Сезонность на 14 месяцах данных
- `MIN_SAMPLES_PER_MONTH = 1` (понижено с 5 — для пилота на 14 месяцев). `MIN_SAMPLES_FOR_HIGH_CONFIDENCE = 3`.
- `/api/analytics/correlation` возвращает поле `confidence: "high" | "limited" | "none"` для каждого месяца. UI показывает badge «ограниченная выборка» при `samples<3`.
- `data_coverage` теперь даёт реалистичные «9/12 месяцев» вместо «0/12» — рендер сезонности работает.

### accommodation_type у отелей
- 625 / 1428 hotels (43.8%) с заполненным типом (Отель/Гостиница/Апартаменты/Хостел/Гостевой дом/База отдыха/Шале/Кемпинг/...). 18 разных типов.
- 803 NULL — объекты в малых населённых пунктах вне публичных источников. Закрыть только через Booking.com или 2GIS Catalog API (платно/требует partnership).
- Источники типов: 101hotels live (262) + OSM Overpass (363).
- Xotelo public API deprecated в 2026, мигрирует на платный RapidAPI ($5-10/мес). `fill_hotel_types_from_xotelo.py` остался под рукой если оживёт.

### События `event_type='event'` (Telegram-приветствия)
- ~32-42 события из ~450 остаются в fallback категории. Это правильное поведение: «АКТИВНОЙ СУББОТЫ!», «Песни Победы» без контекста — это спам/лозунги Telegram-каналов, не события.
- LLM Mistral на cron'е каждые 6h (`reclassify_events`) корректно оставляет их `event`.

### Парсеры событий — ограничения источников
- **events_irk**: главная страница `irk.ru/afisha` без detail-страниц → `description = NULL` всегда (любая lookahead-эвристика тянет title соседа). Зато `image_url` через DOM-walking + `time_start` через regex работают (~35% событий).
- **events_kassir/yandex**: Crawl4AI/Jina с JS-rendering, медленно (~30-60 сек на прогон).
- **events_culture_rf/culture38**: государственные/региональные порталы, низкий volume.
- **events_telegram**: best-effort через web-preview (без Telethon API key); image_url ограничен.

### LLM-провайдеры: затраты и лимиты
- **Groq (primary)**: free-tier ~30 RPM, 12K TPM, 100K токенов/день. Llama 3.3 70b versatile, ~5–60 сек на ответ с tool-calling.
- **DeepSeek (fallback)**: $0.14/1M input, $0.28/1M output. Без TPM-throttle, но требует положительного баланса (HTTP 402 если 0).
- **Mistral (fallback)**: free-tier ~1 запрос/сек, лимит токенов в минуту низкий. Используется как «последний резерв» в chain.
- **LLM-reclassify (ministral-8b)**: ~$0.15 за 209 событий, 30 сек при `concurrency=10`. Cron 6h × $0.10–0.15 = ~$0.50/день.

### Pyright pre-existing warnings
- ~30 warnings в `db_service.py`/`llm_service.py` (AsyncEngine callable, AttributeValueList в BS4) — не runtime errors, не блокируют тесты. Игнорируем по NORTH_STAR §6.

## Стабильное состояние компонентов

Снимок «как устроено». Конкретный статус-таблица с датами живёт в `docs/project/PROJECT_STATUS.md` — туда же при изменениях.

| Компонент | Особенность реализации |
|-----------|------------------------|
| Backend | 8 роутеров, 67 endpoints, lifespan с прогревом ensemble-кэша + 5 cron-jobs |
| Frontend | 8 страниц, Recharts + Yandex Maps, SSE для чата, полная RU-локализация (utils/localize, localizeFeatures, chartTheme) |
| AI-агент | LangGraph + MemorySaver, 12 B2B-tools, 8 правил методологии в system_prompt |
| Ensemble | Async поверх sync моделей через `executor.run_sync`, Redis-кэш, prophet+neuralprophet+xgboost |
| Категоризация | `detect_event_type`: 11 категорий + 14 schema.org `@type` mapping + ~110 keywords + title-priority phase |
| LLM-classify | Mistral structured output (JSON schema strict) для fallback `'event'` → точные категории. Cron каждые 6h. |
| Hotels enrichment | 101hotels live (region+city sweep, 31 город) + OSM Overpass cross-ref (Хаверсин 0.5 км) |
| Тесты | 34+ файла в `backend/tests/` + `e2e_test.py` (9 сценариев) + `test_persona_walkthrough.py` (3 persona) + `agent_stress_test.py` (19 запросов с rubric, JSON-результаты в `tests/results/`). 211+ passed, 0 регрессий |
| Security | Rate limiting (Redis sliding window + in-memory fallback), API-key, CSP, non-root Docker |
| Docker | `postgres:16-alpine`, `redis:7-alpine`, healthchecks, profiles `full` для бекенда+фронтенда |
| Alembic | Каркас настроен (`backend/alembic/env.py`); используется `create_all` + ALTER scripts. Ревизии — direction-of-development |

## Ключевая документация

- `docs/project/PROJECT_STATUS.md` — текущий статус проекта
- `docs/GLOBAL_AUDIT.md` — глобальный аудит (145 пунктов, 25.03.2026)
- `docs/project/PROJECT_AUDIT.md` — аудит проекта (12.03.2026)
- `docs/project/PG_MIGRATION_PLAN.md` — план миграции YDB → PostgreSQL (завершён)
- `docs/research/PARSERS_AUDIT.md` — аудит парсеров
- `docs/research/LLM_PROVIDERS_RESEARCH.md` — исследование LLM-провайдеров
- `docs/research/MISTRAL_MODELS_RESEARCH.md` — исследование моделей Mistral

## Завершённые миграции

- **БД:** YDB → PostgreSQL 16 (SQLAlchemy 2.0 + asyncpg, docker-compose) — 22.02.2026
- **Дашборды:** DataLens → Recharts + ECharts (встроенные в React) — 22.02.2026
- **Агенты:** LangGraph + Command pattern — 22.02.2026
- **Глобальный аудит:** 145 фиксов (async, security, DB, frontend, ML, parsers) — 25.03.2026
- **B2B-rebuild Phase 1-6:** 5 веток `feat/b2b-rebuild-phase{1..5}`, ~69 коммитов — 04.05.2026
  - Phase 1: 30 backend-задач (10 новых endpoints, 7 dead удалено, 5 парсеров расширены, MethodologyService, ParserHealthService).
  - Phase 2: 9 AI-задач (6 новых RMS-tools, 8 правил методологии в промпте).
  - Phase 3: 10 frontend-задач (Yandex Maps, 4-tab Analytics, Layout/Home/Forecast/Events/HotelDetail/About rebuild).
  - Phase 4: UML-модели (UC11/12, 5 сущностей, FR3.8/3.9/4.7, NFR7).
  - Phase 5-6: верификация, презентация, persona walkthrough, merge guide.
- **UI quality pass:** russian-tooltip readability, 17 Recharts tooltips через `chartTheme`, MethodologyTooltip auto-flip, 11 категорий событий с понятными лейблами — 06.05.2026
- **Data quality pass:** Hotels accommodation_type через 101hotels live (262) + OSM Overpass cross-ref (363), 18 типов в распределении. LLM-classify через Mistral для 209 events, 177 reclassified. APScheduler cron каждые 6h. events_irk image_url через DOM-walking. — 06.05.2026
- **Bug fixes:** events_irk description убран (брал title соседа), detect_event_type получил title-priority phase (фиксит «Спектакль» с фейк-description «экскурсия» → tour). PYTHONIOENCODING=utf-8 для Crawl4AI на Windows. — 06.05.2026
- **AI agent hardening** (08.05.2026):
  - Index-based dedup `tool_call_id` (Mistral/Groq parallel-tool bug).
  - Автоматический LLM fallback chain Groq → DeepSeek → Mistral в `main_agent.call_model`.
  - SSE heartbeat 15с (`/api/query/stream`).
  - `LLM_EXPLAIN_TIMEOUT_S` 5→30s (`/api/forecast/explain`).
  - Stress-test runner `tests/agent_stress_test.py`: 19 запросов / 6 edge-cases / rubric 5 баллов. Финальный прогон **19/19 OK, 0 fails, avg 4.63/5**.
- **UX/UI pass 2** (08.05.2026):
  - `MethodologyTooltip` переписан на React Portal (`createPortal`, `z-[9999]`, `position:fixed`) — больше не обрезается в `overflow:hidden` контейнерах.
  - Карта (`Map.tsx` + `YandexMap.tsx`): two-step click — 1-й клик пинит, 2-й или кнопка «Открыть карточку» переходит. Pinned маркер визуально отличается (`circleDotIcon`).
  - Analytics RMS-таблица: drill-down с `expandedDistrict` state. Эндпоинт `/api/analytics/district-segments?district=...`.
  - About: блок «Что не делает система» переписан на `<details>` с расшифровкой каждого ограничения (ADR proxy, comp set, real-time pickup, channel mix, GOPPAR, Telegram MTProto, Alembic).
  - Forecast: блок описания моделей под таблицей метрик; самовалидация — Д1/Д2 заменены на `DD MMM` (даты) с `MethodologyTooltip`.
  - `localizeFeatures.ts`: добавлены `lag_60`, `lag_90`, `lag_180`, `lag_365`, `diff_1`, `diff_7`.
  - Дедуп событий: read-time merge в `routers/events.py` по `(normalize(title), date_start)` + поле `also_at: list[str]` в Event схеме. На live-данных склеиваются 8+ дублей (МакSим, Баста, Ани Лорак, ЛСП, etc).
  - Telegram parser: `?channels=baikalgora,glagol38` параметр + per-channel логи в `events_telegram.py`.

## Архитектурные решения

### Categorization без хардкода
- Phase A: schema.org `@type` mapping (MusicEvent → concert, TheaterEvent → theater, ...) — semantic, бесплатно.
- Phase B: keyword-based detect (`detect_event_type` в `base.py`) с ~110 морфологическими корнями (концерт/выставк/литературн/...) — НЕ конкретные имена событий или артистов.
- Phase C: LLM Mistral structured output для оставшегося `'event'` fallback — асинхронно через cron, $0.15 на полный прогон.

### Title-priority в classifier
`detect_event_type` имеет две фазы: сначала match только в `title`, затем в `title+description`. Это блокирует ловлю keyword'а в шумном description (например, фейк-описание «экскурсия» от соседнего события не превратит «Спектакль-квартирник» в `tour`).

### COALESCE-upsert для hotels
`db_service.save_hotels` в `ON CONFLICT DO UPDATE` использует `func.coalesce(excluded.X, Hotel.c.X)` — новые NULL не перетирают существующие значения. Полезно для cross-source enrichment (101hotels → OSM → Xotelo).

### Auto-failover для внешних API
- OSM Overpass: 2 публичных endpoint'а в очереди, основной упал — fallback на kumi.systems автоматически.
- **LLM agent** (`main_agent.call_model`): chain `[primary, groq, deepseek, mistral]`. На любом 429/402/401/403/5xx/timeout автоматически переключается, в логах виден `falling back to ...`. Каждый провайдер строится лениво в `_PROVIDER_LLM_CACHE`. Stress-test 19 запросов: **19/19 OK, avg score 4.63/5** при том что Groq был исчерпан → запросы прозрачно ушли на Mistral.
- **LLM service** (для не-tool вызовов в `llm_service.py`): отдельная цепочка Mistral → DeepSeek → GigaChat → ... при ошибках.

### Cross-source merge событий (read-time дедуп)
В `routers/events.py:_dedup_events` после получения списка из БД события группируются по `(normalize(title), date_start)`. Из группы выбирается «самая полная» запись (по `_completeness_score`: count непустых description/image_url/address/time_start/price_min/url), остальные source_id попадают в поле `also_at: list[str]`. UI (`frontend/src/pages/Events.tsx`) показывает badge «также: kassir, yandex». Не требует миграции БД — работает на чтении.

### Drill-down RMS-таблицы
`db_service.district_segment_breakdown(district)` отдаёт breakdown района:
- `by_size`: mini (≤15 номеров) / mid (16–50) / large (51+) с avg_occupancy, avg_min_price, revpar.
- `by_accommodation_type`: тип размещения × count + те же метрики.
Используется на `/analytics` страница — клик по строке RMS-таблицы раскрывает inline-таблицу с этими метриками. Кэш Redis 300s.

### v2 Event-схема
Поля: `id, title, description, date_start, date_end, time_start, event_type, location, address, price, price_min, price_max, source, url, image_url, age_restriction, category, tags, parsed_at`. Соответствие парсер → JSON-LD `@type` → семантическая категория → русский UI-label через `localize.ts`.

### Strict-mode для honest empty-date в `/api/analytics/hotels-map`
`db_service.get_hotel_stats_on_date(target_date, strict: bool = False)` имеет два режима:
- `strict=False` (default) — `WHERE date <= target_date ORDER BY date DESC LIMIT 1`. Fallback на ближайший предшествующий день. Используется во внутренней логике где «дашборд должен что-то показать».
- `strict=True` — `WHERE date == target_date`. Endpoint `/api/analytics/hotels-map?date=YYYY-MM-DD` зовёт его именно так — пустой день честно отдаёт `total_hotels=0, total_rooms=0`. Frontend (`Map.tsx`) показывает янтарный баннер «За DD.MM.YYYY нет данных от парсеров». Без `?date=` поведение latest-snapshot сохранено (тянет ~1428 hotels из таблицы `hotels`).

### Frontend rate-limit hardening (Map.tsx + react-query)
Backend rate-limit считает по паттерну: 60 RPM на ВСЕ `/api/analytics/*` суммарно (`middleware/rate_limit.py:_get_rate_pattern`). На дашборде «Региональная карта» это даёт два требования к фронту:
1. **`queryDistricts` при пустом фильтре → ТОП-3 районов по `hotelsCount`** (Иркутский+Улан-Удэ+Ольхонский, ~91% объёма). Aggregation всех 15 районов давала 30+ параллельных queries → 429.
2. **`defaultOptions.queries.retry` — функция, не число**. На 4xx (включая 429) `return false`, на 5xx — две попытки. `request<T>` в `api/client.ts` прикрепляет `(err as Error & {status}).status = response.status` чтобы retry-функция видела HTTP code. Иначе numeric retry умножал каждую failed query на 3.

### Yandex FullscreenControl mode='browser' + Recharts force-remount
`@pbe/react-yandex-maps` default `mode='viewport'` — CSS-based fullscreen, `document.fullscreenchange` НЕ диспатчит. В `YandexMap.tsx` контрол вынесен явно: `<FullscreenControl options={{ mode: 'browser' }} />` (тип `mode` каст через `React.ComponentProps<typeof FullscreenControl>['options']` — валиден в Yandex API, но отсутствует в @pbe-types). После выхода из fullscreen `Map.tsx` инкрементит `chartKey` → `<ResponsiveContainer key={chartKey}>` ремаунтятся, Recharts пересчитывает axes на актуальном parent rect.

### Defensive date-handling в input type="date"
`<input type="date">` может вернуть пустую строку через onChange (clear). `new Date("T00:00:00Z").toISOString()` бросает RangeError → React useMemo падает → белый экран. В `Map.tsx`:
- `isValidIsoDate(s)` — regex `^\d{4}-\d{2}-\d{2}$` + `!isNaN(Date)` check.
- `safeIso(s)` — fallback на `isoToday()` для невалидных значений.
- `shiftDate`, `seasonRangeForDate`, `periodRangeFromDate` — все используют `safeIso`.
- `<input>` `onChange` — guard через `isValidIsoDate` перед `setFocusDate`.
