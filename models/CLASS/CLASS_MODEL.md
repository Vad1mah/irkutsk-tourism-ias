# Диаграммы классов (Class Diagram)

## Назначение

Диаграмма классов представляет статическую структуру системы - классы, их атрибуты, операции и отношения между ними.

## Стереотипы классов

| Стереотип | Цвет | Описание | Источник |
|-----------|------|----------|----------|
| «control» | Синий | Контроллеры, бизнес-логика | Robustness (Control) |
| «boundary» | Оранжевый | Граничные классы (UI, внешние API) | Robustness (Boundary) |
| «entity» | Зелёный | Сущности предметной области | Domain Model, Robustness (Entity) |
| «enumeration» | Красный | Перечисления | IDEF1X |

## Диаграммы по бизнес-процессам

### БП1. Фоновый сбор данных

**Контроллеры («control»):**
- DataCollectorScheduler - APScheduler, запуск сбора по расписанию (события 6ч, отели 2ч, погода 3ч, Telegram 1ч)
- BaseParser - базовый класс парсеров (retry, rate limiting, дедупликация)
- AIEventExtractor - AI extraction через Crawl4AI + Jina fallback
- HealthMonitor - мониторинг состояния парсеров

**Граничные («boundary»):**
- API101Hotels - 101Hotels.com JSON API (региональный режим)
- XoteloAPI - Xotelo/TripAdvisor (рейтинги, типы размещения)
- OpenMeteoAPI - Open-Meteo (погода/прогноз)
- IrkParser, Culture38Parser, ZeroEventParser - HTML парсеры событий
- KassirParser, YandexAfishaParser, CultureRFParser - Crawl4AI парсеры
- TelegramParser - Telegram каналы
- GigaChatEmbeddings - создание эмбеддингов

**Сущности («entity»):**
- Event (Событие) - данные о мероприятии (SQLAlchemy ORM)
- Hotel (СредствоРазмещения) - данные об отеле (SQLAlchemy ORM)
- HotelStatistic (СтатистикаЗагруженности) - исторические данные (SQLAlchemy ORM)
- ВекторныйИндекс - эмбеддинг для RAG
- PostgreSQLRepository, ChromaRepository - хранилища

### БП2. Обработка запроса пользователя

**Контроллеры («control»):**
- FastAPIController - 7 роутеров (analytics, documents, events, forecast, hotels, parser, query) + 2 root-маршрута (`/`, `/health`); всего 8 групп маршрутов и 65 endpoints
- MainAgent (LangGraph) - StateGraph, Command pattern, 12 инструментов (6 базовых + 6 RMS-расширений), MemorySaver, fallback chain Groq → DeepSeek → Mistral
- ForecastAgent (LangGraph) - пайплайн: collect_data → run_models → analyze_factors → generate_explanation
- EnsembleService - ансамблевое прогнозирование (Prophet + NeuralProphet + XGBoost) с inverse-RMSE весами
- FeatureEngineering - 38 ML-фич (календарные, праздничные, лаговые, диффы, скользящие, погодные, событийные, трендовые, ценовые)
- MethodologyService - seasonal-corrected baseline для impact событий (NFR7 методологическая прозрачность)
- ParserHealthService - Redis-стороживание состояния парсеров (TTL 7 дней)

**Граничные («boundary»):**
- Home (Командный центр) - KPI, прогноз 14 дней, ближайшие события с impact, RMS-метрики
- Analytics (Аналитика рынка) - heatmap, Pickup/Pace, RevPAR-таблица с drill-down, экспорт CSV
- Forecast (Прогноз спроса) - Ensemble прогноз с CI-bands, сравнение моделей, feature importance
- Events (Каталог событий) - поиск + фильтры по источнику и типу, also_at для дедуплицированных событий
- Map (Регионы и карта) - Yandex Maps с маркерами объектов, heatmap, radar, treemap, GeoJSON-контур области
- HotelDetail (Карточка объекта) - профиль отеля с динамикой загрузки, цен и сегментным benchmark
- Chat (AI-помощник) - SSE-стриминг ответов LangGraph агента, MemorySaver
- About (О системе) - описание архитектуры и B2B-функционала
- LLMService - мульти-провайдер (Groq primary для tool-calling в main_agent; Mistral primary для не-tool вызовов в llm_service; DeepSeek/GigaChat/OpenRouter/Gemini в fallback)

**Сущности («entity»):**
- QueryHistory (Запрос) - пользовательский вопрос (SQLAlchemy ORM)
- ForecastExplanation - структурированный ответ LLM (Pydantic)
- Forecast - результат прогнозирования (SQLAlchemy ORM)
- ChromaDocument - RAG-документ (векторная БД)

### БП3. Администрирование системы

**Контроллеры («control»):**
- АдминКонтроллер - управление источниками и логами
- МониторСервисов - проверка доступности

**Граничные («boundary»):**
- ПанельАдмина - главная панель
- ФормаРедактирования - редактирование источников
- СтраницаЛогов - просмотр логов

**Сущности («entity»):**
- ИсточникДанных - конфигурация источника
- ЛогСистемы - записи логов

**Перечисления («enumeration»):**
- ТипИсточника: API, PARSER, DATABASE, CRAWL4AI
- LogLevel: DEBUG, INFO, WARNING, ERROR
- ForecastModel: PROPHET, NEURALPROPHET, XGBOOST, ENSEMBLE
- DBBackend: POSTGRESQL

## Типы отношений

| Тип | Обозначение | Пример |
|-----|-------------|--------|
| Ассоциация | Сплошная линия | Запрос — Ответ |
| Агрегация | Пустой ромб ◇ | История ◇— Запрос |
| Зависимость | Пунктирная линия | ИсточникДанных --→ ТипИсточника |

## Множественности

| Обозначение | Значение |
|-------------|----------|
| 1 | Ровно один |
| * | Ноль или много |
| 1..* | Один или много |
| 0..1 | Ноль или один |

## Соответствие другим моделям

| Диаграмма классов | Robustness | Sequence | Domain Model |
|-------------------|------------|----------|--------------|
| «control» классы | Control объекты | Lifelines сервисов | - |
| «boundary» классы | Boundary объекты | Lifelines UI | UI Model |
| «entity» классы | Entity объекты | - | Объекты |

## Файлы

- `class_diagrams.drawio` - 3 диаграммы (по одной на каждый бизнес-процесс)
