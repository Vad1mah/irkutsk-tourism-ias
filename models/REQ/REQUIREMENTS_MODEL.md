# Диаграмма функциональных требований

## Назначение

Диаграмма требований отображает иерархическую структуру функциональных требований системы в соответствии с классификацией Карла Вигерса.

## Нотация

- Диаграмма требований **не является диаграммой UML**
- Связи между требованиями - **агрегация** (ромбик ◇)
- Нумерация автоматическая: FR1.1, FR1.2 и т.д.

## Структура требований

### FR1. Управление данными о средствах размещения

| Код | Требование |
|-----|------------|
| FR1.1 | Получение данных из 101Hotels API (региональный режим, ~200+ отелей) |
| FR1.2 | Cross-reference через Xotelo API (TripAdvisor рейтинги, типы размещения) |
| FR1.3 | Сохранение данных в PostgreSQL (SQLAlchemy ORM: Hotel, HotelStatistic) |
| FR1.4 | Обновление статистики загруженности по расписанию (APScheduler, каждые 2ч) |
| FR1.5 | Просмотр аналитики по районам (heatmap, radar chart, treemap) |

### FR2. Управление данными о туристических событиях

| Код | Требование |
|-----|------------|
| FR2.1 | Парсинг событий из 7 источников (irk.ru, culture38.ru, zeroevent.ru, kassir.ru, Telegram, yandex afisha, culture.ru) |
| FR2.2 | Crawl4AI для JS-heavy сайтов (kassir.ru, yandex afisha) с Jina Reader fallback |
| FR2.3 | Нормализация, валидация, дедупликация событий (BaseParser) |
| FR2.4 | Сохранение событий в PostgreSQL (Event ORM) |
| FR2.5 | Каталог событий с поиском по тексту и фильтрами по источнику |

### FR3. Взаимодействие с пользователем

| Код | Требование |
|-----|------------|
| FR3.1 | Ввод запроса на естественном языке (AI-чат с LangGraph агентом) |
| FR3.2 | Отображение ответа с Markdown рендерингом |
| FR3.3 | Визуализация Ensemble прогнозов с CI-bands (Recharts) |
| FR3.4 | Дашборд текущей ситуации (загруженность, KPI, прогноз, погода) |
| FR3.5 | Сравнение моделей прогнозирования (RMSE, MAE, R², feature importance) |

### FR4. Анализ данных и прогнозирование

| Код | Требование |
|-----|------------|
| FR4.1 | RAG-поиск через ChromaDB (GigaChatEmbeddings) |
| FR4.2 | Ensemble прогнозирование: Prophet + NeuralProphet + XGBoost → weighted average |
| FR4.3 | Feature Engineering (32 фичи: calendar, holidays, lags, rolling, weather, events) |
| FR4.4 | LangGraph ForecastAgent: объяснимые прогнозы (PydanticOutputParser → ForecastExplanation) |
| FR4.5 | Генерация ответа через Mistral AI (основной) с GigaChat/Groq fallback |
| FR4.6 | Redis кэширование прогнозов (TTL 30 минут) |

### FR5. Интеграция компонентов системы

| Код | Требование |
|-----|------------|
| FR5.1 | REST API (FastAPI, 7 роутеров, Swagger UI) |
| FR5.2 | ChromaDB для RAG (629 документов) |
| FR5.3 | Логирование через Python logging + HealthMonitor |
| FR5.4 | APScheduler (события 6ч, отели 2ч, погода 3ч, Telegram 1ч) |
| FR5.5 | Docker Compose (PostgreSQL 16 + Redis 7 + backend + frontend) |
| FR5.6 | Production build с code splitting (Vite 7, 4 чанка) |

### NFR. Нефункциональные требования

| Код | Требование |
|-----|------------|
| NFR1 | Время отклика API < 2с (кроме первого прогноза) |
| NFR2 | Redis кэширование тяжёлых вычислений (TTL 30 мин) |
| NFR3 | Контейнеризация всех компонентов (Docker Compose) |
| NFR4 | Graceful shutdown планировщика и БД-соединений |
| NFR5 | Валидация входных данных через Pydantic |
| NFR6 | CORS для фронтенда, .env для секретов |

## Связь с другими моделями

- FR1, FR2, FR5.4 → IDEF3 Сценарий 1 (фоновый сбор: APScheduler → 7 парсеров + 101Hotels + Xotelo + Open-Meteo → PostgreSQL)
- FR3, FR4 → IDEF3 Сценарий 2 (LangGraph агент → ChromaDB + Ensemble → Mistral → ответ)
- FR5 → интеграция: Docker Compose, REST API, ChromaDB, Redis
- FR1–FR5 → USE_CASE: UC1 (запрос), UC2 (события), UC3 (отели), UC4 (сравнение), UC5 (аналитика), UC6 (сезонность), UC7 (чат), UC8 (сбор данных)

## Соответствие техническому заданию

Требования соответствуют разделу 4 ТЗ (ГОСТ 34.602-89) и теме ВКР: "Интеллектуальная система прогнозирования заполняемости средств размещения на основе данных туристических агрегаторов и событийной активности в регионе".

