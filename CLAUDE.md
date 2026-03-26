# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

ИАС мониторинга и прогнозирования туристической активности Иркутской области (ВКР).

### Архитектура

```
Frontend (React + Vite)        Backend (FastAPI)              Data Sources
├── Home (AI-чат)             ├── routers/ (7 шт., 59 endpoints)
├── Chat (SSE streaming)      │   ├── forecast.py (9)        ├── 101hotels (отели)
├── Analytics (аналитика)     │   ├── events.py (6)          ├── OpenMeteo (погода)
├── Events (календарь)        │   ├── hotels.py (3)          ├── Парсеры событий (8 шт.)
├── Events (календарь)        │   ├── analytics.py (17)      ├── Telegram каналы
├── Map (визуализация)        │   ├── query.py (5)           └── Xotelo/TripAdvisor
├── Forecast (прогноз)        │   ├── parser.py (13)
├── HotelDetail (карточка)    │   └── documents.py (5)
├── Map (визуализация)        ├── services/ (16 шт.)
└── About (о системе)        │   ├── ensemble_service.py (async + кэш)
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
                              └── parsers/ (17 файлов)
                                  ├── events_*.py (8 парсеров)
                                  ├── hotels_101hotels.py
                                  ├── hotels_xotelo.py
                                  └── weather_openmeteo.py
```

## Команды

### Backend
```bash
cd backend
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env  # Настроить переменные
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

# Unit тесты (60 тестов в 5 файлах)
cd backend && .\\venv\\Scripts\\activate && pytest tests/ -v

# E2E тесты (9 сценариев)
cd backend && python tests/e2e_test.py

# API docs
open http://localhost:8000/docs
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
- **Frontend:** React 18, TypeScript, Tailwind CSS 4, Vite 7
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

Feature engineering: 25+ признаков (лаги, rolling stats, праздники, погода, события).

## AI-агент (LangGraph)

5 tools в main_agent.py:
- `search_hotels` — поиск отелей (ChromaDB + PostgreSQL)
- `search_events` — поиск событий
- `get_weather` — текущая/прогнозная погода (OpenMeteo)
- `forecast_occupancy` — прогноз загрузки (Ensemble)
- `get_statistics` — KPI и статистика

## Известные ограничения

**Пробел данных: июль-сентябрь 2025**

Данные за летний период не собирались. Влияние:
- R² моделей отрицательный на долгосрочных прогнозах
- Для демо использовать краткосрочные прогнозы (3-7 дней)
- Система архитектурно готова к работе с полными данными

## Статус (25.03.2026)

| Компонент | Статус |
|-----------|--------|
| Backend | ✅ Работает (59 endpoints, 7 роутеров) |
| Frontend | ✅ 8 страниц (Home, Chat, Analytics, Events, Map, Forecast, HotelDetail, About) |
| AI-агент | ✅ 5 tools, MemorySaver, SSE streaming |
| Ensemble | ✅ ~2s (async + кэш) |
| Unit тесты | ✅ 60 тестов, 5 файлов |
| E2E тесты | ✅ 9/9 passed |
| Security | ✅ Rate limiting + API key auth + CSP + non-root Docker |
| Docker | ✅ PostgreSQL 16 + Redis 7 (secrets, healthchecks) |
| Глобальный аудит | ✅ 145 фиксов (25.03.2026) |

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
