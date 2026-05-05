# Диаграмма функциональных требований

## Назначение

Диаграмма требований отображает иерархическую структуру функциональных требований ИАС мониторинга и прогнозирования туристической активности Иркутской области в соответствии с классификацией Карла Вигерса. Требования сформулированы под B2B-концепцию системы (отельеры, региональная администрация, исследователи).

## Нотация

- Диаграмма требований **не является диаграммой UML**
- Связи между требованиями - **агрегация** (ромбик ◇)
- Нумерация автоматическая: FR1.1, FR1.2 и т.д.

## Структура требований

### FR1. Управление данными о средствах размещения

| Код | Требование |
|-----|------------|
| FR1.1 | Получение данных из 101Hotels API (региональный режим, ~370+ гостиниц + 179 санаториев) |
| FR1.2 | Cross-reference через Xotelo API (TripAdvisor рейтинги, типы размещения) |
| FR1.3 | Сохранение данных в PostgreSQL (SQLAlchemy ORM: Hotel, HotelStatistic) |
| FR1.4 | Обновление статистики загруженности по расписанию (APScheduler, каждые 2ч) |
| FR1.5 | Региональная аналитика: heatmap, рейтинг RevPAR, treemap количества объектов по 15 районам |

### FR2. Управление данными о событиях, влияющих на спрос

| Код | Требование |
|-----|------------|
| FR2.1 | Парсинг событий из 8 источников (irk.ru, culture38.ru, zeroevent.ru, kassir.ru, Telegram, yandex afisha, culture.ru, sluda-events) |
| FR2.2 | Crawl4AI для JS-heavy сайтов (kassir.ru, yandex afisha) с Jina Reader fallback |
| FR2.3 | Нормализация, валидация, дедупликация событий (BaseParser + AIExtractor) |
| FR2.4 | Сохранение событий в PostgreSQL (Event ORM) |
| FR2.5 | Каталог событий с поиском по тексту, фильтрами по типу/источнику и сортировкой по impact |

### FR3. Взаимодействие с B2B-пользователем

| Код | Требование |
|-----|------------|
| FR3.1 | Ввод параметрических и текстовых запросов через AI-чат (LangGraph агент с B2B system prompt) |
| FR3.2 | Отображение ответа с Markdown рендерингом и табличным выводом |
| FR3.3 | Визуализация Ensemble прогнозов с CI-bands (Recharts) |
| FR3.4 | Командный центр: KPI текущей загрузки, прогноз 14 дней, ближайшие события с impact, RevPAR/ADR/Pickup |
| FR3.5 | Сравнение моделей прогнозирования (RMSE, MAE, R², feature importance) |
| FR3.6 | Расчёт RMS-метрик: RevPAR, ADR, Occupancy %, Pickup, Pace через эндпоинты `/api/analytics/revenue-summary` и `/api/analytics/pickup-pace`. При отсутствии revenue — прокси-оценка `min_price * occupancy_share` с явной пометкой. **Расширено:** все метрики помечены как proxy в API ответах и UI (через MethodologyTooltip) |
| FR3.7 | Тепловая карта загрузки по дням недели и месяцам (`/api/analytics/weekday-heatmap`) — матрица 7×12 для объекта или района. **Расширено:** gap-aware рендер — ячейки с `samples < 5` рендерятся диагональной штриховкой; gap-периоды (e.g. июль–сентябрь 2025) отмечены отдельным цветом |
| FR3.8 | **[NEW]** Сегментный benchmark. Система предоставляет анонимный сегментный benchmark (район × размерная категория mini ≤ 15 / mid 16–50 / large 51+). Реализация: `GET /api/hotels/{id}/segment-benchmark`, frontend HotelDetail page |
| FR3.9 | **[NEW]** Daily proxy-pickup из дельт snapshot'ов. Реализация: `GET /api/analytics/booking-pace` — считает разницу occupancy между текущим snapshot'ом и snapshot'ом `lookback_days` назад |

### FR4. Анализ данных и прогнозирование

