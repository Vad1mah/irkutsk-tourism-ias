# Контекст проекта: ИАС Туризм Прибайкалья

> Краткий справочник по архитектуре. Детальный план — в `PROJECT_FOCUS.md`
> Обновлено: 2026-03-25

---

## 1. Структура проекта

```
Diplom/
├── backend/                    # FastAPI сервер
│   ├── app/
│   │   ├── main.py            # Точка входа
│   │   ├── config.py          # Настройки (pydantic-settings)
│   │   ├── constants.py       # Централизованные константы
│   │   ├── scheduler.py       # APScheduler (ежедневный сбор)
│   │   ├── routers/           # 7 API роутеров (59 endpoints)
│   │   │   ├── hotels.py      # /api/hotels (3)
│   │   │   ├── events.py      # /api/events (6)
│   │   │   ├── forecast.py    # /api/forecast (9)
│   │   │   ├── query.py       # /api/query (5)
│   │   │   ├── analytics.py   # /api/analytics (17)
│   │   │   ├── parser.py      # /api/parser (13)
│   │   │   └── documents.py   # /api/documents (5)
│   │   ├── services/          # 16 сервисов
│   │   │   ├── data_service.py        # PostgreSQL (SQLAlchemy 2.0 + asyncpg)
│   │   │   ├── db_service.py          # ORM session factory
│   │   │   ├── chroma_service.py      # Vector store (RAG)
│   │   │   ├── llm_service.py         # 6 LLM провайдеров (Mistral основной)
│   │   │   ├── prophet_service.py     # Prophet модель
│   │   │   ├── neuralprophet_service.py # NeuralProphet
│   │   │   ├── xgboost_service.py     # XGBoost + LightGBM
│   │   │   ├── ensemble_service.py    # Weighted ensemble (async + кэш)
│   │   │   ├── feature_engineering.py # 25+ фичей для ML
│   │   │   ├── main_agent.py          # LangGraph Agent (5 tools)
│   │   │   ├── forecast_agent.py      # LangGraph Forecast Agent
│   │   │   ├── holidays_service.py    # Праздники РФ + школьные каникулы
│   │   │   ├── weather_service.py     # OpenMeteo API
│   │   │   ├── cache_service.py       # Redis (кэш + rate limiting)
│   │   │   ├── poi_service.py         # Достопримечательности (OSM)
│   │   │   └── protocols.py           # Интерфейсы сервисов
│   │   ├── models/
│   │   │   └── schemas.py             # Pydantic модели
│   │   ├── db/                        # SQLAlchemy ORM
│   │   ├── middleware/
│   │   │   └── rate_limit.py          # Redis sliding window
│   │   ├── dependencies/
│   │   │   └── auth.py                # API Key auth
│   │   └── parsers/                   # 17 файлов
│   │       ├── base.py                # Базовый класс парсера
│   │       ├── events_irk.py          # irk.ru/afisha
│   │       ├── events_culture38.py    # culture38.ru
│   │       ├── events_culture_rf.py   # Культура.РФ
│   │       ├── events_yandex.py       # Яндекс Афиша
│   │       ├── events_kassir.py       # Kassir.ru
│   │       ├── events_telegram.py     # Telegram каналы
│   │       ├── events_zeroevent.py    # zeroevent.ru
│   │       ├── events_major.py        # Крупные события (вручную)
│   │       ├── hotels_101hotels.py    # 101Hotels (региональный парсинг)
│   │       ├── hotels_xotelo.py       # Xotelo/TripAdvisor (cross-reference)
│   │       ├── weather_openmeteo.py   # Погода OpenMeteo
│   │       ├── ai_extractor.py        # LLM-извлечение данных
│   │       ├── anti_detection.py      # Anti-bot обход
│   │       └── health_monitor.py      # Мониторинг парсеров
│   └── requirements.txt
│
├── frontend/                   # React 18 + TypeScript + Vite 7
│   ├── src/
│   │   ├── pages/             # 10 страниц
│   │   │   ├── Home.tsx       # AI-чат (подсказки, retry, localStorage)
│   │   │   ├── Chat.tsx       # SSE streaming чат
│   │   │   ├── Situation.tsx  # Ensemble прогноз + CI + погода
│   │   │   ├── Seasonality.tsx# Сезонность, корреляции
│   │   │   ├── Events.tsx     # Каталог событий (поиск + фильтры)
│   │   │   ├── Map.tsx        # Аналитика регионов (Recharts)
│   │   │   ├── Forecast.tsx   # Ensemble + сравнение + feature importance
│   │   │   ├── HotelDetail.tsx# Карточка отеля
│   │   │   ├── Dashboard.tsx  # ECharts GeoMap + KPI
│   │   │   └── About.tsx      # О системе для комиссии
│   │   ├── components/        # UI: Button, Card, Badge, Input, ErrorState
│   │   └── api/client.ts      # API клиент (fetch)
│   └── package.json
│
├── docs/                      # Документация ВКР
│   ├── project/               # ТЗ, WBS, риски, ТЭО, статус
│   ├── research/              # Исследования (LLM, парсеры, модели)
│   ├── vkr/                   # Текст и структура ВКР
│   └── presentation/          # Презентации
│
├── models/                    # UML/IDEF модели
├── CLAUDE.md                  # Инструкции для AI-ассистента
└── .cursorrules               # Правила проекта для Cursor
```

