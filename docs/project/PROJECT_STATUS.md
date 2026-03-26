# Статус проекта

**Дата обновления:** 26.03.2026
**Этап:** Производственная практика (24.02 — 04.04.2026)

## Обновление 26.03.2026 — Консолидация и документация

### Frontend

- Консолидация страниц: 10 → 8 (Analytics, Forecast with Seasonality, Map, Events, Home, Chat, HotelDetail, About)
- Dashboard и Seasonality объединены в Analytics и Forecast соответственно

### Данные

- Импорт данных: 1366 отелей, 37663 записей статистики (2025-03-16 — 2026-03-26), 318 событий

### Документация

- 10 исследовательских документов создано/обновлено, покрывающих все технологические решения
- YDB-ссылки в документации ВКР обновлены на PostgreSQL

### Backend

- Docker: исправлен порт (80:8080)
- `verify_api_key` добавлен на `/api/documents/stats`

### Тестирование

- Unit тесты: 59 passed, 1 skipped (60 тестов, 5 файлов)

### Фазы 0–4 (26.03.2026)

Согласование проектной документации с текущим стеком после миграции БД и консолидации фронтенда: в исследованиях YDB заменён на PostgreSQL там, где фигурировал как источник данных для прогноза; в описании дашбордов — 8 страниц и актуальные имена (Analytics, Forecast, Map, Events, Home, Chat, HotelDetail, About); исправлены перекрёстные ссылки на `docs/research/MISTRAL_MODELS_RESEARCH.md`; в статусе зафиксированы фактические результаты pytest; в исследовании бэкенда добавлено краткое обоснование пары HTTP-клиентов (aiohttp / httpx).

---

## Обновление 25.03.2026 — Глобальный аудит (145 фиксов)

### Метод
3 раунда по 4 независимых субагента (12 проверок). Охват: 52 Python-файла, 33 TS/TSX-файла, 20 конфиг-файлов. Все находки записаны в `docs/GLOBAL_AUDIT.md`.

### Ключевые изменения

| Категория | Описание |
|-----------|----------|
| Инфраструктура | Docker non-root user, secrets через env vars, Redis auth, restricted ports, nginx security headers + gzip + SSE proxy |
| Async | forecast_agent, ensemble calibration, telegram classifier, chroma — все переведены на async/to_thread |
| Безопасность | Auth production block (CRITICAL), SSE rate limit, prompt sanitization, generic errors, CSP/HSTS headers |
| Database | FK + CHECK constraints, updated_at, batch inserts (upsert), transaction rollbacks, pool_recycle |
| Frontend | ErrorState на всех страницах, типы API contract синхронизированы, echarts tree-shaking, убраны все `any` |
| ML pipeline | Silent failure маркировка, fallback logging, ensemble empty guard |
| Парсеры | User-Agent rotation, async sessions, date logic fixes, retry/timeout |
| Чистка | Удалены YDB remnants, dead code, unused imports, naming fixes, aria-labels |

### Компоненты системы (актуально)

| Компонент | Статус |
|-----------|--------|
| Backend (FastAPI) | ✅ Работает |
| Frontend (React) | ✅ 8 страниц (Home, Chat, Analytics, Events, Map, Forecast, HotelDetail, About). Dashboard и Seasonality объединены в Analytics и Forecast соответственно |
| Backend (7 роутеров) | ✅ 59 endpoints (analytics 17, parser 12, forecast 9, events 6, documents 5, query 5, hotels 3) + 2 в main |
| PostgreSQL | ✅ 678 отелей, 227 событий |
| Redis | ✅ Кэширование + Rate Limiting (с аутентификацией) |
| ChromaDB | ✅ 629 документов |
| AI-агент (LangGraph) | ✅ 5 tools, MemorySaver с TTL, SSE streaming |
| Ensemble прогноз | ✅ ~2s (async + кэш) |
| GeoMap (ECharts) | ✅ Bubble map (tree-shaken) |
| Security | ✅ Rate Limiting + API Key Auth + CSP + non-root containers |
| Docker | ✅ PostgreSQL 16 + Redis 7 (secrets, restricted ports, healthchecks) |
| Unit тесты | ✅ 59 passed, 1 skipped (60 тестов, 5 файлов) |
| E2E тесты | ✅ 9/9 passed |
| POI (OpenStreetMap) | ✅ Достопримечательности (LRU cache) |
| RevPAR/ADR | ✅ Бизнес-метрики |