| Код | Требование |
|-----|------------|
| FR4.1 | RAG-поиск через ChromaDB (GigaChat Embeddings, 629+ документов) |
| FR4.2 | Ensemble прогнозирование: Prophet + NeuralProphet + XGBoost → weighted average через `executor.run_sync` |
| FR4.3 | Feature Engineering (38 фич: calendar, holidays, lags, rolling, weather, events, trend, prices) |
| FR4.4 | LangGraph ForecastAgent: объяснимые прогнозы (PydanticOutputParser → ForecastExplanation) |
| FR4.5 | Генерация ответа через Mistral AI (основной) с GigaChat / Groq / DeepSeek / OpenRouter / Gemini fallback |
| FR4.6 | Redis кэширование прогнозов (TTL 30 минут) |
| FR4.7 | Расчёт impact события на загрузку. **Уточнено:** метод `seasonal_corrected` с baseline по похожим дням недели в окне ±3 нед., исключая другие event-дни и gap-периоды. Наивный метод: Δ Occupancy = Occupancy(день события) − среднее Occupancy(±7 дней). Реализован в `MethodologyService`. Эндпоинт `GET /api/analytics/events-impact?method=seasonal_corrected&window_weeks=3` |

### FR5. Интеграция компонентов системы

| Код | Требование |
|-----|------------|
| FR5.1 | REST API (FastAPI, 7 роутеров, 59 endpoints, Swagger UI) |
| FR5.2 | ChromaDB для RAG (629 документов) |
| FR5.3 | Логирование через Python logging + HealthMonitor |
| FR5.4 | APScheduler (события 6ч, отели 2ч, погода 3ч, Telegram 1ч) |
| FR5.5 | Docker Compose (PostgreSQL 16 + Redis 7 + backend + frontend) |
| FR5.6 | Production build с code splitting (Vite 7, 4 чанка) |

### FR6. Экспорт данных для исследовательских задач

| Код | Требование |
|-----|------------|
| FR6.1 | CSV-экспорт через `/api/analytics/export?type=occupancy\|events\|hotels` с параметрами `date_from`, `date_to`, `district` |
| FR6.2 | Контроль размера выгрузки (по умолчанию ≤ 100 000 строк, при превышении — 413 Payload Too Large) |
| FR6.3 | Документация методологии расчёта метрик (приложением к выгрузке UC4). **Расширено:** каждая выгрузка содержит ссылку на `MethodologyRecord` (метод, формула, версия) через `MethodologyService` |
| FR6.4 | Воспроизводимость: фиксация версии моделей и весов Ensemble в выгрузке методологии |

### NFR. Нефункциональные требования

| Код | Требование |
|-----|------------|
| NFR7 | **[NEW]** Методологическая прозрачность — каждая выводимая метрика имеет видимое пояснение источника, формулы и ограничений (через `MethodologyTooltip` компонент во фронте + блок «Методология» на About странице + поле `method` в API ответах) |
| NFR1 | Время отклика API < 2с (кроме первого прогноза) |
| NFR2 | Redis кэширование тяжёлых вычислений (TTL 30 мин) |
| NFR3 | Контейнеризация всех компонентов (Docker Compose) |
| NFR4 | Graceful shutdown планировщика и БД-соединений |
| NFR5 | Валидация входных данных через Pydantic v2 |
| NFR6 | CORS для фронтенда, .env для секретов, защита парсер-эндпоинтов через `X-API-Key` |

## Связь с другими моделями

- FR1, FR2, FR5.4 → IDEF3 Сценарий 1 (фоновый сбор: APScheduler → 8 парсеров событий + 101Hotels + Xotelo + Open-Meteo → PostgreSQL)
- FR3, FR4 → IDEF3 Сценарий 2 (LangGraph агент → ChromaDB + Ensemble → Mistral → ответ)
- FR3.6, FR3.7, FR4.7 → новые B2B-аналитические эндпоинты (Analytics router)
- FR3.8 → USE_CASE: UC12 (сегментный benchmark), HotelDetail page, `GET /api/hotels/{id}/segment-benchmark`
- FR3.9 → USE_CASE: UC10, `GET /api/analytics/booking-pace`, BookingSnapshot domain entity
- FR6 → IDEF3 Сценарий 3 (Экспорт по запросу исследователя)
- FR5 → интеграция: Docker Compose, REST API, ChromaDB, Redis
- NFR7 → MethodologyService + MethodologyRecord domain entity + MethodologyTooltip компонент
- FR1–FR6 → USE_CASE: UC1 (прогноз), UC2 (карточка объекта), UC3 (события + impact), UC4 (сравнение моделей + методология), UC5 (региональная аналитика), UC6 (источники), UC7 (мониторинг), UC8 (сбор данных), UC9 (экспорт), UC10 (RMS-метрики), UC11 (corrected impact), UC12 (сегментный benchmark)

## Соответствие техническому заданию

Требования соответствуют разделу 4 ТЗ (ГОСТ 34.602-89) и теме ВКР: «Интеллектуальная система прогнозирования заполняемости средств размещения на основе данных туристических агрегаторов и событийной активности в регионе» в B2B-позиционировании (отельеры, региональная администрация, исследователи).
