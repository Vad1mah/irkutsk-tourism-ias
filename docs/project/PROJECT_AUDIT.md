# АУДИТ ПРОЕКТА: Tourism Analytics System

**Дата:** 12.03.2026
**Этап:** Производственная практика (24.02 — 04.04.2026)
**Версия аудита:** 1.0

---

## СОДЕРЖАНИЕ

1. [Общая оценка](#1-общая-оценка)
2. [Структура проекта](#2-структура-проекта)
3. [Backend — код и архитектура](#3-backend)
4. [Frontend — код и архитектура](#4-frontend)
5. [Инфраструктура и DevOps](#5-инфраструктура)
6. [Документация](#6-документация)
7. [UML/IDEF модели](#7-модели)
8. [Тестирование](#8-тестирование)
9. [Безопасность](#9-безопасность)
10. [Критические проблемы](#10-критические-проблемы)
11. [Рекомендации по приоритетам](#11-рекомендации)

---

## 1. ОБЩАЯ ОЦЕНКА

| Область | Оценка | Комментарий |
|---------|--------|-------------|
| Архитектура backend | 8/10 | Грамотное разделение на слои, DI, async |
| Архитектура frontend | 7/10 | Lazy loading, React Query, но дублирование типов |
| Качество кода backend | 7/10 | Type hints, но устаревшие typing imports, смешанные форматы парсеров |
| Качество кода frontend | 8/10 | Strict TS, без `any`, но 3 type assertion |
| Документация | 5/10 | Много документов, но часть сильно устарела |
| Тестирование | 6/10 | Unit + E2E есть, но покрытие неполное, нет frontend тестов |
| DevOps | 7/10 | Docker Compose, Dockerfile, но нет Alembic миграций |
| Безопасность | 7/10 | Rate limiting, API key, но .env.example с DB_BACKEND=ydb |
| UML модели | 8/10 | 12 типов диаграмм, актуализированы, но нет IDEF0 |

**Итого: 7.0/10** — проект функционально завершён, но имеет ряд документационных и инфраструктурных недоработок.

---

## 2. СТРУКТУРА ПРОЕКТА

### 2.1 Файловая статистика

| Область | Файлов | Строк кода (примерно) |
|---------|--------|----------------------|
| Backend (app/) | ~52 | ~12 000 |
| Frontend (src/) | ~21 | ~5 000 |
| Документация (docs/) | ~39 | ~15 000 |
| UML модели (models/) | ~25 | ~5 000 |
| Тесты (backend/tests/) | ~12 | ~800 |
| Конфигурация | ~10 | ~200 |

### 2.2 Выявленные проблемы структуры

| # | Проблема | Критичность |
|---|----------|-------------|
| S1 | Нет корневого `README.md` | Средняя |
| S2 | Нет `backend/README.md` и `frontend/README.md` | Низкая |
| S3 | `.gitignore` исключает `.env.example` — это ошибка, пример должен коммититься | Высокая |
| S4 | `lightning_logs/` (199 папок) в backend — артефакты NeuralProphet, не в `.gitignore` | Средняя |
| S5 | Тестовые файлы в корне (`test_ui.py`, `test_pages.py`, `analyze_screenshots.py`) — нарушение структуры | Низкая |
| S6 | `101hotel_parser/` с venv включён в проект, но в `.gitignore` | Информационная |
| S7 | Файлы с кириллическими именами (`ИССЛЕДОВАНИЯ_МОДЕЛИ_ПРОГНОЗА.md`, `Проектные инициативы практикум.md`) — проблемы кодировки | Низкая |
| S8 | Нет директории `models/IDEF0/`, хотя упоминается в `.cursorrules` | Средняя |

---

## 3. BACKEND

### 3.1 Архитектура (оценка: 8/10)

**Сильные стороны:**
- Чистое разделение: routers → services → models → db
- Dependency Injection через `Annotated[Service, Depends()]`
- Lifespan context manager для управления жизненным циклом
- Фабрика `data_service` для переключения PostgreSQL/YDB
- 7 роутеров с чёткой ответственностью
- APScheduler для автоматического сбора данных

**Проблемы:**

| # | Файл | Проблема | Критичность |
|---|------|----------|-------------|
| B1 | `main.py` | `RateLimitMiddleware(redis_client=None)` — Redis подключается позже в lifespan, middleware получает клиент через `app.state` | Низкая |
| B2 | `main.py` | Глобальный `Exception` handler скрывает детали ошибки (всегда "Internal server error") | Средняя |
| B3 | `main.py` | `_executor.shutdown(wait=False)` — при незавершённых задачах потеря данных | Низкая |
| B4 | `config.py` | `db_backend` по умолчанию `"ydb"`, хотя реально используется PostgreSQL | Средняя |
| B5 | `ensemble_service.py` | Устаревшие `List`, `Dict`, `Optional` вместо `list`, `dict`, `| None` | Низкая |
| B6 | `dependencies/__init__.py` | `@lru_cache` для сервисов — не обновляется при смене конфигурации | Низкая |
| B7 | `scheduler.py` | `asyncio.ensure_future` — deprecated в Python 3.10+, использовать `create_task` | Низкая |

### 3.2 Роутеры

| Роутер | Endpoints | Замечания |
|--------|-----------|-----------|
| hotels | 2 (GET) | Кэширование, валидация дат |
| events | 6 (GET+POST+DELETE) | API key на мутациях, но нет валидации `date_from <= date_to` |
| query | 4 (POST+GET) | AI-агент, health, test |
| forecast | 7 (POST+GET) | ThreadPoolExecutor для CPU-тяжёлых задач, fallback на demo |
| documents | 5 (POST+GET+DELETE) | Chroma CRUD, индексация |
| parser | 10 (POST+GET) | API key, все парсеры, scheduler |
| analytics | 9 (GET) | KPI, корреляции, heatmap |

**Проблема B8:** В `events.py` нет валидации `date_from <= date_to` в `get_events`.

**Проблема B9:** В `parser.py` `_save_parsed_events` вызывает `insert_event` по одному — неэффективно при больших объёмах (нужен batch insert).

**Проблема B10:** В `forecast.py` при ошибках ML-моделей — «тихий» fallback на demo без явного предупреждения в ответе (только лог).

### 3.3 Парсеры

| Парсер | Тип | Возврат | Статус |
|--------|-----|---------|--------|
| events_irk | Функция | `dict` | Работает |
| events_culture38 | Функция | `dict` | Работает |
| events_zeroevent | Функция | `dict` | Работает |
| events_yandex | Класс | `ParsedEvent` | Требует Crawl4AI |
| events_kassir | Класс | `ParsedEvent` | Требует Crawl4AI |
| events_culture_rf | Функция | `ParsedEvent` | Работает |
| events_telegram | Функция | `ParsedEvent` | Работает |
| events_major | Функция | `ParsedEvent` | Ручной |
| hotels_101hotels | Класс | Сохранение в БД | Работает |
| hotels_xotelo | Класс | Сохранение в БД | Работает |
| weather_openmeteo | Класс | `dict` | Работает |

**Проблема B11:** Смешанный формат возврата — часть парсеров возвращает `dict`, часть `ParsedEvent`. Нет единого интерфейса.

**Проблема B12:** 2 парсера (kassir, yandex) требуют Crawl4AI (закомментирован в requirements.txt), что означает они не могут работать без дополнительной установки.

### 3.4 ML-сервисы

| Модель | Async | Кэш | Fallback | Тесты |
|--------|-------|------|----------|-------|
| Prophet | asyncio.to_thread | Нет | Demo | Через Ensemble |
| NeuralProphet | asyncio.to_thread | Нет | Demo | Через Ensemble |
| XGBoost | asyncio.to_thread | Нет | Demo | Через Ensemble |
| Ensemble | asyncio.gather | TTL 30мин | Partial | 12 тестов |

### 3.5 Зависимости (requirements.txt)

| Категория | Пакетов | Замечания |
|-----------|---------|-----------|
| Web (FastAPI, etc.) | 5 | Версии актуальны |
| Database | 4 | alembic есть в зависимостях, но не настроен (нет alembic.ini) |
| ML | 7 | Prophet, NeuralProphet, XGBoost, LightGBM |
| LLM | 7 | OpenAI, Gemini, Groq, LangChain |
| Parsing | 4 | aiohttp, httpx, BS4, telethon |
| Testing | 2 | pytest, pytest-asyncio |

**Проблема B13:** Alembic в зависимостях, но не инициализирован (нет `alembic.ini`, нет папки `migrations/`). Таблицы создаются через `create_tables()` в lifespan — это не production-ready подход.

**Проблема B14:** `lightgbm` в зависимостях, но не используется явно ни в одном сервисе (есть JSON-модель `forecast_lightgbm.json`, но нет `lightgbm_service.py`).

---

## 4. FRONTEND

### 4.1 Архитектура (оценка: 7/10)

**Сильные стороны:**
- Strict TypeScript (все strict-опции включены)
- Отсутствие `any` в коде
- Lazy loading всех страниц
- Code splitting (react-vendor, charts, query)
- React Query с настроенным кэшем
- Глобальный ErrorBoundary
- Адаптивный layout с мобильным меню

**Проблемы:**

| # | Файл | Проблема | Критичность |
|---|------|----------|-------------|
| F1 | `Map.tsx:312,330` | `levelColor = 'var(--destructive)'`, затем `hsl(${levelColor})` → `hsl(var(--destructive))` вместо `hsl(var(--destructive))` — двойная обёртка, цвет не отобразится | Высокая |
| F2 | `Situation.tsx:357` | `as unknown as string` — unsafe type assertion | Средняя |
| F3 | `Forecast.tsx:126,331` | `as Record<string, unknown>`, `as unknown as string` — unsafe assertions | Средняя |
| F4 | `api/client.ts` | Все типы в одном файле (~180 строк) — стоит выделить `types.ts` | Низкая |
| F5 | Нет отдельных хуков | `useQuery` вызывается inline в каждой странице — дублирование | Низкая |
| F6 | `Map.tsx` | Нет skeleton/loading состояния (единственная страница без него) | Средняя |
| F7 | `package.json` | Нет ESLint/Prettier — нет линтинга кода | Средняя |
| F8 | Нет `nginx.conf` для SPA | `nginx.conf` существует, но нужно проверить `try_files $uri /index.html` | Низкая |

### 4.2 Страницы

| Страница | Строк | Loading | Errors | Качество |
|----------|-------|---------|--------|----------|
| Home | ~300 | Spinner+Skeleton | Toast+Retry | Хорошо |
| Situation | ~720 | SituationSkeleton | Карточка | Хорошо |
| Seasonality | ~500 | SeasonalitySkeleton | Warning | Хорошо |
| Events | ~400 | EventsSkeleton | Empty state | Хорошо |
| Map | ~420 | **Нет** | Текст | **Нужен skeleton** |
| Forecast | ~550 | ForecastSkeleton | Карточка | Хорошо |

### 4.3 Компоненты

| Компонент | Проблемы |
|-----------|----------|
| Button | При `isLoading` без `leftIcon` — корректно показывает spinner |
| Card | `CardContent` — пустой `className` по умолчанию (безвредно) |
| Badge | OK |
| Input | OK |
| Layout | OK, мобильное меню |
| ErrorBoundary | Глобальный, нет per-page |
| HeatmapGrid | OK |

---

## 5. ИНФРАСТРУКТУРА

### 5.1 Docker (оценка: 7/10)

**docker-compose.yml:**
- PostgreSQL 16 + Redis 7 + Backend + Frontend
- Healthchecks для PostgreSQL и Redis
- Volumes для данных
- Profile "full" для backend/frontend

**Проблемы:**

| # | Проблема | Критичность |
|---|----------|-------------|
| I1 | Backend Dockerfile не содержит healthcheck | Средняя |
| I2 | Frontend nginx.conf — нужно убедиться что `try_files $uri /index.html` настроен для SPA | Средняя |
| I3 | Нет `.dockerignore` — в образ могут попасть venv, __pycache__, .git | Высокая |
| I4 | `docker-compose.yml` — пароль PostgreSQL захардкожен (`tourism_pass`) | Средняя |
| I5 | Нет production-ready конфигурации (нет Nginx reverse proxy для API) | Низкая |

### 5.2 Alembic

**Проблема I6:** Alembic установлен как зависимость, но не инициализирован. Управление схемой БД через `create_tables()` — недопустимо для production. Нужен `alembic init` + миграции.

### 5.3 .env

| Параметр | .env.example | Реальное | Проблема |
|----------|-------------|----------|----------|
| DB_BACKEND | ydb | postgresql | Вводит в заблуждение |
| API_KEY | your-secret-key-here | Настроен | OK |
| MISTRAL_API_KEY | Пустой | Настроен | OK |

### 5.4 .gitignore

**Проблема I7:** `.env.example` в `.gitignore` — пример конфигурации должен быть доступен в репозитории.

**Проблема I8:** `lightning_logs/` и тестовые артефакты (`test_report*.json`, `*_SUMMARY.md`, `*_REPORT.md` в корне) не в `.gitignore`.

---

## 6. ДОКУМЕНТАЦИЯ

### 6.1 Статус документов

| Документ | Актуален | Проблемы |
|----------|----------|----------|
| `PROJECT_STATUS.md` | Да (01.03.2026) | — |
| `PROJECT_CONTEXT.md` | Да | — |
| `PROJECT_FOCUS.md` | Да | — |
| `PG_MIGRATION_PLAN.md` | Да (завершён) | — |
| `PARSERS_AUDIT.md` | Частично (22.02.2026) | Расхождения статусов kassir/culture_rf |
| `DASHBOARD_RESEARCH.md` | Да | Решение: Tremor+ECharts, но используется Recharts |
| `LLM_PROVIDERS_RESEARCH.md` | Да | — |
| `MISTRAL_MODELS_RESEARCH.md` | Да | — |
| **VKR_THEORETICAL_FRAMEWORK.md** | **Нет** | **OpenRouter, YDB, нет Ensemble/NeuralProphet/XGBoost/LangGraph** |
| **VKR_PRACTICAL_DOCUMENTATION.md** | **Нет** | **YDB, OpenRouter, Prophet only, нет PostgreSQL/Mistral/Ensemble** |
| `VKR_DRAFT.md` | Да | Актуализирован |
| `VKR_PARAGRAPH.md` | Да | — |
| **DIPLOM_PRESENTATION.md** | **Нет** | **OpenRouter, 3 источника вместо 8** |
| **PREZENTACIYA_S_RECHYU.md** | **Нет** | **OpenRouter, moonshotai** |
| **TEO_POLNOE.md** | **Нет** | **YDB, нет PostgreSQL** |
| `RISKS_MANAGEMENT.md` | Частично | R10 (YDB) должен быть снят |
| `WBS_NETWORK.md` | Частично | GitHub Actions вместо APScheduler |
| **CLAUDE.md** | Частично | — |
| **.cursorrules** | Частично | `llm/` → Groq, но основной — Mistral |

### 6.2 Критические расхождения в документации

| # | Расхождение | Где | Должно быть |
|---|------------|-----|-------------|
| D1 | LLM: OpenRouter/Llama 3.2 | VKR_THEORETICAL_FRAMEWORK | Mistral (основной) |
| D2 | БД: YDB | VKR_THEORETICAL_FRAMEWORK, VKR_PRACTICAL, TEO | PostgreSQL 16 |
| D3 | Прогнозирование: только Prophet | VKR_PRACTICAL | Ensemble (Prophet+NeuralProphet+XGBoost) |
| D4 | Источники событий: 2-3 | VKR_PRACTICAL, PRESENTATION | 8 парсеров |
| D5 | Агент: без LangGraph | VKR_PRACTICAL, VKR_THEORETICAL | LangGraph + Command pattern |
| D6 | Визуализация: DataLens | VKR_PRACTICAL | Recharts (встроенные) |
| D7 | Планировщик: GitHub Actions | WBS_NETWORK | APScheduler |
| D8 | Dashboard: Tremor+ECharts | DASHBOARD_RESEARCH | Recharts (фактически) |
| D9 | `llm/` = Groq provider | .cursorrules | Groq — резервный, основной — Mistral через llm_service |
| D10 | 15 парсеров | .cursorrules | 16 файлов (10 парсеров + 6 утилит) |

### 6.3 Отсутствующие документы

| Документ | Необходимость |
|----------|---------------|
| `README.md` (корень) | Высокая — точка входа для разработчика |
| `backend/README.md` | Средняя |
| `frontend/README.md` | Средняя |
| API Reference (OpenAPI export) | Низкая — есть Swagger |
| Deployment Guide | Средняя — для production |
| `CHANGELOG.md` | Низкая |

---

## 7. UML/IDEF МОДЕЛИ

### 7.1 Наличие

| Тип | Папка | .md | .drawio | Статус |
|-----|-------|-----|---------|--------|
| Use Case | UC | 2 файла | 1 | Актуализирован |
| Class | CLASS | 1 | 1 | Актуализирован |
| Sequence | SEQUENCE | 1 | 1 | Актуализирован |
| Activity | ACTIVITY | 1 | 1 | Есть |
| Component | COMPONENT | — | 2 | Нет описания (.md) |
| Domain | DOMAIN | 1 | 1 | Актуализирован |
| Robustness | ROBUSTNESS | 1 | 1 | Есть |
| Requirements | REQ | 1 | 1 | Актуализирован |
| Business Process | BP | 1 | 1 | Есть |
| UI Model | UI | 1 | 1 | Есть |
| IDEF1 | IDEF1 | 1 | 1 | Есть |
| IDEF3 | IDEF3 | 1 | 1 | Актуализирован |
| **IDEF0** | **Нет** | **Нет** | **Нет** | **Отсутствует** |

### 7.2 Проблемы

| # | Проблема | Критичность |
|---|----------|-------------|
| M1 | Нет директории `models/IDEF0/` — IDEF0 указан в `.cursorrules`, ссылается в IDEF3_MODEL.md | Средняя |
| M2 | `models/COMPONENT/` — нет описания (`.md`), только `.drawio` | Низкая |

---

## 8. ТЕСТИРОВАНИЕ

### 8.1 Покрытие

| Область | Тестов | Покрытие |
|---------|--------|----------|
| Agent tools | 16 | Хорошо |
| Ensemble service | 12 | Хорошо |
| Security | 3+ | Средне |
| Forecast helpers | 3+ | Средне |
| E2E (API) | 9 | Хорошо |
| **Frontend** | **0** | **Нет тестов** |
| **Парсеры** | **0** | **Нет юнит-тестов** |
| **LLM service** | **0** | **Нет тестов** |
| **Data service** | **0** | **Нет тестов** |

### 8.2 Проблемы

| # | Проблема | Критичность |
|---|----------|-------------|
| T1 | Нет тестов для frontend (Vitest не установлен) | Средняя |
| T2 | Нет юнит-тестов для парсеров | Средняя |
| T3 | Нет тестов для data_service (PostgreSQL queries) | Средняя |
| T4 | `conftest.py` использует deprecated `event_loop` fixture | Низкая |
| T5 | `conftest.py` — silent `except: pass` при подключении к БД/Redis | Низкая |
| T6 | Тестовые артефакты в корне проекта (`test_report.json`, `UI_TEST_REPORT.md` и т.д.) | Низкая |
| T7 | Нет CI/CD pipeline (GitHub Actions / GitLab CI) | Средняя |

---

## 9. БЕЗОПАСНОСТЬ

### 9.1 Реализованные меры

| Мера | Статус | Детали |
|------|--------|--------|
| Rate Limiting | Реализовано | Redis sliding window + in-memory fallback |
| API Key Auth | Реализовано | X-API-Key для parser/admin endpoints |
| SQL Injection | Исправлено | Экранирование %, _ в LIKE |
| CORS | Настроено | Ограничены origins, methods, headers |
| Input Validation | Частично | Pydantic, но не все параметры |
| Secrets | SecretStr | Pydantic SecretStr для ключей |

### 9.2 Проблемы

| # | Проблема | Критичность |
|---|----------|-------------|
| SEC1 | Без `API_KEY` в `.env` все protected endpoints открыты (dev mode) — нет warning при production | Высокая |
| SEC2 | `docker-compose.yml` — пароль PostgreSQL в plain text | Средняя |
| SEC3 | `.env.example` в `.gitignore` — при клонировании репозитория не будет примера конфигурации | Высокая |
| SEC4 | Нет HTTPS/TLS конфигурации для production | Информационная |
| SEC5 | `global_exception_handler` скрывает все ошибки — затрудняет диагностику | Средняя |

---

## 10. КРИТИЧЕСКИЕ ПРОБЛЕМЫ (требуют исправления)

### Приоритет 1 — Исправить немедленно

| # | Проблема | Файл | Решение |
|---|----------|------|---------|
| **CRIT-1** | `.env.example` в `.gitignore` | `.gitignore` | Удалить `.env.example` из .gitignore |
| **CRIT-2** | `DB_BACKEND=ydb` в `.env.example` | `backend/.env.example` | Заменить на `postgresql` |
| **CRIT-3** | `levelColor` баг в Map | `frontend/src/pages/Map.tsx:312,330` | Убрать `hsl()` обёртку или использовать HSL-значения напрямую |

### Приоритет 2 — Исправить до защиты ВКР

| # | Проблема | Решение |
|---|----------|---------|
| **HIGH-1** | VKR_THEORETICAL_FRAMEWORK устарел | Обновить: Mistral, PostgreSQL, Ensemble, LangGraph |
| **HIGH-2** | VKR_PRACTICAL_DOCUMENTATION устарел | Обновить: PostgreSQL, Mistral, Ensemble, 8 парсеров |
| **HIGH-3** | Презентации устарели | Обновить DIPLOM_PRESENTATION, PREZENTACIYA_S_RECHYU |
| **HIGH-4** | TEO_POLNOE — YDB вместо PostgreSQL | Обновить раздел БД |
| **HIGH-5** | Нет IDEF0 модели | Создать `models/IDEF0/` |
| **HIGH-6** | Нет `.dockerignore` | Создать для backend и frontend |
| **HIGH-7** | Нет Alembic миграций | Инициализировать Alembic, создать начальную миграцию |

### Приоритет 3 — Улучшения

| # | Проблема | Решение |
|---|----------|---------|
| MED-1 | Смешанный формат парсеров (dict vs ParsedEvent) | Единый интерфейс |
| MED-2 | Нет batch insert для событий | Реализовать `insert_events_batch` |
| MED-3 | Нет skeleton в Map.tsx | Добавить MapSkeleton |
| MED-4 | Нет ESLint/Prettier во frontend | Настроить |
| MED-5 | Устаревшие typing imports в ensemble_service | `list`, `dict`, `| None` |
| MED-6 | `lightning_logs/` не в .gitignore | Добавить |
| MED-7 | Тестовые артефакты в корне | Перенести или добавить в .gitignore |
| MED-8 | Нет валидации date_from <= date_to в events | Добавить |
| MED-9 | DASHBOARD_RESEARCH: Tremor+ECharts, факт: Recharts | Обновить документ |

---

## 11. РЕКОМЕНДАЦИИ ПО ПРИОРИТЕТАМ

### Этап 1: Критические исправления (1-2 часа)

1. Исправить `.gitignore` (убрать `.env.example`)
2. Исправить `.env.example` (`DB_BACKEND=postgresql`)
3. Исправить `levelColor` баг в `Map.tsx`
4. Создать `.dockerignore` для backend и frontend
5. Добавить `lightning_logs/` в `.gitignore`

### Этап 2: Документация ВКР (4-8 часов)

1. Обновить `VKR_THEORETICAL_FRAMEWORK.md` — стек, LLM, БД, ML
2. Обновить `VKR_PRACTICAL_DOCUMENTATION.md` — все 12 разделов
3. Обновить `TEO_POLNOE.md` — PostgreSQL
4. Обновить презентации
5. Создать `models/IDEF0/`
6. Синхронизировать `.cursorrules` и `CLAUDE.md`

### Этап 3: Инфраструктура (2-4 часа)

1. Инициализировать Alembic
2. Добавить healthcheck в backend Dockerfile
3. Проверить nginx.conf для SPA
4. Настроить ESLint + Prettier для frontend

### Этап 4: Качество кода (2-4 часа)

1. Унифицировать формат парсеров (ParsedEvent)
2. Добавить batch insert для событий
3. Добавить skeleton в Map.tsx
4. Исправить type assertions во frontend
5. Обновить typing imports в ensemble_service
6. Добавить валидацию date_from <= date_to

---

## ПРИЛОЖЕНИЕ: Карта файлов проекта

```
tourism-analytics/
├── backend/
│   ├── app/
│   │   ├── config.py              # Pydantic Settings
│   │   ├── constants.py           # Константы (районы, slug-и)
│   │   ├── main.py                # FastAPI app + lifespan
│   │   ├── scheduler.py           # APScheduler
│   │   ├── db/
│   │   │   ├── session.py         # SQLAlchemy async session
│   │   │   └── models.py          # ORM модели (5 таблиц)
│   │   ├── dependencies/
│   │   │   ├── __init__.py        # DI: 10 сервисных зависимостей
│   │   │   └── auth.py            # API key verification
│   │   ├── middleware/
│   │   │   └── rate_limit.py      # Redis sliding window
│   │   ├── models/
│   │   │   └── schemas.py         # Pydantic schemas (~20 моделей)
│   │   ├── routers/               # 7 роутеров, ~43 endpoints
│   │   ├── services/              # 16 сервисов
│   │   ├── parsers/               # 16 файлов (10 парсеров + утилиты)
│   │   └── llm/
│   │       └── groq_provider.py   # Groq HTTP client
│   ├── tests/                     # 10 тестовых файлов
│   ├── models/                    # JSON-модели прогнозов
│   ├── requirements.txt           # 35 зависимостей
│   ├── Dockerfile                 # Python 3.11-slim
│   └── .env.example               # 30+ переменных
├── frontend/
│   ├── src/
│   │   ├── pages/                 # 6 страниц
│   │   ├── components/            # 8 компонентов
│   │   ├── api/client.ts          # Типизированный API (17 методов)
│   │   ├── lib/cn.ts              # clsx + tailwind-merge
│   │   └── utils/weather.ts       # Weather emoji helper
│   ├── package.json               # 12 dependencies + 7 devDependencies
│   ├── vite.config.ts             # Proxy + code splitting
│   ├── Dockerfile                 # Multi-stage Node → Nginx
│   └── nginx.conf                 # SPA routing
├── docs/
│   ├── research/                  # 11 исследований
│   ├── vkr/                       # 7 документов ВКР
│   ├── project/                   # 14 файлов управления
│   ├── presentation/              # 5 презентаций
│   └── assignments/               # 4 задания
├── models/                        # 12 типов UML/IDEF (нет IDEF0)
├── docker-compose.yml             # PostgreSQL + Redis + Apps
├── CLAUDE.md                      # AI assistant guide
└── .cursorrules                   # Cursor IDE rules
```