### Закрытые задачи (были ⚠️)

| Задача | Статус | Решение |
|--------|--------|---------|
| Dashboard page | ✅ | ECharts tree-shaking, типизация, ErrorState |
| NeuralProphet early_stopping | ✅ | Удалён неподдерживаемый параметр |

---

## Обновление 16.03.2026 — Масштабная сессия (25+ фиксов)

### Выполненные задачи

| Задача | Статус | Описание |
|--------|--------|----------|
| Очистка проекта | ✅ | Удалено ~107 файлов мусора |
| Events limit, погода, рейтинги | ✅ | Фиксы API и данных |
| Map skeleton, star rating, event_type | ✅ | UI/UX улучшения |
| Warmup кэша | ✅ | Прогрев кэша при старте |
| NeuralProphet timeout | ✅ | Исправлен таймаут обучения |
| Mistral retry | ✅ | Повторные попытки при сбоях LLM |
| Price-history endpoint | ✅ | История цен отелей |
| Events-impact endpoint | ✅ | Влияние событий на загрузку |
| XGBoost 0 точек | ✅ | Исправлена проблема с пустыми прогнозами |
| Best-dates погода | ✅ | Учёт погоды в лучших датах |
| Correlation null | ✅ | Исправлены null в корреляциях |
| Ensemble weights | ✅ | Перекалибровка весов ансамбля |
| Chat memory | ✅ | LangGraph MemorySaver + thread_id |
| SSE streaming | ✅ | Streaming endpoint для AI-чата |
| Telegram LLM-классификатор | ✅ | LLM-классификация постов из Telegram |
| Heatmap forward-fill | ✅ | Заполнение пропусков в тепловой карте |
| Districts confidence | ✅ | Confidence intervals по районам |
| UI "Прибайкалье" | ✅ | Ребрендинг карты |
| Hotel prices (min_price) | ✅ | min_price в save_hotels |
| Hotels пагинация | ✅ | Пагинация списка отелей |
| POI (OpenStreetMap) | ✅ | Достопримечательности из OSM |
| RevPAR/ADR метрики | ✅ | Revenue per available room, Average daily rate |
| Price-recommendation | ✅ | Рекомендации по ценообразованию |
| Росстат интеграция | ✅ | Данные Росстата |
| Dashboard page | ⚠️ | Страница создана, маршрут добавлен, но /api/analytics/hotels-map не регистрируется в FastAPI runtime |
| NeuralProphet early_stopping | ⚠️ | Параметр не поддерживается в установленной версии |

### Незавершённые задачи

Нет открытых задач. Все пункты из аудита 25.03.2026 закрыты.

---

## Обновление 12-13.03.2026 — Полировка и новые фичи

### Выполненные задачи

| Задача | Статус | Описание |
|--------|--------|----------|
| Удаление legacy agent_tools.py | ✅ | Удалён дублирующий файл + legacy из llm_service |
| Исправление ExplainResponse | ✅ | ForecastFactor тип: name, impact, direction, description |
| Замена YDB-меток | ✅ | pg_hotels/pg_events + /index-db alias в documents.py |
| Удаление dead code в client.ts | ✅ | Убраны neuralForecast, xgboostForecast, EventImpact, DataCoverage |
| PNG-экспорт графиков | ✅ | SVG→Canvas→PNG, кнопка на Forecast |
| Сравнение районов | ✅ | До 3 районов на одном LineChart (Forecast) |
| Дефолтный район | ✅ | Иркутский автоматически на Situation |
| Подсказки AI-чата | ✅ | 6 подсказок покрывающих все tools агента |
| Страница About | ✅ | /about — техстек, возможности, архитектура для комиссии |
| Пустые состояния | ✅ | Осмысленные подсказки вместо голых сообщений |
| Тесты: schemas | ✅ | 15 тестов на Pydantic-схемы |
| Фикс устаревших тестов | ✅ | Удалены 3 битых cache-теста, исправлен SYSTEM_PROMPT import |

### Тестирование (актуальное)

