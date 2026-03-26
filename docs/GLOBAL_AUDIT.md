# Глобальный аудит проекта Tourism Analytics

**Дата:** 25.03.2026
**Метод:** 3 раунда по 4 субагента (12 независимых проверок)
**Охват:** 52 Python-файла backend, 33 TS/TSX-файла frontend, 20 конфиг-файлов

## Сводка

| Критичность | Количество |
|-------------|-----------|
| Critical | 42 |
| Medium | 68 |
| Low | 35 |
| **Итого** | **145** |

Confirmed (найдено 2+ раундами): 28

## Статус исправлений

**Все 145 пунктов исправлены 25.03.2026.**

| Фаза | Описание | Пункты |
|------|----------|--------|
| A | Инфраструктура: Dockerfile non-root, docker-compose secrets/ports, nginx security headers + gzip + SSE, frontend nginx-unprivileged | 16-22, 107-108 |
| B1 | Async/sync: forecast_agent → forecast_ensemble_async, ensemble calibration → asyncio.to_thread, telegram ainvoke, chroma async wrappers | 1-4 |
| B2 | Баги: docstring placement, Prophet fallback, season consistency, format safety, protocol signatures, parser imports, weather session, 101hotels loop guard | 5-12 |
| B3 | Утечки памяти: MemorySaver TTL cleanup, POI cache LRU limit, forecast_locks cleanup | 13-15 |
| B4 | Безопасность critical: auth production block, SSE rate limit, prompt sanitization, generic error messages | 23-26 |
| C | Database: FK constraints, CHECK constraints, updated_at columns, batch inserts, transaction rollbacks, pool_recycle | 37-42, 94-97 |
| D1 | Frontend баги: best_model extraction, ExplainResponse types, phantom message fix, echarts tree-shaking, GeoMap theme | 27-31 |
| D2 | API contract: TripSummary forecast_source, HealthResponse chroma_docs, DistrictData confidence, PriceHistoryData fields, dead Pydantic models | 65-70 |
| D3 | Error handling: ErrorState на всех страницах, единообразная обработка ошибок | 57-64 |
| E | Silent failures: except:pass → logging, fallback маркировка, parser date handling, logging severity | 32-36, 98-105 |
| F1 | Валидация: days_ahead bounds, Literal types, is_connected checks, hardcoded values | 43-56 |
| F2 | Кэширование: Redis для analytics/events endpoints | 79-80, 86 |
| F3 | Performance: LLM singleton, ClientSession reuse, asyncio.gather для POI, LRU eviction | 81-85 |
| F4 | Безопасность medium: rate limiting analytics, CORS/CSP, .env.example, requirements bounds | 87-93, 106, 109-110 |
| F5 | Парсеры: date logic, User-Agent rotation, async session management | 71-78, 103-104 |
| G | Чистка: dead code, unused imports, naming fixes, accessibility aria-labels, YDB remnants removal | 111-145 |

**Повторный мини-аудит (25.03.2026):** 9/10 backend OK, 6/8 frontend OK. Найдены и исправлены 3 остаточные проблемы: sync fallback в forecast_agent.py, отсутствие ErrorState в Forecast.tsx, `any` в Dashboard.tsx.

---

## CRITICAL — требуют немедленного исправления

### Блокировка event loop (async/sync)

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 1 | `services/forecast_agent.py` | 187 | Sync `forecast_ensemble()` блокирует event loop на 10-30с. Нужно `forecast_ensemble_async` | 1B, 3C |
| 2 | `services/ensemble_service.py` | 107 | Sync `compare_models()` внутри async метода — калибровка блокирует на 20-60с | 1B, 3C |
| 3 | `parsers/events_telegram.py` | 265 | Sync `structured.invoke()` для LLM-классификации ~400 сообщений. Нужен `ainvoke` | 1D |
| 4 | `services/chroma_service.py` | 56 | Sync `embed_documents`/`embed_query` — сетевые вызовы к GigaChat блокируют loop | 1B |