---

## 2. Стек технологий

| Слой | Технология | Назначение |
|------|------------|------------|
| **Backend** | FastAPI, Pydantic v2 | REST API (59 endpoints) |
| **Frontend** | React 18 + TypeScript + Vite 7 | Web UI (10 страниц) |
| **База данных** | PostgreSQL 16 (Docker, SQLAlchemy 2.0 + asyncpg) | Хранение данных |
| **Vector Store** | ChromaDB | RAG для AI |
| **LLM** | **Mistral** Large (основной, 1B токенов/мес) | AI-ассистент + объяснения |
| **Embeddings** | GigaChat Embeddings | Векторизация |
| **Прогнозирование** | Prophet + NeuralProphet + XGBoost + LightGBM | Ensemble моделей |
| **AI Agents** | LangGraph (main_agent + forecast_agent) | 5 tools, MemorySaver |
| **Визуализация** | Recharts + ECharts | Графики + GeoMap |
| **Погода** | OpenMeteo API | Бесплатно |
| **Cache** | Redis 7 (с аутентификацией) | Кэширование + Rate Limiting |
| **Стили** | Tailwind CSS 4 | Тёмная/светлая тема |

---

## 3. Данные (PostgreSQL)

| Таблица | Записей | Описание |
|---------|---------|----------|
| `hotels` | 678 | Отели Иркутской области (+Xotelo: 1262) |
| `hotel_statistics` | 34,739 | История загрузки (~370 дней) |
| `events` | **227** | События из 8 источников |
| `query_history` | — | Запросы пользователей |
| `forecasts` | — | Результаты прогнозирования |

### События по источникам:

| Источник | Количество | Что включает |
|----------|------------|--------------|
| zeroevent.ru | ~50 | Концерты, балеты, спектакли |
| irk.ru | 39 | Новости, городские мероприятия |
| Telegram | 29 | 6 каналов региона |
| manual | 21 | Ice Fest, Ёрдынские игры, Звёзды на Байкале |
| Культура РФ | 20 | Федеральный портал |
| Яндекс Афиша | 19 | Афиша города |
| Kassir.ru | 17 | Билеты и события |
| culture38.ru | 6 | Культурные события |
| **ВСЕГО** | **227** | 8 источников |

---

## 4. API Endpoints (60 шт.)

