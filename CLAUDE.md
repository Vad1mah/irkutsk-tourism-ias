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
├── Home (AI-чат)             ├── routers/ (7 шт., 59 endpoints)
├── Chat (SSE streaming)      │   ├── forecast.py (9)        ├── 101hotels (отели)
├── Analytics (аналитика)     │   ├── events.py (6)          ├── OpenMeteo (погода)
├── Events (календарь)        │   ├── hotels.py (3)          ├── Парсеры событий (8 шт.)
├── Map (визуализация)        │   ├── analytics.py (17)      ├── Telegram каналы
├── Forecast (прогноз)        │   ├── query.py (5)           └── Xotelo/TripAdvisor
├── HotelDetail (карточка)    │   ├── parser.py (12)
└── About (о системе)         │   └── documents.py (5)
                              ├── services/ (16 шт.)
                              │   ├── ensemble_service.py (async + кэш)
                              │   ├── main_agent.py (LangGraph, 5 tools)
                              │   ├── forecast_agent.py (LangGraph)
                              │   ├── llm_service.py (6 LLM провайдеров)
                              │   ├── data_service.py (PostgreSQL)
                              │   ├── chroma_service.py (RAG)
                              │   ├── cache_service.py (Redis)
                              │   ├── prophet_service.py
                              │   ├── neuralprophet_service.py
                              │   ├── xgboost_service.py
                              │   ├── feature_engineering.py
                              │   ├── weather_service.py
                              │   ├── holidays_service.py
                              │   ├── poi_service.py
                              │   ├── db_service.py
                              │   └── protocols.py
                              ├── middleware/
                              │   └── rate_limit.py
                              ├── dependencies/
                              │   └── auth.py (API key)
                              ├── db/ (SQLAlchemy ORM, async session)
                              ├── models/schemas.py (Pydantic v2)
                              ├── constants.py (DEFAULT_DISTRICT, лимиты)
                              ├── executor.py (ThreadPoolExecutor для sync ML)
                              ├── scheduler.py (APScheduler: парсеры по расписанию)
                              └── parsers/ (~14 файлов)
                                  ├── base.py + ai_extractor + anti_detection + health_monitor
                                  ├── events_*.py (8 парсеров)
                                  ├── hotels_101hotels.py
                                  ├── hotels_xotelo.py
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> На старте `lifespan` поднимает PostgreSQL, Redis, Chroma, LLM, APScheduler и
> запускает фоновый прогрев ensemble-кэша (`_warmup_forecast_cache` в `main.py`).
> Если Redis недоступен — кэш отключается, но сервер продолжает работать.

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

| Endpoint | Описание |
|----------|----------|
| `POST /api/query` | AI-агент (RAG + tools) |
| `POST /api/query/stream` | AI-агент SSE streaming |
| `GET /api/forecast/ensemble` | Ensemble прогноз (лучшая модель) |
| `GET /api/forecast/compare-all` | Сравнение всех моделей |
| `GET /api/hotels` | Отели по району |
| `GET /api/events` | События региона |
| `GET /api/analytics/kpi` | KPI дашборд |
| `GET /api/analytics/hotels-map` | Данные для карты отелей |

## Технологический стек

- **Backend:** FastAPI, Pydantic v2, async/await
- **Database:** PostgreSQL 16 (SQLAlchemy 2.0 + asyncpg, Docker)
- **Cache:** Redis 7 (с аутентификацией)
- **Vector DB:** ChromaDB (RAG)
- **ML:** Prophet, NeuralProphet, XGBoost, LightGBM, Ensemble
- **LLM:** Mistral Large (основной), + GigaChat, Groq, DeepSeek, OpenRouter, Gemini (резервные)
- **AI Agents:** LangGraph (main_agent + forecast_agent, 5 tools, MemorySaver)
- **Frontend:** React 18, TypeScript 5.9, Tailwind CSS 4, Vite 7
- **Визуализация:** Recharts (графики) + ECharts (GeoMap на Map, scatter на Analytics)

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

# LLM
LLM_PROVIDER=mistral
MISTRAL_API_KEY=...

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

5 tools в main_agent.py:
- `search_hotels` — поиск отелей (ChromaDB + PostgreSQL)
- `search_events` — поиск событий
- `get_weather` — текущая/прогнозная погода (OpenMeteo)
- `forecast_occupancy` — прогноз загрузки (Ensemble)
- `get_statistics` — KPI и статистика

## Слои доступа к данным

Внутри `services/` сосуществуют два сервиса БД — это намеренно, не дубль:

| Сервис | Роль |
|--------|------|
| `db_service` | Низкоуровневый: пул соединений, `connect()`/`close()`, создание таблиц при старте |
| `data_service` | Доменный фасад: `get_occupancy_by_district`, `get_hotels`, `get_events` и т. п. — то, что вызывают роутеры и tools агента |

Все CPU-тяжёлые синхронные ML-вызовы (`prophet_service.forecast`, `xgboost_service.forecast`, `ensemble_service.forecast_ensemble`) ОБЯЗАНЫ идти через `app.executor.run_sync(...)`, иначе блокируют event loop. Не оборачивайте их в `asyncio.to_thread` точечно — ThreadPoolExecutor общий, чтобы не плодить пулы.

## Известные ограничения

**Пробел данных: июль-сентябрь 2025**

Данные за летний период не собирались. Влияние:
- R² моделей отрицательный на долгосрочных прогнозах
- Для демо использовать краткосрочные прогнозы (3-7 дней)
- Система архитектурно готова к работе с полными данными

## Стабильное состояние компонентов

Снимок «как устроено». Конкретный статус-таблица с датами живёт в `docs/project/PROJECT_STATUS.md` — туда же при изменениях.

| Компонент | Особенность реализации |
|-----------|------------------------|
| Backend | 7 роутеров, 59 endpoints, lifespan с прогревом ensemble-кэша |
| Frontend | 8 страниц, Recharts + ECharts, SSE для чата |
| AI-агент | LangGraph + MemorySaver (thread_id для контекста), 5 tools |
| Ensemble | Async поверх sync моделей через `executor.run_sync`, Redis-кэш |
| Тесты | 8 файлов в `backend/tests/` + `e2e_test.py` (9 сценариев) |
| Security | Rate limiting (Redis sliding window + in-memory fallback), API-key, CSP, non-root Docker |
| Docker | `postgres:16-alpine`, `redis:7-alpine`, healthchecks, profiles `full` для бекенда+фронтенда |
| Alembic | Каркас настроен (`backend/alembic/env.py`); ревизии добавлять при изменении схемы |

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