### Баги в коде

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 5 | `routers/forecast.py` | 392 | Docstring ПОСЛЕ кода — мёртвый код, нет описания в Swagger для `/ensemble` | 1A |
| 6 | `routers/forecast.py` | 237 | Prophet fallback на самого себя — при ошибке тот же crash, 500 | 1A |
| 7 | `routers/analytics.py` | 94 | `_get_season` vs `constants.py:SEASON_MONTHS` — март и сентябрь классифицируются по-разному | 1A |
| 8 | `services/forecast_agent.py` | 357 | `:.1f` format на строке `'?'` — `ValueError` crash | 1B |
| 9 | `services/protocols.py` | 21 | Protocol `get_hotels` не совпадает с реальной сигнатурой DBService | 1B |
| 10 | `parsers/__main__.py` | 84 | Импорт несуществующей `fetch_and_save_weather` — `ImportError` | 1D, 3D |
| 11 | `parsers/weather_openmeteo.py` | 250 | `_session is None` в `fetch_historical` — нет `_ensure_session()` | 1D |
| 12 | `parsers/hotels_101hotels.py` | 143 | Бесконечный цикл: пустая страница + `total>0` → `collected` не растёт | 1D |

### Утечки памяти

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 13 | `services/main_agent.py` | 526 | `MemorySaver` — все сессии навсегда в RAM, нет TTL/очистки → OOM | 1B, 2D |
| 14 | `services/poi_service.py` | 44 | `_cache: dict` без TTL и размера — растёт бесконечно | 1B, 3C |
| 15 | `routers/analytics.py` | 24 | `_forecast_locks` dict — Lock объекты никогда не удаляются | 1A, 3C |

### Инфраструктура

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 16 | `backend/Dockerfile` | — | Нет `curl` — healthcheck в docker-compose всегда FAIL, стек не поднимается | 2C |
| 17 | `backend/Dockerfile` | — | Контейнер работает от root — компрометация = root-доступ | 2B, 2C |
| 18 | `docker-compose.yml` | 8 | Hardcoded пароль `tourism_pass` в git | 2B, 2C |
| 19 | `docker-compose.yml` | 27 | Redis без пароля, порт 6379 открыт наружу | 2B, 2C |
| 20 | `docker-compose.yml` | 10 | PostgreSQL порт 5432 открыт наружу | 2B, 2C |
| 21 | `frontend/nginx.conf` | — | Нет security headers для статики, нет gzip, нет SSE buffering off | 2C |
| 22 | `frontend/.env.production` | 1 | Мёртвый localtunnel URL `cold-bears-dig.loca.lt` | 2C |

### Безопасность

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 23 | `dependencies/auth.py` | 34 | Auth bypass: `API_KEY` не задан → все endpoints открыты даже в production | 1D, 2B |
| 24 | `routers/query.py` | 67 | SSE `/stream` без auth — LLM abuse, DoS через 100+ длинных соединений | 1A, 2B |
| 25 | `services/llm_service.py` | 559 | Prompt injection: `query` напрямую в контекст LLM без санитизации | 2B, 2D |
| 26 | `services/main_agent.py` | 456 | `str(e)` в ответе пользователю — утечка внутренних ошибок (API keys, SQL) | 2D |