### Прогнозирование (Forecast, 9 endpoints):
```
GET  /api/forecast                     # Prophet прогноз
GET  /api/forecast/neural              # NeuralProphet
GET  /api/forecast/xgboost             # XGBoost + LightGBM
GET  /api/forecast/ensemble            # Weighted ensemble
GET  /api/forecast/compare-all         # Сравнение всех моделей + метрики
GET  /api/forecast/explain             # LangGraph Agent с LLM объяснением
GET  /api/forecast/weather             # Прогноз погоды
GET  /api/forecast/best-dates          # Лучшие даты для поездки
GET  /api/forecast/feature-importance  # Важность фичей XGBoost
```

### Основные:
```
GET  /api/hotels                       # Список отелей (пагинация)
GET  /api/hotels/{id}                  # Детали отеля
GET  /api/hotels/{id}/statistics       # Статистика отеля
GET  /api/events                       # События (227 шт.)
POST /api/query                        # AI-ассистент (RAG)
POST /api/query/stream                 # AI-ассистент (SSE streaming)
```

### Аналитика (17 endpoints):
```
GET  /api/analytics/kpi                # KPI метрики
GET  /api/analytics/districts          # По районам
GET  /api/analytics/heatmap            # Тепловая карта
GET  /api/analytics/hotels-map         # Данные для GeoMap
GET  /api/analytics/price-history      # История цен
GET  /api/analytics/events-impact      # Влияние событий
GET  /api/analytics/recommendations    # Рекомендации
...и другие
```

---

## 5. Модели прогнозирования

### Метрики (тест 7 дней, Иркутский район):

| Модель | RMSE | MAE | Особенность |
|--------|------|-----|-------------|
| **Ensemble** | **2.67** | **2.39** | Weighted average, async + кэш |
| Prophet | 5.58 | 5.17 | Weather regressor, holidays |
| NeuralProphet | 5.92 | 4.77 | Lagged regressors, events |
| XGBoost | 6.11 | 5.44 | Quantile regression (CI) |

### Feature Engineering (25+ фичей):

```
Календарные (8): day_of_week, month, quarter, is_weekend...
Праздники (5):   is_holiday, days_to_holiday, is_long_weekend...
Лаги (7):        lag_1, lag_7, lag_14, lag_30, lag_90, diff_1, diff_7
Rolling (5):     rolling_mean_7, rolling_mean_30, rolling_std_7, min_7, max_7
Погода (4):      temperature, precipitation, temp_deviation, is_good_weather
События (3):     events_count, events_week, has_major_event
Тренд (2):       time_index, trend
```

### LangGraph Agent Workflow:

```
START → collect_data → run_models → analyze_factors → generate_explanation → END
         ↓               ↓              ↓                    ↓
      PostgreSQL,     Prophet,       Праздники,           Mistral Large
      Weather,        NeuralProphet, Сезон, События,      объясняет
      Events,         XGBoost        ML feature importance прогноз
      Holidays
```

---

## 6. Переменные окружения

```bash
# backend/.env
DB_BACKEND=postgresql
DATABASE_URL=postgresql://user:pass@localhost:5432/tourism

# Mistral AI — основная LLM (1B токенов/месяц бесплатно)
LLM_PROVIDER=mistral
MISTRAL_API_KEY=...

# Резервные провайдеры
GIGACHAT_CREDENTIALS=...
GROQ_API_KEY=...

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis_pass

# Security
API_KEY=your-secret-key  # Для parser endpoints
```

---

## 7. Запуск

### Docker (PostgreSQL + Redis):
```bash
docker compose up -d postgres redis
```

### Backend:
```bash
cd backend
venv\Scripts\activate  # Windows
uvicorn app.main:app --reload --port 8000
```

### Frontend:
```bash
cd frontend
npm run dev
```

### Проверка работы:
```bash
# Health check
curl http://localhost:8000/health

# Ensemble прогноз
curl "http://localhost:8000/api/forecast/ensemble?district=Иркутский&days_ahead=14"

# Сравнение моделей
curl "http://localhost:8000/api/forecast/compare-all?district=Иркутский&test_days=7"

# API документация
open http://localhost:8000/docs
```

---

> Детальный план работ — в `PROJECT_FOCUS.md`