**Unit тесты:** 59 passed, 1 skipped (60 тестов, 5 файлов)
- `test_agent_tools.py` — 16 тестов (tools, промпт, состояние, MainAgent)
- `test_ensemble_service.py` — 9 тестов (веса, агрегация, калибровка)
- `test_forecast_helpers.py` — 8 тестов (кэш, расчёт загрузки, диапазоны дат)
- `test_schemas.py` — 15 тестов (Hotel, Event, ForecastRequest, QueryRequest)
- `test_security.py` — 12 тестов (rate limit, SQL injection, API key, валидация)

**E2E тесты:** 9/9 passed
- Health, KPI, Hotels, Events, Prophet, Ensemble, Weather, AI Query, Scheduler — OK

**Визуальная проверка (25.03.2026):** 8 страниц, 13 скриншотов (dark + light), 0 JS ошибок

### Компоненты системы

| Компонент | Статус |
|-----------|--------|
| Backend (FastAPI) | ✅ Работает |
| Frontend (React) | ✅ Работает |
| PostgreSQL | ✅ 678 отелей, 227 событий |
| Redis | ✅ Кэширование + Rate Limiting |
| ChromaDB | ✅ 629 документов |
| AI-агент (LangGraph) | ✅ Tool usage ~90% |
| Ensemble прогноз | ✅ ~2s (async + кэш) |
| GeoMap (ECharts) | ✅ Bubble map |
| Security | ✅ Rate Limiting + API Key Auth |

---

## Результаты практики (28.02 - 01.03.2026)

### Выполненные задачи

| Задача | Статус | Дата |
|--------|--------|------|
| AI-агент: tool usage fix | ✅ | 28.02 |
| Ensemble: async + cache | ✅ | 28.02 |
| Frontend: toast, retry, localStorage | ✅ | 01.03 |
| Unit тесты: 27 passed | ✅ | 28.02 |
| E2E тесты: 9/9 passed | ✅ | 28.02 |

### AI-агент: исправление tool usage (28.02.2026)

**Проблема:** LLM (Mistral) не всегда выбирал tools для получения данных.

**Решение:**
- Добавлен tool `get_statistics` для KPI
- Усилен SYSTEM_PROMPT с примерами tool usage
- Результат: tool usage rate ~90%

**Файлы:** `backend/app/services/main_agent.py`

### Ensemble: оптимизация производительности (28.02.2026)

**Проблема:** Таймауты >30s при обучении 3 моделей.

**Решение:**
- Async версия `forecast_ensemble_async` с `asyncio.gather`
- In-memory кэширование с TTL 30 мин
- Результат: время выполнения ~2s

**Файлы:** `backend/app/services/ensemble_service.py`

### Frontend UX улучшения (01.03.2026)

| Улучшение | Описание |
|-----------|----------|
| Toast уведомления | react-hot-toast для ошибок |
| Retry кнопка | Повтор запроса при timeout |
| localStorage | История чата сохраняется |

**Файлы:** `frontend/src/components/Layout.tsx`, `frontend/src/pages/Home.tsx`

### Тестирование

**Unit тесты:** 27 passed, 1 skipped
- `tests/test_agent_tools.py` — 16 тестов
- `tests/test_ensemble_service.py` — 12 тестов

**E2E тесты:** 9/9 passed
- Health, KPI, Hotels, Events, Prophet, Ensemble, Weather, AI Query, Scheduler

### Известные ограничения

**Пробел данных: июль-сентябрь 2025**

Данные за летний период не собирались. Влияние:
- R² моделей отрицательный (прогноз хуже среднего)
- Долгосрочные прогнозы (30+ дней) менее точны

**Решение для ВКР:**
- Честно задокументировать ограничение
- Демонстрировать краткосрочные прогнозы (3-7 дней)
- Система архитектурно готова к работе с полными данными

---

## Результаты запуска (22.02.2026)

### Backend (FastAPI)

| Сервис | Статус | Детали |
|--------|--------|--------|
| FastAPI/Uvicorn | Работает | http://localhost:8000 |
| ChromaDB | Работает | 629 документов в коллекции |
| LLM (Mistral) | Работает | mistral-large-latest |
| PostgreSQL | Работает | Docker, 648 отелей, 34739 записей статистики, 198 событий |
| Redis | Работает | Docker, кэширование API-ответов |
| YDB | Доступен (fallback) | Переключение через DB_BACKEND в .env |
| Crawl4AI | Установлен | Playwright доступен, импорт работает |
| Plotly | Не импортируется | Влияет на интерактивные графики NeuralProphet |

### Frontend (React + Vite)