### Frontend — баги и типы

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 27 | `pages/Situation.tsx` | 398 | `compareData.metrics.best_model` — wrong path, `best_model` внутри `metrics` dict | 1C, 3A |
| 28 | `api/client.ts` | 173 | `ExplainResponse.forecasts: Record<string, number>` — реально `Record<string, List>` | 3A |
| 29 | `pages/Chat.tsx` | 96+131 | Двойное сообщение при ошибке — пустой пузырь + ошибка | 1C |
| 30 | `pages/Dashboard.tsx` | 12 | `import * as echarts from 'echarts'` — +800KB в бандл вместо tree-shaking | 1C |
| 31 | `components/GeoMap.tsx` | 72-138 | Hardcoded тёмные цвета (#1c1c2e) — сломано в светлой теме | 1C |

### Silent Failures

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 32 | `routers/analytics.py` | 988-1003 | `except Exception: pass` × 4 в best-dates — погода/события молча пропускаются | 3B |
| 33 | `services/neuralprophet_service.py` | 133 | Events `except: pass` — прогноз без событий без уведомления | 3B |
| 34 | `parsers/__init__.py` | 220 | Major events `except: pass` — потеря событий без логирования | 1D, 3B |
| 35 | `services/ensemble_service.py` | 56-84 | Все 3 модели могут упасть → пустой `ensemble: []` с HTTP 200 | 3B |
| 36 | `services/neuralprophet_service.py` | 155 | Fallback на линейную экстраполяцию без маркировки — попадает в Ensemble как "реальный" | 3B |

### Database

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 37 | `db/models.py` | 51 | Нет FK `hotel_statistics.id → hotels.id` — orphan записи | 2A |
| 38 | `services/db_service.py` | 370 | N+1: `save_hotels` — отдельный INSERT на каждый отель (200+ roundtrip) | 1B, 2A |
| 39 | `services/db_service.py` | 399 | N+1: `save_statistics` — аналогично | 2A |
| 40 | `services/db_service.py` | 359-564 | 4 метода без try/rollback: `delete_events_by_source`, `save_hotels`, `save_statistics`, `update_hotel_metadata` | 2A |
| 41 | `db/models.py` | 29-56 | Нет CHECK constraints (rating 0-5, price >= 0, lat/lon, occupancy 0-100) | 2A |
| 42 | проект | — | Нет Alembic миграций — невозможно ALTER TABLE без пересоздания | 2A |

---

## MEDIUM — существенные недоработки

### Backend — валидация и качество

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 43 | `routers/forecast.py` | 389 | Скрытый `days` параметр обходит валидацию `days_ahead` | 1A |
| 44 | `routers/forecast.py` | 589 | `/explain` — нет валидации `days_ahead`, `target_date`, `district` | 1A |
| 45 | `routers/analytics.py` | 1033 | `/hotels-map` — единственный endpoint без `data.is_connected` проверки | 1A |
| 46 | `routers/analytics.py` | 1089 | `/poi` — `category` без whitelist, `limit` без `le=` | 1A |
| 47 | `routers/analytics.py` | 205 | Hardcoded год 2025 в проверке пробела данных | 1A |
| 48 | `routers/analytics.py` | 1270 | Hardcoded Росстат данные (20 строк) в теле функции | 1A |
| 49 | `routers/query.py` | 137 | `/test-llm` — HTTP 200 при ошибке LLM (должен быть 5xx) | 1A |
| 50 | `routers/forecast.py` | 460 | `type(e).__name__` в ответе клиенту — information leak | 1A, 2B |
| 51 | `routers/forecast.py` | 283 | Hardcoded `"Irkutsk"` на английском (весь проект на русском) | 1A |
| 52 | `routers/documents.py` | 52 | `chroma.search("")` — semantic search пустой строки вместо `collection.get()` | 1A, 2D |
| 53 | `models/schemas.py` | 65 | `session_id` без `max_length`/формата — DoS и session hijacking | 2B, 2D |
| 54 | `routers/events.py` | 8 | Прямой `data_service` import вместо DI в 5 endpoints | 1A |
| 55 | `routers/parser.py` | 221 | Кросс-импорт `reindex_chroma` из `documents.py` — связность между роутерами | 1A |
| 56 | `config.py` | 25 | `llm_provider: str` без `Literal` — опечатка не вызовет ошибку | 2C |

### Frontend — состояния и UX

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 57 | `pages/About.tsx` | 64 | KPI запрос без `isLoading`/`isError` — при ошибке показывает `490+` | 1C |
| 58 | `pages/Situation.tsx` | — | 8 из 10 запросов без обработки ошибок | 1C |
| 59 | `pages/Map.tsx` | — | 4 из 6 запросов без обработки ошибок | 1C |
| 60 | `pages/Dashboard.tsx` | — | `priceHistory`, `districtsData` без error handling | 1C |
| 61 | `pages/Chat.tsx` | 151 | useEffect с пропущенными зависимостями | 1C |
| 62 | `pages/Events.tsx` | 35 | 10 типов событий с hardcoded hex-цветами | 1C |
| 63 | `pages/Dashboard.tsx` | 308 | ECharts scatter — hardcoded hex для occupancy levels | 1C |
| 64 | Все страницы | — | Inconsistent error handling: 3 паттерна (ErrorState / inline / нет) | 1C |

### API Contract

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 65 | `api/client.ts` | 185 | `TripSummary` — отсутствует поле `forecast_source` (backend отдаёт) | 3A |
| 66 | `api/client.ts` | 312 | `HealthResponse` — отсутствует `chroma_docs` | 3A |
| 67 | `api/client.ts` | 97 | `DistrictData` — отсутствует `confidence` поле | 3A |
| 68 | `api/client.ts` | 106 | `Recommendation.period` — optional в backend, required в frontend | 3A |
| 69 | `api/client.ts` | 231 | `PriceHistoryData` — не включает `district`, `trend`, `period` | 3A |
| 70 | `models/schemas.py` | 184-222 | 6 dead Pydantic models: CorrelationResponse, EventsImpact, HeatmapPoint, MonthlyStats, DistrictStats, DistrictData | 3A, 3D |

### Парсеры

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 71 | `parsers/events_culture38.py` | 163 | Дата-логика не проверяет `day < today.day` при совпадении месяца | 1D |
| 72 | `parsers/events_culture38.py` | 173 | ID без даты → коллизии одноимённых событий | 1D |
| 73 | `parsers/events_culture_rf.py` | 213 | Сессия BaseParser не закрывается (утечка) | 1D |
| 74 | `parsers/events_irk.py` | 30 | Нет retry, hardcoded UA | 1D |
| 75 | `parsers/hotels_101hotels.py` | 105 | HTTP без timeout и User-Agent | 1D |
| 76 | `parsers/hotels_xotelo.py` | 102 | Нет User-Agent, нет retry | 1D |
| 77 | `parsers/anti_detection.py` | 28 | Устаревшие User-Agent (Chrome 119/120) | 1D |
| 78 | `parsers/base.py` | 70 | Один hardcoded UA без ротации из `anti_detection` | 1D |

### Performance — кэширование

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 79 | `routers/analytics.py` | — | 13 из 17 endpoints без кэша (correlation, districts, kpi, heatmap...) | 3C |
| 80 | `routers/events.py` | — | GET `/events` без кэша | 3C |
| 81 | `services/main_agent.py` | 429 | `get_llm_with_tools()` создаёт новый LLM на каждый вызов (2-4 раза за запрос) | 1B, 2D |
| 82 | `services/weather_service.py` | 80 | `ClientSession` создаётся на каждый HTTP-запрос | 1B |
| 83 | `services/poi_service.py` | 118 | `get_all_categories` — 6 последовательных HTTP вместо `asyncio.gather` | 3C |
| 84 | `services/weather_service.py` | 38 | Кэш может расти сверх `MAX_CACHE_SIZE` (нет LRU eviction) | 1B, 3C |
| 85 | `executor.py` + services | — | Два разных thread pool (custom 4-thread + default) — рассинхрон | 3C |
| 86 | `routers/analytics.py` | — | In-memory кэш не проверяет Redis → двойное вычисление | 3C |

### Безопасность (medium)

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 87 | `middleware/rate_limit.py` | 25 | `/api/analytics/*` не покрыт rate limiting | 2B |
| 88 | `main.py` | 132 | Нет `Content-Security-Policy`, `HSTS`, `Permissions-Policy` | 2B |
| 89 | `main.py` | 123 | CORS `allow_methods` включает DELETE (нет DELETE endpoints) | 1D, 2B |
| 90 | `main.py` | 146 | ValueError handler пропускает SQL-ошибки, config names | 2B |
| 91 | `routers/analytics.py` | 1089 | POI `category` без whitelist — potential Overpass injection | 2B |
| 92 | `.env.example` | 88 | `API_KEY=your-secret-key-here` — может быть использован как реальный | 2B, 2C |
| 93 | `.env.example` | — | Отсутствуют `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` (os.getenv bypass) | 2C |

### Database (medium)

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 94 | `db/session.py` | 22 | Нет `pool_recycle` — idle connections могут закрываться firewall/LB | 2A |
| 95 | `db/session.py` | 48 | `get_db()` / `DbSession` — мёртвый код, никто не использует DI для сессий | 2A |
| 96 | `db/models.py` | — | Нет `updated_at` на таблицах с upsert | 2A |
| 97 | `services/db_service.py` | 341 | Неидиоматичное `pg_insert(Event).excluded` — лишние объекты | 2A |

### Silent Failures (medium)

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 98 | `routers/analytics.py` | 603-919 | 8 случаев `logger.warning` вместо `logger.error` для реальных отказов | 3B |
| 99 | Ensemble + forecast | — | 5 endpoints возвращают HTTP 200 с пустым/degraded ответом вместо ошибки | 3B |
| 100 | `services/chroma_service.py` | 54-114 | Вся RAG молча отключается без embeddings — AI отвечает без контекста | 3B |
| 101 | `services/llm_service.py` | 624 | LLM fallback tools→RAG без уведомления пользователя | 3B |
| 102 | `routers/analytics.py` | — | ~25 случаев `or 0` скрывают NULL → "0% загрузка" вместо "нет данных" | 3B |
| 103 | `parsers/events_culture38.py` | 167 | Ошибка парсинга даты → fallback на `date.today()` | 3B |
| 104 | `parsers/events_zeroevent.py` | 145 | Невалидная дата → fallback на 1 января | 3B |
| 105 | `services/llm_service.py` | 496 | Нет fallback-цепочки между LLM-провайдерами | 2D |

### Config/Infra (medium)

| # | Файл | Строка | Описание | Раунды |
|---|------|--------|----------|--------|
| 106 | `config.py` | 18 | Hardcoded `tourism_pass` как default DATABASE_URL | 2B, 2C |
| 107 | `frontend/Dockerfile` | — | Nginx от root — нужен `nginx-unprivileged` | 2C |
| 108 | `docker-compose.yml` | — | Frontend без healthcheck | 2C |
| 109 | `requirements.txt` | 17-26 | Нет upper bounds на критичных deps (numpy, pandas, sklearn) | 2C |
| 110 | `requirements.txt` | 67 | pytest в production image | 2C |

---

## LOW — улучшения и чистка

### Dead code

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 111 | `routers/forecast.py:631` | Дублирование логирования ошибки (2 строки подряд) | 1A |
| 112 | `routers/documents.py:172` | Legacy alias `/index-db` скрытый от schema | 1A |
| 113 | `routers/analytics.py:582,648,754` | Дублированные импорты внутри функций (timedelta, defaultdict) | 1A, 3D |
| 114 | `routers/events.py:226` | Повторный `import hashlib` внутри функции | 1A, 3D |
| 115 | `services/db_service.py:44` | Мёртвый метод `_session()` | 1B, 3D |
| 116 | `parsers/health_monitor.py:227` | `monitored()` декоратор нигде не применён | 1D, 3D |
| 117 | `parsers/anti_detection.py:357,373` | `with_rate_limit()` и `with_cache()` нигде не применены | 3D |
| 118 | `services/holidays_service.py:137` | `get_holiday_features()` нигде не вызывается | 3D |
| 119 | `dependencies/auth.py:61` | `optional_api_key()` нигде не подключён | 3D |
| 120 | 6 моделей в `schemas.py` | MonthlyStats, CorrelationResponse, DistrictData, Recommendation, EventsImpact, HeatmapPoint | 3A, 3D |
| 121 | 10 backend endpoints | Нет вызовов из frontend: `/poi`, `/revpar`, `/price-recommendation`, `/rosstat`, `/data-coverage`, `/hotels-by-city`, `/neural`, `/xgboost`, `/compare`, `/holidays` | 3A |

### Неиспользуемые импорты (30+)

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 122 | parsers/ (18 файлов) | ~19 неиспользуемых импортов: `date`, `settings`, `aiohttp`, `Any`, `Optional`, `asyncio`, etc. | 3D |
| 123 | services/ (7 файлов) | ~7 неиспользуемых: `Any`, `Forecast`, `QueryHistory`, `json`, `timedelta`, `END`, `Set` | 3D |
| 124 | routers/ (3 файла) | ~5 неиспользуемых: `Depends`, `datetime`, `DistrictStats`, `ParserResult`, `Any` | 3D |
| 125 | `db/models.py` | `BigInteger` не используется | 3D |

### Frontend — мелочи

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 126 | `pages/Situation.tsx:38` | `resolvedDistrict = selectedDistrict` — бессмысленный alias | 1C |
| 127 | `pages/Situation.tsx:109` | Тривиальные `useMemo` для `data || []` | 1C |
| 128 | `lib/cn.ts:4` | Тип `cn()` слишком узкий — не принимает объекты | 1C |
| 129 | `utils/export.ts:42` | Hardcoded hex-цвета фона для PNG export | 1C |
| 130 | `components/InsightCard.tsx` | Tailwind-цвета вместо CSS-переменных | 1C |
| 131 | `components/ui/Input.tsx` | `Input`, `Textarea`, `Select` — нигде не импортируются | 3D |
| 132 | `components/ui/Card.tsx` | `CardDescription`, `CardFooter` — нигде не импортируются | 3D |
| 133 | GeoMap, Dashboard | ~9 `any` кастов в ECharts handlers | 1C |

### Naming inconsistencies

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 134 | `parsers/weather_openmeteo.py:30` | Ключ `leestvyanka` — опечатка (listvyanka) | 3D |
| 135 | `services/neuralprophet_service.py:427` | `dict[str, any]` — строчная `any` вместо `Any` | 1B, 3D |
| 136 | services/ | Смесь `Dict`/`List` (typing) и `dict`/`list` (builtin) | 3D |

### Accessibility

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 137 | Forecast, Events, Map | Icon-only кнопки без `aria-label` | 1C |
| 138 | `pages/Chat.tsx:275` | Input без `<label>` и `aria-label` | 1C |
| 139 | `pages/Events.tsx:360` | Calendar grid без ARIA-ролей | 1C |

### YDB remnants

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 140 | `backend/.env` | Строки `DB_BACKEND`, `YDB_ENDPOINT`, `YDB_DATABASE`, `YDB_AUTH_KEY_PATH` | 3D |
| 141 | `backend/scripts/migrate_ydb_to_pg.py` | Скрипт миграции 196 строк — можно удалить | 3D |
| 142 | `.cursor/rules/*.mdc` | `no-demo-data.mdc`, `project-context.mdc` ссылаются на YDB как текущую БД | 3D |

### Прочее

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 143 | `parsers/events_major.py` | Статические данные 2025-2026 устаревают, нет механизма обновления | 1D |
| 144 | `parsers/anti_detection.py:373` | `with_cache` создаёт новый кэш при каждом вызове | 1D |
| 145 | `routers/analytics.py:87` | `_get_month_name` дублирует `MONTH_NAMES_RU` из constants | 1A |

---

## Не подлежит исправлению (объективные ограничения)

- **R2 < 0 у всех моделей** — пробел данных июль-сентябрь 2025, решится к октябрю 2026
- **rooms_num=0 у 69% Xotelo-only отелей** — ограничение API 101Hotels
- **GeoMap упрощённый полигон Иркутской области** — для демо достаточен
- **Цвета ECharts не через CSS variables** — ограничение ECharts API (частично)
- **Росстат 2024 / events_major** — статические справочные данные
- **Server: uvicorn в заголовках** — uvicorn добавляет на уровне протокола
- **TripAdvisor данные null** — требует отдельного парсинга

---

## Рекомендуемый порядок исправления

### Фаза A: Инфраструктура (1-2 часа)
Пункты: 16, 17, 18, 19, 20, 21, 22, 107, 108

### Фаза B: Критические баги (2-3 часа)
Пункты: 1-12, 23-26

### Фаза C: Database (1-2 часа)
Пункты: 37-42

### Фаза D: Frontend типы и UX (1-2 часа)
Пункты: 27-31, 57-64, 65-69

### Фаза E: Silent failures (1-2 часа)
Пункты: 32-36, 98-105

### Фаза F: Кэширование и performance (1-2 часа)
Пункты: 79-86

### Фаза G: Чистка (1 час)
Пункты: 111-145