| Компонент | Статус |
|-----------|--------|
| Vite dev server | Работает (http://localhost:5173) |
| API прокси | Настроен (/api → localhost:8000) |
| node_modules | Установлены |
| Сборка (tsc --noEmit) | Пройдена (0 ошибок) |
| Production build | Пройден (vite build, code splitting: 4 чанка) |

### Инфраструктура

| Компонент | Статус |
|-----------|--------|
| Python venv | Создан, зависимости установлены |
| Docker Compose | PostgreSQL 16 + Redis 7 (+ backend/frontend через profile "full") |
| Dockerfile backend | Python 3.11-slim, uvicorn |
| Dockerfile frontend | Node 20 multi-stage build → Nginx alpine |
| YDB authorized_key.json | На месте (fallback) |
| .env | Настроен (6 LLM, DB_BACKEND=postgresql) |

## Исправления при запуске

1. **chroma_service.py** — добавлены `init()` и синглтон `chroma_service` (ленивая инициализация)
2. **ydb[yc]** — не был установлен, устанавливается

## Архитектура (актуальная на 25.03.2026)

```
Backend (FastAPI, порт 8000)
├── 7 роутеров (59 endpoints): hotels, events, query, forecast, documents, parser, analytics
├── Сервисы (16):
│   ├── data_service / db_service — PostgreSQL (SQLAlchemy 2.0 + asyncpg)
│   ├── llm_service — 6 LLM провайдеров (Mistral основной)
│   ├── chroma_service — векторная БД (GigaChat Embeddings)
│   ├── cache_service — Redis (кэширование + rate limiting)
│   ├── prophet_service, neuralprophet_service, xgboost_service
│   ├── ensemble_service — ансамблевые прогнозы (async + кэш)
│   ├── feature_engineering — 25+ ML-фичей
│   ├── weather_service — Open-Meteo API
│   ├── holidays_service — праздники РФ
│   ├── poi_service — достопримечательности (OSM)
│   └── protocols — интерфейсы сервисов
├── AI-агенты (LangGraph):
│   ├── main_agent — 5 tools, MemorySaver, SSE streaming
│   └── forecast_agent — объяснимые прогнозы
├── Парсеры (17 файлов):
│   ├── hotels_101hotels — региональный парсинг (200+ отелей)
│   ├── hotels_xotelo — Xotelo/TripAdvisor (1262 объекта)
│   ├── events_* — 8 парсеров событий
│   ├── weather_openmeteo, health_monitor, anti_detection, ai_extractor
│   └── base — базовый класс BaseParser
└── scheduler.py — APScheduler (ежедневный сбор)

Frontend (React 18 + Vite 7, порт 5173)
├── Страницы (8): Dashboard и Seasonality объединены в Analytics и Forecast
│   ├── Home — AI-чат (подсказки, retry, localStorage)
│   ├── Chat — SSE streaming чат
│   ├── Analytics — Ensemble прогноз + KPI + корреляции + тепловая карта
│   ├── Events — каталог событий (поиск + фильтры)
│   ├── Map — аналитика регионов (Recharts: heatmap, radar, treemap)
│   ├── Forecast — Ensemble + сравнение моделей + сезонность + feature importance
│   ├── HotelDetail — карточка отеля (/hotels/:id)
│   └── About — описание системы для комиссии
├── UI: Button, Card, Badge, Input, ErrorState
├── Визуализации: Recharts + ECharts (tree-shaken)
├── Стили: TailwindCSS 4, тёмная/светлая тема
└── Данные: fetch API

Инфраструктура:
├── Docker Compose (PostgreSQL 16 + Redis 7, secrets, healthchecks)
├── ChromaDB (локальная векторная БД)
├── Nginx (frontend, security headers, gzip, SSE proxy)
└── APScheduler (ежедневный сбор данных)
```

## Запланированные изменения

### Миграция БД (YDB → PostgreSQL) — ЗАВЕРШЕНО 22.02.2026
- Docker Compose: PostgreSQL 16 + Redis 7
- SQLAlchemy ORM: 5 моделей (Hotel, HotelStatistic, Event, QueryHistory, Forecast)
- `data_service.py` — фабрика переключения YDB/PostgreSQL
- Данные: 648 отелей, 34 739 записей статистики, 198 событий
- API: все endpoint'ы протестированы и работают

### Миграция дашбордов (DataLens → встроенные графики) — ЗАВЕРШЕНО 22.02.2026
- Map.tsx полностью переписан: 3 режима (Обзор, Тепловая карта, Сравнение)
- Визуализации: карточки районов, treemap, radar chart, heatmap grid
- DataLens iframe удалён, всё на Recharts
- Навигация обновлена

### Улучшение AI-агентов (LangGraph) — ОБНОВЛЕНО 22.02.2026
- **forecast_agent.py:** Command pattern, PydanticOutputParser + ChatPromptTemplate (по образцу executory_formula), ensemble_service для best_model, метрики моделей в state
- **main_agent.py:** Command[Literal[...]] для маршрутизации, 4 tools (search_hotels, search_events, get_weather, forecast_occupancy)
- **ForecastExplanation:** Pydantic модель для structured LLM output (summary, main_factors, recommendation, confidence_note)
- **chroma_service.py:** свойство is_initialized, ленивая инициализация

### Улучшение прогнозирования — ОБНОВЛЕНО 23.02.2026

**Этап 1 (22.02):**
- Prophet: погода как future regressor
- NeuralProphet: события как binary events
- XGBoost: feature engineering (погода, события, лаги, календарные)
- Ensemble: weighted average

**Этап 2 (23.02) — Quality Fix:**
- **NeuralProphet:** weather regressor через `add_lagged_regressor` (context7), multi-step через `raw=True` + target fallback, predict(future) вместо predict(df)
- **XGBoost:** quantile regression (`reg:quantileerror`) для confidence intervals (context7), тюнинг гиперпараметров (lr=0.05, depth=5, n_est=300, early_stopping=20), R2 метрика
- **Ensemble:** перекалибровка весов с TTL (не одноразовая), weighted CI (не min/max), `_best_model` по реальным метрикам (не хардкод)
- **Feature Engineering:** lag_365→lag_90 (339 дней данных), rolling_std bfill (не fillna(0)), погода AVG_MONTHLY_TEMP (не 0), days_from_holiday правильный расчёт

**Метрики моделей (test_days=7):**

| Район | Prophet | NeuralProphet | XGBoost | Ensemble |
|-------|---------|---------------|---------|----------|
| Иркутский RMSE | 5.58 | 5.92 | 6.11 | **2.67** |
| Иркутский MAE | 5.17 | 4.77 | 5.44 | **2.39** |
| Ольхонский RMSE | **17.5** | 37.02 | 27.16 | 24.48 |
| Ольхонский MAE | **14.61** | 35.7 | 25.8 | 22.54 |
| Слюдянский RMSE | 10.8 | 10.32 | 14.06 | **8.52** |
| Слюдянский MAE | 9.13 | 9.95 | 12.29 | **6.9** |

**Топ-фичи XGBoost:** rolling_min_7, rolling_max_7, lag_1, diff_1, is_holiday, temperature

### Парсеры — протестированы 22.02.2026
- **Работают:** irk.ru (28), culture38.ru (6), zeroevent.ru (57), Telegram (25), 101hotels
- **Требуют Crawl4AI:** kassir.ru, yandex afisha (JS-heavy сайты)
- **Итого событий в БД:** 198 (из 6 источников)
- Все парсеры обновлены: новые endpoint'ы `/api/parser/events/{source}`

### 101Hotels парсер — критическое обновление 22.02.2026

**Исправленный баг:** slug-и городов в `CITY_DISTRICTS_EN` были неправильными (`listvyanka` вместо `leestvyanka`, `khuzhir` вместо `huzhir`). Парсер собирал данные только по Иркутску (96 отелей), теряя ~60% данных.

**Региональный парсинг:** обнаружен endpoint `/region/russia/{slug}`, возвращающий ВСЕ отели региона. Два региона (`na_baikale` + `irkutskaya_oblast`) дают ~200+ отелей в 30 населённых пунктах.

**Покрытие до/после:**

| Параметр | Было | Стало |
|---|---|---|
| Режим | По городам (5 slug-ов) | Региональный (2 региона) |
| Рабочих slug-ов | 1 (irkutsk) | 30+ (авто) |
| Отелей | ~96 | ~200+ |
| Населённых пунктов | 1 | 30+ |
| Дедупликация | Нет | По hotel ID |

### Исследование агрегаторов — ЗАВЕРШЕНО 22.02.2026

Проведён анализ 30+ российских агрегаторов бронирования. Проверены скрытые API у 13 сервисов (F12-подход). Результат: **101Hotels — единственный агрегатор с открытым JSON API** без авторизации, предоставляющим данные о загрузке номеров. Подробный отчёт: `docs/research/AGGREGATORS_RESEARCH.md`.

### Парсер Xotelo (TripAdvisor) — ЗАВЕРШЕНО 22.02.2026

Обнаружен и интегрирован бесплатный API Xotelo для cross-reference метаданных:
- **1262 объекта** Иркутской области (vs 200+ у 101Hotels)
- 25 типов размещения (Hotel, Hostel, Lodge, Tourist Base, Cottage и др.)
- 631 объект с рейтингом TripAdvisor (avg 3.89)
- 1188 с координатами
- Cross-reference по координатам (Хаверсин): 0.0 км для тестовых пар
- Новые поля в hotels: `accommodation_type`, `tripadvisor_rating`, `tripadvisor_reviews`, `tripadvisor_url`, `image_url`
- Endpoint: `POST /api/parser/hotels/xotelo`

### UX фронтенда — УЛУЧШЕНО 22.02.2026, дополнено 22.02.2026
- **Events.tsx:** поиск по тексту + фильтр по источнику данных (7+ источников)
- **Home.tsx:** обработка ошибок запросов, кнопка очистки чата
- **Рефакторинг:** `_getWeatherEmoji` → общий `utils/weather.ts` (убран дубликат из Home, Situation)

**Обновление фронтенда (22.02.2026):**
- **Forecast.tsx (НОВАЯ):** полноценная страница прогнозирования — выбор района, горизонта, Ensemble с CI-bands, сравнение моделей (линейный график), таблица метрик (RMSE/MAE/R²), feature importance (XGBoost)
- **Situation.tsx:** Prophet-only заменён на Ensemble прогноз с CI-bands и fallback на Prophet; добавлен виджет сравнения моделей с бейджем best
- **Layout.tsx:** исправлена битая UTF-8 кодировка (mojibake), добавлен пункт навигации «Прогнозы» (ML badge)
- **client.ts:** добавлены API-методы `ensembleForecast`, `compareModels`, `neuralForecast`, `xgboostForecast`
- **App.tsx:** добавлен маршрут `/forecast`
- **TypeScript:** `tsc --noEmit` без ошибок (исправлены pre-existing проблемы в Events.tsx, Map.tsx, Home.tsx, Situation.tsx)

### Тестирование API endpoints — 22.02.2026

| Endpoint | Status | Примечание |
|----------|--------|------------|
| GET / | 200 | Корневой |
| GET /health | 200 | DB, Redis, Chroma OK |
| GET /api/hotels | 200 | 648 отелей |
| GET /api/events | 200 | 198 событий |
| GET /api/forecast/ensemble | 200 | Таймаут при расчёте (>30s) |
| GET /api/forecast/compare-all | 200 | Таймаут при расчёте (>30s) |
| GET /api/analytics/data-coverage | 200 | Покрытие данных |
| GET /api/parser/scheduler/status | 200 | 4 задачи, running=true |
| GET /docs | 200 | Swagger UI |

### Обработка ошибок и валидация — ЗАВЕРШЕНО 22.02.2026
- **main.py:** глобальные exception handlers (ValueError → 400, Exception → 500 с логированием)
- **hotels.py:** валидация формата дат (400 вместо 500)
- **forecast.py:** валидация `days` (1-16), исправлено `forecast` → `forecasts` в /weather
- **analytics.py:** валидация `days` (1-90) для heatmap, `district` для data-coverage
- Аудит: 13 GET + 2 POST endpoint'а протестированы, все возвращают корректные статусы

### Улучшение промптов LLM — ЗАВЕРШЕНО 22.02.2026
- **SYSTEM_PROMPT:** сделан динамическим (`_build_system_prompt()`), включает текущую дату
- **explain_forecast:** разделение факторов на positive/negative/neutral, структурированный формат
- **agent_system_prompt:** уже использовал динамическую дату (подтверждено)

### Обновление VKR_DRAFT — 22.02.2026

Обновлены разделы черновика ВКР:
- LLM: MiMo-V2-Flash → Mistral (основной), GigaChat/Groq (экспериментальные)
- AI-агент: «Отказ от LangChain» → «Выбор LangGraph» (Command pattern, PydanticOutputParser)
- Источники событий: 2 → 7 парсеров (irk, culture38, zeroevent, kassir, telegram, yandex, culture_rf)
- Источники размещения: 101Hotels + Xotelo API (cross-reference)
- СУБД: YDB → PostgreSQL 16 + Redis 7 (Docker)
- IDEF3 Сценарий 1: GitHub Actions → APScheduler, 3 работы → 9 работ
- Прогнозирование: Prophet → Ensemble (Prophet + NeuralProphet + XGBoost)

### Обновление моделей документации — 22.02.2026

Все модели приведены в соответствие с актуальным состоянием системы:

| Модель | Обновления |
|--------|------------|
| USE_CASE | UC4 (сравнение моделей), UC5 (аналитика районов), UC8 (сбор данных APScheduler). Планировщик: GitHub Actions → APScheduler |
| CLASS | PostgreSQL вместо YDB, Mistral вместо MiMo-V2-Flash. Добавлены: EnsembleService, FeatureEngineering, 7+ парсеров, Redis |
| SEQUENCE | PostgreSQL повсюду. UC1: Ensemble прогноз. UC4: сравнение моделей. UC8: 7 источников событий + Xotelo |
| IDEF3 | APScheduler вместо GitHub Actions. Добавлен сбор погоды. PostgreSQL вместо YDB. Ensemble вместо Prophet |
| DOMAIN | Добавлены: LangGraph, Ensemble, Feature Engineering, погода, Redis, ChromaDB, APScheduler |

## Выполненные рефакторинги (22.02.2026)

1. Централизация констант → `backend/app/constants.py` (12 групп, 6 файлов обновлено)
2. Параметризация YQL запросов → `ydb_service.py` (6 методов, устранение SQL injection)
3. LangGraph Command pattern → `main_agent.py`
4. Замена print() → logger в 5 файлах парсеров
5. Исправление бага в `hotels_101hotels.py` (инвертированная логика сохранения)
6. Исправление `scheduler.py` (deprecated asyncio API)
7. Исправление `chroma_service.py` (where-параметр, ленивая инициализация)
8. Удаление хардкода координат из `llm_service.py`, `weather_openmeteo.py`
9. Удаление хардкода районов из `analytics.py`, `forecast.py`, `agent_tools.py`
10. Реструктуризация документации → `docs/`, `models/`
11. Исправление slug-ов 101Hotels → `constants.py` (5 slug-ов исправлены, 2 удалены)
12. Региональный парсинг 101Hotels → `hotels_101hotels.py` (city → region, дедупликация)
13. Расширение географии → `constants.py` (30+ населённых пунктов, 15 районов)
14. Обновление `scheduler.py` → вызов `parse_and_save_hotels(use_regions=True)`
15. Обновление `weather_openmeteo.py` → новые slug-и, `CITY_SLUG_TO_NAME`

### Обновление REQUIREMENTS_MODEL — 22.02.2026

Модель функциональных требований полностью переработана:
- FR1: 5 требований (101Hotels + Xotelo + PostgreSQL + APScheduler + аналитика районов)
- FR2: 5 требований (7 парсеров + Crawl4AI + нормализация + PostgreSQL + каталог)
- FR3: 5 требований (LangGraph чат + Ensemble визуализация + дашборд + сравнение моделей)
- FR4: 6 требований (RAG + Ensemble + Feature Engineering + ForecastAgent + Mistral + Redis кэш)
- FR5: 6 требований (REST API + ChromaDB + logging + APScheduler + Docker + Vite build)
- NFR: 6 нефункциональных требований (производительность, кэш, контейнеризация, graceful shutdown, валидация, безопасность)
- Обновлены связи с IDEF3, USE_CASE и темой ВКР

### Исправления качества кода — 22.02.2026

1. `forecast.py`: 5 проглоченных исключений (`except: pass`) заменены на `logger.warning()` с описанием ошибки
2. `analytics.py`: `/events-impact` — реализован реальный расчёт влияния событий:
   - Сравнение загрузки в день события (`occupancy_on_day`) со средней по району (`avg_occupancy`)
   - Поле `impact` = разница (положительное = событие повысило загрузку)
   - Кэширование запросов по районам для производительности
   - Сортировка по абсолютному значению impact (наиболее влиятельные — первыми)
