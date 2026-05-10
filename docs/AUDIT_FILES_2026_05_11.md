# Пофайловый аудит проекта — 2026-05-11

> Глубокий пофайловый анализ репозитория ИАС туризма (FastAPI + React) накануне защиты ВКР (12.05.2026). Цель — понять, какие файлы нужны системе/защите, какие являются легаси/мусором, и подготовить безопасный план зачистки **после защиты**.
>
> **Принцип**: ничего не удалять до защиты. Отчёт — рабочий артефакт + план действий по уровням риска.

---

## Содержание

1. [Executive summary](#executive-summary)
2. [Backend code](#backend-code)
3. [Frontend code](#frontend-code)
4. [Документация (`docs/`)](#документация-docs)
5. [Корневой уровень](#корневой-уровень)
6. [Кейс `figure_4..9.png`](#кейс-figure_49png)
7. [Пробелы в `.gitignore`](#пробелы-в-gitignore)
8. [Action plan — 4 bucket'а по риску](#action-plan)

---

## Executive summary

| Категория | Всего | KEEP | OBSOLETE | TRASH | NEEDS-REVIEW |
|---|---:|---:|---:|---:|---:|
| Backend Python (`app/`) | 85 | 85 | 0 | 0 | 0 |
| Backend scripts | 13 (tracked) | 3 | 8 | 2 | 0 |
| Backend tests | 36 | 34 | 0 | 2 | 0 |
| Frontend (`src/`) | 36 | 30 | 6 | 0 | 0 |
| Docs `vkr/` | ~25 | ~22 (VKR-CRITICAL) | 2 | 1 (cursovaya_backup) | 0 |
| Docs `project/` | 12 | 9 | 3 | 0 | 0 |
| Docs `research/` | 18 | 18 (REFERENCE) | 0 | 0 | 0 |
| Docs `_archive/` | 5 + junk | 5 | 0 | 0 | 0 |
| Docs корень | 8 | 4 | 4 | 0 | 0 |
| Docs `superpowers/plans/` | 6 | 0 | 6 | 0 | 0 |
| Docs `presentation/` | 5 | 5 (VKR-CRITICAL) | 0 | 0 | 0 |
| Корневой уровень untracked | ~15 | 0 | 0 | 11 | 4 (REFERENCE) |
| Корневой уровень tracked | ~10 | 6 | 4 | 0 | 0 |

**Главный вывод**: production-код (backend `app/` + frontend `src/`) — почти полностью в работе, тривиальные orphan'ы только во frontend. Шум сосредоточен в:
- `backend/scripts/` — 8 устаревших one-off скриптов (4 audit_*, 4 take_screenshots*),
- корне репозитория — 7 директорий-дубликатов и не-tracked мусор,
- `docs/` — около 8-10 документов, описывающих процесс который уже завершён (фазы rebuild'а, дифф-отчёты).

Удалять что-либо до защиты **не нужно и рискованно** — после защиты можно безопасно зачистить ~15-20 МБ.

---

## Backend code

### Routers — 8 файлов, все KEEP

Все подключены в `backend/app/main.py:173-179` через `app.include_router(...)`. Ни одного orphan'а.

| Файл | Статус | Почему KEEP |
|---|---|---|
| `routers/__init__.py` | KEEP | Барелл-экспорты роутеров |
| `routers/analytics.py` | KEEP | 12+ B2B endpoints (KPI, segments, booking-pace, etc) |
| `routers/documents.py` | KEEP | RAG-индексация, `reindex_chroma()` в scheduler |
| `routers/events.py` | KEEP | `/api/events` + read-time дедуп по 8 источникам |
| `routers/forecast.py` | KEEP | Ensemble + validate + explain |
| `routers/hotels.py` | KEEP | `/api/hotels` + segment-benchmark |
| `routers/parser.py` | KEEP | `/api/parser/*` (защищён API-key) |
| `routers/query.py` | KEEP | `/api/query` + SSE streaming |

### Services — 19 файлов, все KEEP

Полный import-граф проверен; все 19 файлов имеют как минимум одного импортёра внутри `app/`.

| Файл | Статус | Где импортируется |
|---|---|---|
| `services/__init__.py` | KEEP | Барелл-экспорты |
| `services/cache_service.py` | KEEP | `main.py:14`, warmup, rate-limit |
| `services/chroma_service.py` | KEEP | `main.py:12`, init `:94`, `documents.py`, scheduler |
| `services/data_service.py` | KEEP | Используется ВСЕМИ роутерами как доменный фасад |
| `services/db_service.py` | KEEP | `main.py:11,77,117` (lifecycle: connect/create/close) |
| `services/ensemble_service.py` | KEEP | `main.py:28` warmup, `forecast.py`, тесты |
| `services/feature_engineering.py` | KEEP | `forecast_agent.py`, `prophet_service.py`, тесты |
| `services/forecast_agent.py` | KEEP | `forecast.py:446`, упомянут в `main_agent.py:217` (специализированный агент прогноза) |
| `services/holidays_service.py` | KEEP | `feature_engineering.py:22`, `forecast_agent.py:38`, `prophet_service.py:14` |
| `services/llm_service.py` | KEEP | `main.py:13,98`, `query.py`, оба агента |
| `services/main_agent.py` | KEEP | `query.py:52` — центр AI-агента (12 B2B-tools) |
| `services/methodology_service.py` | KEEP | `analytics.py:1392` (seasonal_corrected baseline) |
| `services/neuralprophet_service.py` | KEEP | `ensemble_service`, `feature_engineering`, тесты |
| `services/parser_health_service.py` | KEEP | `scheduler.py:57`, `parser.py:27`, все парсеры через `_run_standalone_with_health` |
| `services/poi_service.py` | KEEP | `analytics.py:1393` (POI на Ольхоне drill-down) |
| `services/prophet_service.py` | KEEP | `ensemble_service`, `feature_engineering`, тесты |
| `services/protocols.py` | KEEP | DI-паттерн: `dependencies/__init__.py:11`, `analytics.py:18` (DataServiceProtocol) |
| `services/weather_service.py` | KEEP | `main.py:114-115`, warmup, `feature_engineering`, тесты |
| `services/xgboost_service.py` | KEEP | `ensemble_service`, `forecast.py` (explain), `feature_engineering` |

> **Замечание**: `forecast_agent.py` и `main_agent.py` — это **намеренный** разделённый дизайн (общий агент с tool-routing vs специализированный для прогноза). Оба нужны. Описано в `CLAUDE.md`.

### Parsers — 16 файлов, все KEEP (с одной заметкой)

| Файл | Статус | Заметка |
|---|---|---|
| `parsers/__init__.py` | KEEP | Барелл — `fetch_all_events`, импорты всех 8 source'ов |
| `parsers/__main__.py` | KEEP | CLI entry: `python -m app.parsers` |
| `parsers/base.py` | KEEP | `detect_event_type`, `ParsedEvent`, `BaseParser` |
| `parsers/ai_extractor.py` | KEEP | `events_yandex/kassir.py` — Crawl4AI/Jina wrapper |
| `parsers/anti_detection.py` | KEEP | `ai_extractor.py:25` — stealth + rate-limit |
| `parsers/health_monitor.py` | KEEP | `_run_standalone_with_health` во всех парсерах |
| `parsers/events_irk.py` | KEEP | scheduler + `parser.py:9` |
| `parsers/events_culture38.py` | KEEP | scheduler + `parser.py:10` |
| `parsers/events_zeroevent.py` | KEEP | scheduler + `parser.py:11` |
| `parsers/events_yandex.py` | KEEP | scheduler + `parser.py:12` (Crawl4AI/Jina) |
| `parsers/events_kassir.py` | KEEP | scheduler + `parser.py:13` (Crawl4AI) |
| `parsers/events_culture_rf.py` | KEEP | scheduler + `parser.py:17` |
| `parsers/events_telegram.py` | KEEP | scheduler + `parser.py:14` |
| `parsers/events_major.py` | **KEEP** | **РЕАЛЬНО используется**: `routers/events.py:14` импортирует `get_major_events_2025_2026` и `get_school_holidays_2025_2026` (hardcoded справочные данные за 2025-2026). Не путать с парсером — это data-provider. |
| `parsers/hotels_101hotels.py` | KEEP | scheduler + `parser.py:18` (основной источник, cron 2h) |
| `parsers/hotels_osm.py` | KEEP | OSM Overpass fallback (cross-ref Хаверсин 0.5 км) |
| `parsers/hotels_xotelo.py` | KEEP-as-scaffolding | По CLAUDE.md «deprecated, public API 400, скрипт под рукой если оживёт RapidAPI». Endpoint существует в `routers/parser.py:71-94`. Не ломает ничего; можно оставить или убрать после защиты. |
| `parsers/weather_openmeteo.py` | KEEP | scheduler (cron 3h), `weather_service` |

### Backend scripts — 13 tracked файлов

Здесь скрыт основной мусор Python-части проекта. Группировка по статусу:

#### KEEP (3 файла)

| Файл | Статус | Почему |
|---|---|---|
| `scripts/import_from_ydb_101hotels.py` | KEEP | Используется для дозабора данных (мартовские пробелы 2026 восстановлены 08.05.2026 через этот скрипт). Описан в `CLAUDE.md:94`. |
| `scripts/take_screenshots_final.py` | KEEP | Финальная версия скриншотов для презентации/отчёта. |
| `scripts/__pycache__/` | TRASH (untracked) | Pycache, удалить локально |

#### OBSOLETE → удалить после защиты (8 файлов, последний коммит `c3a1bbc` baseline)

Все 8 файлов имеют **один и тот же последний коммит** — `c3a1bbc chore: baseline snapshot before B2B-rebuild Phase 1`. То есть существовали ДО B2B-рефокуса и за 5+ недель активной работы НИ РАЗУ не правились — это сильный сигнал, что они никому не нужны.

| Файл | Размер | Почему OBSOLETE |
|---|---|---|
| `scripts/audit_chat.py` | small | Разовый Playwright UI-аудит чата. Output — `.screenshots/audit/`. Историческая утилита. |
| `scripts/audit_frontend.py` | small | Разовый аудит фронта. |
| `scripts/audit_quick.py` | small | Быстрый аудит. |
| `scripts/audit_tabs.py` | small | Аудит вкладок UI. |
| `scripts/take_screenshots.py` | small | Версия 1. |
| `scripts/take_screenshots_v2.py` | small | Версия 2. |
| `scripts/take_screenshots_v3.py` | small | Версия 3. |
| `scripts/test_llm_providers.py` | 9 KB | Тест fallback'а LLM-провайдеров. Функционал поглощён `main_agent.py:_resolve_provider_chain` (Groq → DeepSeek → Mistral). Покрыт тестами в `tests/test_agent_*`. |

#### Завершённые миграции → удалить или переместить в `_archive/` (2 файла)

| Файл | Статус | Почему |
|---|---|---|
| `scripts/import_csv_to_pg.py` | OBSOLETE | One-time миграция YDB → PostgreSQL, завершена 22.02.2026 (`CLAUDE.md`). Last commit — Initial. |
| `scripts/migrate_event_schema_v2.py` | OBSOLETE | One-time миграция event-схемы (ALTER + dedup constraint), применена. |

#### Следы non-tracked инфраструктуры

В **локальной файловой системе** есть, но в `git ls-files` НЕ tracked:
- `scripts/reclassify_events.py` — упомянут в CLAUDE.md как cron 6h. Видимо живёт локально, не в репо.
- `scripts/fill_hotel_types_from_osm.py` — упомянут в CLAUDE.md как утилита enrichment.
- `scripts/fill_hotel_types_from_xotelo.py` — упомянут в CLAUDE.md как «deprecated, под рукой».
- `scripts/import_missing_hotels.py` — Initial commit, но в `git ls-files` есть.

> **Странность**: 3 утилиты, которые активно описаны в CLAUDE.md, не закоммичены. Стоит проверить, не потерялись ли они на чужом компьютере / при ребейзах.

### Backend tests — 36 файлов, 34 KEEP + 2 артефакта

Все `test_*.py` файлы тестируют живой код. Особо отметить:
- `tests/test_dead_endpoints_removed.py` — намеренный охранный тест, что удалённые endpoint'ы возвращают 404/405 (legacy: `/api/forecast/neural`, `/xgboost`, `/compare` etc). KEEP.
- `tests/test_persona_walkthrough.py` — 3 persona-сценария (отельер/администратор/исследователь) добавлены 11.05.2026.
- `tests/conftest.py`, `tests/__init__.py` — pytest scaffolding. KEEP.
- `tests/e2e_test.py` — 9 end-to-end сценариев. KEEP.
- `tests/agent_stress_test.py` — упоминается в CLAUDE.md, 19 запросов с rubric. KEEP.

**TRASH (output-артефакты, не тесты)**:

| Файл | Что это |
|---|---|
| `tests/metrics_report.json` | Output какого-то прогона метрик. Не источник тестов. |
| `tests/results_20260206_144839.json` | Результаты стресс-теста за 06.02.2026. Не источник. Имя содержит timestamp. |

> Рекомендация: вынести в `tests/results/` (упомянут в CLAUDE.md), добавить `tests/results/*.json` в `.gitignore`.

### Прочее

| Артефакт | Размер | Статус | Действие |
|---|---|---|---|
| `backend/agent_graph.png` | 10 KB | OBSOLETE | LangGraph rendering от Feb 22 (5 версий tools назад). `git rm --cached`. |
| `backend/chroma_data/chroma.sqlite3` | 164 KB | TRASH | **Tracked** runtime БД ChromaDB. `.gitignore:34` ловит `*.sqlite`, но т.к. файл уже committed — игнорирование не работает. `git rm --cached` + добавить `backend/chroma_data/` в `.gitignore`. |
| `backend/Dockerfile` | — | KEEP | Production Dockerfile. |
| `backend/docker/parsers.Dockerfile` + `parsers-compose.yml` | — | KEEP | Standalone parsers compose (опциональный деплой), не мешает. |
| `backend/alembic/` | — | KEEP-as-scaffolding | Каркас не используется (CLAUDE.md), но сохранён для будущей миграции. |
| `backend/.env.example` | — | KEEP | Шаблон окружения. |
| `backend/pytest.ini` | — | KEEP | Pytest конфиг. |

---

## Frontend code

### Active files — 30 KEEP

Полный граф зависимостей от `main.tsx` → `App.tsx` → `pages/*` → `components/*` → `utils/*` проверен grep'ом.

**Pages (8/8 active)**: `Home, Analytics, Chat, Events, Forecast, HotelDetail, Map, About` — все в роутинге `App.tsx`.

**Components used**:
- `Layout.tsx` (главный wrapper, навигация, темы)
- `ErrorBoundary.tsx` + `ErrorState.tsx` (error handling)
- `YandexMap.tsx` (карта Иркутской области, fullscreen mode='browser')
- `MethodologyTooltip.tsx` (Portal-based, z-[9999])
- `ui/{Card, Button, Badge, Input, Dropdown}` — UI-кит

**Utils used**:
- `localize.ts` — RU labels (districts, event types, metrics)
- `chartTheme.ts` — Recharts foreground colors
- `format.ts` — `toRuDate`, `formatNumber`
- `localizeFeatures.ts` — XGBoost feature names (`lag_60`, `diff_7`, etc)
- `export.ts` — `exportChartPng` в `Forecast.tsx:18`

**Hooks**: `usePageTitle.ts` (на всех 8 страницах), `useTheme.ts` (Layout + Map)

**Constants/Lib/API**: `constants/districts.ts`, `lib/cn.ts`, `api/client.ts` — все используются.

### Orphans — 6 файлов (OBSOLETE)

Все верифицированы grep'ом: ноль импортёров вне самих файлов.

| Файл | Размер | Почему orphan |
|---|---|---|
| `components/GeoMap.tsx` | 88 строк | Использует `react-leaflet` (другая карто-библиотека) и `useTheme`. **Никем не импортируется**. В `pages/About.tsx:110` упомянут только как ТЕКСТ-метка («Региональная карта на GeoMap по 15 районам»), не import. Заменён на `YandexMap.tsx`. |
| `components/HeatmapGrid.tsx` | 94 строки | Никем не импортируется. Видимо заменён на Recharts heatmap внутри `Analytics.tsx`. |
| `components/OccupancyIndicator.tsx` | 36 строк | Никем не импортируется. Старый dashboard-виджет от B2C? |
| `components/InsightCard.tsx` | 68 строк | Никем не импортируется. |
| `utils/insights.ts` | — | Никем не импортируется во frontend (есть `Insight` в backend как ML feature, но не отсюда). |
| `utils/weather.ts` | — | Никем не импортируется. Backend имеет `weather_service` (OpenMeteo), фронт использует данные через API. |

> **Удалить можно после защиты** одной командой:
> ```bash
> rm frontend/src/components/{GeoMap,HeatmapGrid,OccupancyIndicator,InsightCard}.tsx
> rm frontend/src/utils/{insights,weather}.ts
> ```
>
> Если `react-leaflet` используется только в `GeoMap.tsx` — после удаления можно убрать его и из `package.json` (uninstall + lock-update).

---

## Документация (`docs/`)

### `docs/vkr/` — 25 элементов, ядро ВКР

#### VKR-CRITICAL (НЕ ТРОГАТЬ)

| Файл | Размер | Роль |
|---|---|---|
| `vkr/OTCHET_PO_PRAKTIKE.md` | 223 KB | **ФИНАЛЬНЫЙ рабочий отчёт** (32 audit-фикса применены). |
| `vkr/REFERENCES_REVIEW.md` | 22 KB | Полный аудит 53 источников (7 правок применены 11.05.2026). |
| `vkr/Приложение_А_ТЭО.md` | 27 KB | ТЭО (Приложение А). |
| `vkr/VKR_REVISION_PLAN.md` | 56 KB | План аудита (блоки A/B/C/D/E). |
| `vkr/AUDIT_32_RULES.md` | 27 KB | 32 правила проверки. |
| `vkr/AUDIT_AI_TRACES.md` | 32 KB | AI-traces в тексте (где сгенерировано). |
| `vkr/AUDIT_DIFF_ORIGINAL.md` | 33 KB | Diff между версиями. |
| `vkr/AUDIT_TABLES_FIGURES.md` | 13 KB | Аудит таблиц и нумерации. |
| `vkr/SESSION_DELTA_REPORT.md` | — | Журнал правок по сессиям. |
| `vkr/FINAL_WRITING_STYLE_GUIDE.md` | 55 KB | Style guide (научный русский). |
| `vkr/SUPERVISOR_REQUIREMENTS.md` | 4 KB | Требования научрука. |
| `vkr/WRITING_RULES.md` | 3 KB | Правила оформления. |
| `vkr/OTCHET_PO_PRAKTIKE_ISPOLATOV.docx` + `.pdf` | — | Артефакты для печати. |
| `vkr/figures/` (35 элементов) | — | Финальный набор картинок (figure_13-18 + b2b_v2 диаграммы). См. секцию 6. |
| `vkr/build_docx.py`, `inspect_styles.py`, `verify_styles.py` | — | Генераторы финальных документов из MD. |

#### OBSOLETE — после защиты в `_archive/`

| Файл | Размер | Почему OBSOLETE |
|---|---|---|
| `vkr/OTCHET_PO_PRAKTIKE_FROM_DOCX.md` | 151 KB | Старая конвертированная из docx версия, заменена на `OTCHET_PO_PRAKTIKE.md`. |
| `vkr/cursovaya_backup/` | — | Backup курсовой работы (2 docx + 1 png + 1 md, имена в битой кодировке). Дублирует корневую `cursovaya/`. |

#### NEEDS-REVIEW (не трогать пока, но проверить состав после защиты)

| Файл | Размер | Замечание |
|---|---|---|
| `vkr/VKR_DRAFT.md` | 97 KB | Черновик. Если содержимое вошло в `OTCHET_PO_PRAKTIKE.md` — после защиты архивировать. |
| `vkr/VKR_PARAGRAPH.md` | 29 KB | Параграфы. То же. |
| `vkr/VKR_PRACTICAL_DOCUMENTATION.md` | 61 KB | Практическая часть. То же. |
| `vkr/VKR_THEORETICAL_FRAMEWORK.md` | 25 KB | Теоретическая часть. То же. |
| `vkr/VKR_STRUCTURE.md` | 8 KB | Старая структура. |

> **Не трогать ни одного из этих файлов до защиты.** Они могут быть исходниками `OTCHET_PO_PRAKTIKE.md`, и пропажа в момент финального просмотра — катастрофа.

### `docs/presentation/` — 5 элементов, всё VKR-CRITICAL

| Файл | Роль |
|---|---|
| `PREZENTACIYA_VKR.md` (48 KB) | Текст речи на защиту (B2B версия). |
| `PREZENTACIYA_S_RECHYU.md` (18 KB) | Альтернативная версия речи. |
| `text_zashity.txt` (11 KB) | Plain-text вариант защиты. |
| `*.pptx` (~56 MB) | Слайды. |
| `*.pdf` | PDF слайдов. |
| `Informacionno-analiticheskaya-sistema-monitoringa-...pptx` | Финальные слайды. |

### `docs/project/` — 12 файлов

#### KEEP (актуальные ссылочные)

| Файл | Размер | Роль |
|---|---|---|
| `project/PROJECT_STATUS.md` | 34 KB | Reference snapshot перед B2B-rebuild. Цитируется как «текущий статус» в CLAUDE.md. |
| `project/TEO_POLNOE.md` | 91 KB | ТЭО полное (Приложение А, основной источник). |
| `project/AI_AGENT_TEST_REPORT.md` | 15 KB | Отчёт по тестам AI-агента. |
| `project/PG_MIGRATION_PLAN.md` | 9 KB | План миграции YDB → PG (выполнен, история). |
| `project/RISKS_MANAGEMENT.md` | 10 KB | Управление рисками. |
| `project/WBS_DICTIONARY.md` + `WBS_NETWORK.md` + `WBS_VKR.xml` | — | WBS-диаграммы. |
| `project/kontseptsiya-sistema-turizma.md` + `tz-sistema-turizma.md` | — | Концепция и ТЗ. |
| `project/GANTT_RISKS.drawio` + `NETWORK_DIAGRAM.drawio` | — | Диаграммы (drawio source). |

#### OBSOLETE (старые, до B2B-рефокуса) — в `_archive/` после защиты

| Файл | Размер | Замечание |
|---|---|---|
| `project/PROJECT_FOCUS.md` | 817 байт | Stub-redirect, указывает на `_archive/PROJECT_FOCUS.md`. Намеренный перенаправлятель, можно удалить. |
| `project/PROJECT_CONTEXT.md` | 13 KB | Старая B2C-концепция. |
| `project/PROJECT_AUDIT.md` | 29 KB | Архивный аудит, marked archived в самом файле. |

### `docs/research/` — 18 файлов, все REFERENCE

Все 18 `*_RESEARCH.md` — научно-справочные обоснования выбора стека (DATABASE, ORM, BACKEND_FRAMEWORK, FRONTEND_STACK, AGENT_FRAMEWORK, LLM_PROVIDERS, MISTRAL_MODELS, EMBEDDING, VECTOR_DB, CACHE, INFRASTRUCTURE, DASHBOARD, PARSERS, PARSERS_AUDIT, PARSERS_IMPLEMENTATION_PLAN, PARSERS_RESEARCH, AGGREGATORS, FORECAST_MODEL, FORECAST_CLASSICAL_COMPARISON, LANGGRAPH_AGENT). KEEP — могут потребоваться для списка литературы или вопросов комиссии.

### `docs/_archive/` — 5 файлов + `junk_from_root/`

Уже архивные — KEEP в `_archive/`:
- `_archive/DEEP_AUDIT_2026_03_27.md`
- `_archive/DIPLOM_PRESENTATION.md` (старая презентация)
- `_archive/GLOBAL_AUDIT.md` (145 фиксов от 25.03.2026)
- `_archive/PROJECT_FOCUS.md` (старая B2B+B2C концепция)
- `_archive/PROMPTS_FOR_NEW_SESSION.md`
- `_archive/README.md`
- `_archive/junk_from_root/figure_6_home.png`, `temp_refs.txt`

### `docs/superpowers/` — OBSOLETE

| Файл | Статус | Почему |
|---|---|---|
| `superpowers/plans/2026-05-04-rebuild-phase{1,2,3,4,6}-*.md` | OBSOLETE | Phase 1-6 завершены 04.05.2026 (CLAUDE.md). История процесса — в `_archive/rebuild_phases/`. |
| `superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md` | OBSOLETE | Та же причина. |

### `docs/` корень

#### KEEP

| Файл | Роль |
|---|---|
| `NORTH_STAR.md` | Единый источник правды (B2B-курс, дедлайн 12.05.2026). |
| `SESSION_HANDOFF.md` | Текущее состояние работ (обновлён 11.05.2026). |
| `REFOCUS_PLAN.md` | План 9 этапов с DoD. |
| `DEPLOYMENT.md` | Deployment guide. |

#### OBSOLETE — после защиты в `_archive/`

| Файл | Размер | Почему |
|---|---|---|
| `MERGE_GUIDE.md` | 9 KB | Гайд по merge стратегий B2B-фаз — нужен при merge'е, после — история. |
| `PHASE_REBUILD_SUMMARY.md` | 5 KB | Summary исполненных фаз. |
| `OTCHET_DIFF_ANALYSIS.md` | 174 KB | Diff-анализ. После защиты ценности нет. |
| `ORIGINAL_OTCHET.md` | 189 KB | Исходная версия (для сравнения). |

#### Дубликаты-OBSOLETE — в `_archive/` или удалить

| Файл | Дубликат для |
|---|---|
| `docs/Ежедневные записи студента.docx.md` (русское имя) | Конвертированный из docx, дубликат assignments. |
| `docs/Индивидуальное задание на предди... Исполатов.docx (1).md` | То же. |
| `docs/Копия Индивидуальное задание на производственную...docx.md` | То же. |

### `docs/assignments/`

| Файл | Статус |
|---|---|
| `assignments/ZADANIE_2_OPISANIE_PRODUKTA.md` | KEEP (задание от руководителя). |

---

## Корневой уровень

### TRASH untracked (~600 KB, можно удалить ЛЮБОЕ ВРЕМЯ)

Эти файлы вообще не в git — удаление 100% безопасно, никак не влияет на репозиторий.

| Файл / директория | Размер | Что это |
|---|---|---|
| `.pytest-final.log` | 36 KB | Лог локального запуска тестов. |
| `.pytest-final2.log` | 36 KB | Тоже. |
| `.pytest-run.log` | 52 KB | Тоже. |
| `.pytest-run2.log` | 40 KB | Тоже. |
| `.pytest-x.log` | 36 KB | Тоже. |
| `__pycache__/` | — | Python bytecode на уровне корня (НЕ должен быть). |
| `{03E0FC43-...}.png` | 45 KB | Скриншот Snip&Sketch (May 10, GUID-имя). |
| `{113402B0-...}.png` | 99 KB | Тот же. |
| `{8226E30A-...}.png` | 275 KB | Тот же. |
| `lightning_logs/` | 3.4 MB | PyTorch Lightning training artifacts. В `.gitignore:43-44`. |
| `.cache/` | 0 байт | Пустая. |
| `.playwright-mcp/` | 16 KB | MCP-сервер Playwright локальный кэш. |
| `screenshots/` (без точки) | 200 KB | 3 GUID-png; дубликат `.screenshots/`. |

**Итог untracked TRASH**: ~4.3 МБ.

### Tracked OBSOLETE (требуют `git rm` после защиты)

| Директория | Размер | Что внутри | Почему OBSOLETE |
|---|---|---|---|
| `archive/` | 16 KB | `PROJECT_STATUS_ANALYSIS.md`, `PROMPT_FOR_AGENT.md` | Дубликат семантики `docs/_archive/`. |
| `cursovaya/` | 11 MB | 1 docx + 1 md + 1 png (битые имена в UTF-16) | Backup курсовой; есть в `docs/vkr/cursovaya_backup/`. |
| `Individual_task/` | 24 KB | 2 .md (русские имена) | Дубликаты `docs/assignments/` и docx-конвертов в `docs/`. |
| `.screenshots/` | 69 MB | 29 файлов помечены deleted в `git status`, остаётся `.screenshots/audit/` | Нужно `git rm -r .screenshots/` (закоммитить уже-удалённое). |

### REFERENCE (учебно-справочные, KEEP)

| Директория | Размер | Что внутри |
|---|---|---|
| `models/` | 7.2 MB | UML-модели в drawio: ACTIVITY, BP, CLASS, COMPONENT, DOMAIN, IDEF0/1/3, REQ, ROBUSTNESS, SEQUENCE, UC, UI + 5 ML-json (`forecast_*.json`). Используется в ВКР как иллюстрации. |
| `teachers_materials/` | 22 MB | 18 файлов: лекции ИГУ (10-18 ПИС) + GOST 34602-89 (PDF + md). Нормативные ссылки и методички. |
| `new_tasks/` | 8.3 MB | 16 учебных PDF по ТЭО + Monte Carlo шаблоны (.xlsm, .docx, .md). Цитируется в `scripts/monte_carlo_teo.py`. |
| `example/` | 268 KB | `vkr-gorokhov-a-e.md` (чужой пример ВКР для структуры). |
| `scripts/` (root) | 48 KB | `dev-up.ps1` (запуск стека) + `monte_carlo_teo.py` (расчёт ТЭО). Активны. |

После защиты эти 4 директории можно опционально перенести в `docs/reference/` для порядка, но это **косметика, не зачистка**.

### Special case: `101hotel_parser/`

Это **отдельный legacy-проект** (НЕ пустая директория):
```
101hotel_parser/
├── main.py
├── requirements.txt
├── venv/
├── databases/
├── tables/
├── logs/
└── authorized_key.json
```

Старый курсовой парсер 101hotels (Feb 22, 2026). Сейчас его функция переехала в `backend/app/parsers/hotels_101hotels.py`. В `.gitignore:40` (untracked, локально лежит, в репо его нет).

**Decision**: REFERENCE / локальный архив. Не мешает (т.к. не в git).

### Корневые tracked-файлы — в основном KEEP

| Файл | Статус | Замечание |
|---|---|---|
| `.cursorignore` | KEEP | Конфиг Cursor IDE. |
| `.cursorrules` | KEEP | Правила проекта для Cursor IDE (B2B-курс). |
| `.gitignore` | KEEP | См. секцию 7 — есть пробелы. |
| `CLAUDE.md` | KEEP-100% | Главный конфиг Claude Code. |
| `claude-vpn.bat` | KEEP, переместить | Прокси-обёртка `claude` через `127.0.0.1:10808`. После защиты — в `scripts/`. |
| `docker-compose.yml` | KEEP | Инфраструктура (postgres, redis). |
| `AI_TEXT_DETECTION_RULES.md` (61 KB, untracked) | REFERENCE | Reference для рерайта AI-текста под академический стиль. После защиты — `docs/_archive/` или `docs/vkr/reference/`. |
| `.cursor/` | KEEP | Cursor IDE workspace. |
| `.github/` | KEEP | GitHub Actions workflows. |
| `.claude/` | KEEP (untracked, в gitignore) | Claude Code workspace. |
| `.remember/` | KEEP (untracked, в gitignore) | Memory store. |

---

## Кейс `figure_4..9.png`

В `git status` помечены как deleted:
- `docs/vkr/figures/figure_4_navigation.png`
- `docs/vkr/figures/figure_5_analytics.png`
- `docs/vkr/figures/figure_6_home.png`
- `docs/vkr/figures/figure_7_forecast.png`
- `docs/vkr/figures/figure_8_map.png`
- `docs/vkr/figures/figure_9_chat.png`

**Это НЕ блокер защиты.**

Проверка:
1. `grep "\.png\|\.drawio" docs/vkr/OTCHET_PO_PRAKTIKE.md` → **0 совпадений**.
2. `grep "figure_" docs/vkr/OTCHET_PO_PRAKTIKE.md` → **0 совпадений**.

Это значит: основной отчёт (`OTCHET_PO_PRAKTIKE.md`) **не содержит markdown-ссылок** на `.png`. Все картинки в финальный документ вставлены через `.docx` (Word-формат, картинки внутри).

**Текущий состав `docs/vkr/figures/` (35 элементов)**:
- Финальные `figure_13_navigation`, `figure_14_themes_{dark,light}`, `figure_15_analytics`, `figure_16_forecast`, `figure_17_map`, `figure_18_chat`
- Архитектурные диаграммы: `figure_1_architecture`, `figure_2_er_diagram`, `figure_3_agent_graph`, `figure_4_research_sources`, `figure_6_data_pipeline`, `figure_10_ensemble_pipeline`, `figure_10_rms_competitors`
- B2B v2 диаграммы: `use_case_b2b_v2`, `domain_b2b_v2`, `component_diagram_b2b_v2`, `idef0_a0_b2b_v2`, `idef0_a-0_b2b_v2`, `bp_model-Контекстная диаграмма`, `bp_model-Декомпозиция`, `deployment_diagrams-БП1...`, `uc11_sequence`, `figure_10_sequence_uc1`

**Действие**: после защиты можно безопасно `git rm` удалённые файлы, чтобы зафиксировать текущее состояние:
```bash
git rm docs/vkr/figures/figure_{4_navigation,5_analytics,6_home,7_forecast,8_map,9_chat}.png
```

---

## Пробелы в `.gitignore`

Текущий файл:
```
1   # Окружение
2   .env
3   .env.bak
4   authorized_key.json
5
6   # Claude Code / IDE persistent state
7   .remember/
8   .claude/
9
10  # Python
11  __pycache__/
12  *.pyc
13  *.pyo
14  *.pyd
15  venv/
16  .venv/
17
18  # IDE
19  .vscode/
20  .idea/
21  .cursor/
22
23  # Node
24  node_modules/
25  dist/
26  *.log
27
28  # Chroma DB
29  chroma_db/
30
31  # Базы данных
32  *.csv
33  *.db
34  *.sqlite
35
36  # Логи
37  logs/
38  *.log
39
40  101hotel_parser/
41
42  # NeuralProphet training logs
43  lightning_logs/
44  backend/lightning_logs/
45
46  # Test artifacts
47  test_report*.json
48  *_TEST_REPORT.md
49  *_TEST_SUMMARY.md
50  EXECUTIVE_SUMMARY.md
51  TEST_REPORTS_INDEX.mdpytest_out.txt    ← BUG: склеены 2 правила
```

### Проблемы

1. **Строка 51** — синтаксическая склейка: `TEST_REPORTS_INDEX.md` и `pytest_out.txt` слились в одно правило. Должно быть две строки.
2. **`.pytest-*.log` не ловятся**: правило `*.log` (строка 26, 38) теоретически должно их ловить, но на практике файлы `.pytest-final.log` лежат **untracked** (значит правило срабатывает) — ОК. Но `.gitignore` не явно говорит про pytest-логи; стоит добавить явно для читаемости.
3. **GUID-png** в корне (`{03E0FC43-...}.png` и т.п.) не ловятся. Нужно `{*}.png`.
4. **`screenshots/`** (без точки) не ловится. `.screenshots/` тоже не в .gitignore (хотя там 29 файлов tracked).
5. **`backend/chroma_data/`** не ловится — есть `chroma_db/` (другое имя). А `*.sqlite` (строка 34) не помогает, т.к. файл уже tracked.
6. **`backend/agent_graph.png`** — артефакт, нужно явно или добавить `agent_graph.png` в правила.
7. **`tests/results/*.json`** — куда CLAUDE.md обещает писать output stress-test'ов. Стоит добавить.

### Предлагаемая правка (применить только после защиты)

```diff
 # Окружение
 .env
 .env.bak
 authorized_key.json

 # Claude Code / IDE persistent state
 .remember/
 .claude/

 # Python
 __pycache__/
 *.pyc
 *.pyo
 *.pyd
 venv/
 .venv/

 # IDE
 .vscode/
 .idea/
 .cursor/

 # Node
 node_modules/
 dist/
 *.log

 # Chroma DB
 chroma_db/
+backend/chroma_data/

 # Базы данных
 *.csv
 *.db
 *.sqlite

 # Логи
 logs/
 *.log
+.pytest-*.log

 101hotel_parser/

 # NeuralProphet training logs
 lightning_logs/
 backend/lightning_logs/

 # Test artifacts
 test_report*.json
 *_TEST_REPORT.md
 *_TEST_SUMMARY.md
 EXECUTIVE_SUMMARY.md
-TEST_REPORTS_INDEX.mdpytest_out.txt
+TEST_REPORTS_INDEX.md
+pytest_out.txt
+backend/tests/results/*.json
+backend/tests/metrics_report.json
+
+# Скриншоты Snip&Sketch / артефакты презентации
+{*}.png
+screenshots/
+.screenshots/
+
+# Backend артефакты
+backend/agent_graph.png
```

---

## Action plan

Четыре bucket'а, отсортированы по риску. **До защиты (12.05.2026) применять только Bucket 1.**

### Bucket 1 — Zero risk (untracked мусор) ⏰ можно сейчас

Эти файлы **не в git вообще**, их удаление никак не влияет на репозиторий.

```bash
# Из корня проекта
rm .pytest-final.log .pytest-final2.log .pytest-run.log .pytest-run2.log .pytest-x.log
rm -r __pycache__/
rm '{03E0FC43-6723-4679-B0FD-B80C988740AB}.png' \
   '{113402B0-2A5B-441F-A91B-EADDEAE76D0A}.png' \
   '{8226E30A-B59B-447C-B7E2-9409C3422B12}.png'
rm -r lightning_logs/ .cache/ .playwright-mcp/ screenshots/
```

**Объём освобождения**: ~4.3 МБ. **Изменение в git**: 0 (всё untracked).

### Bucket 2 — Low risk (tracked legacy → `git rm`) ⚠️ ПОСЛЕ защиты

Эти изменения формально модифицируют git — лучше делать после защиты, когда основная работа сохранена.

```bash
# Зафиксировать удаления .screenshots/ (29 файлов уже помечены D в git status)
git rm -r .screenshots/

# Убрать runtime-БД из репо
git rm --cached backend/chroma_data/chroma.sqlite3

# Убрать старый артефакт LangGraph
git rm --cached backend/agent_graph.png

# Зафиксировать удаления figure_4..9 (если ещё не зафиксированы)
git rm docs/vkr/figures/figure_{4_navigation,5_analytics,6_home,7_forecast,8_map,9_chat}.png

# Применить .gitignore-фиксы (см. секцию 7)
# ... edit .gitignore ...

git commit -m "chore: cleanup legacy artifacts post-defense"
```

### Bucket 3 — Medium risk (mass moves в `_archive/`) ⚠️⚠️ ПОСЛЕ защиты

Перемещение/удаление дублирующих директорий и архивных доков.

```bash
# Удалить корневые дубликаты
git rm -r archive/ cursovaya/ Individual_task/

# Удалить .docx.md дубли в docs/ (3 файла с русскими именами)
git rm "docs/Ежедневные записи студента.docx.md" \
       "docs/Индивидуальное задание на преддипломную практику 2026 (очная форма обучения) Исполатов.docx (1).md" \
       "docs/Копия Индивидуальное задание на производственную практику 2026 (очная форма обучения).docx.md"

# Переместить выполненные планы фаз в архив
mkdir -p docs/_archive/rebuild_phases/
git mv docs/superpowers/plans/*.md docs/_archive/rebuild_phases/
git mv docs/superpowers/specs/*.md docs/_archive/rebuild_phases/

# Архивировать отработанные процесс-документы
git mv docs/PHASE_REBUILD_SUMMARY.md docs/_archive/
git mv docs/MERGE_GUIDE.md docs/_archive/
git mv docs/OTCHET_DIFF_ANALYSIS.md docs/_archive/
git mv docs/ORIGINAL_OTCHET.md docs/_archive/
git mv docs/vkr/OTCHET_PO_PRAKTIKE_FROM_DOCX.md docs/_archive/
git mv docs/vkr/cursovaya_backup/ docs/_archive/

# Архивировать стары project/ доки (B2C-эра)
git mv docs/project/PROJECT_FOCUS.md docs/_archive/PROJECT_FOCUS_stub.md
git mv docs/project/PROJECT_CONTEXT.md docs/_archive/
git mv docs/project/PROJECT_AUDIT.md docs/_archive/

# Переместить root-вспомогательное в scripts
mv claude-vpn.bat scripts/

# AI_TEXT_DETECTION_RULES.md (untracked) → в архив или удалить
mv AI_TEXT_DETECTION_RULES.md docs/_archive/

git commit -m "docs: consolidate legacy & rebuild-phase artifacts in _archive/"
```

### Bucket 4 — High risk (удаление кода) ⚠️⚠️⚠️ ПОСЛЕ защиты, поштучно

Каждый файл — отдельный grep-чек перед удалением (на случай dynamic imports или текстовых упоминаний).

#### Backend scripts (10 файлов)

```bash
git rm backend/scripts/audit_chat.py \
       backend/scripts/audit_frontend.py \
       backend/scripts/audit_quick.py \
       backend/scripts/audit_tabs.py
git rm backend/scripts/take_screenshots.py \
       backend/scripts/take_screenshots_v2.py \
       backend/scripts/take_screenshots_v3.py
git rm backend/scripts/import_csv_to_pg.py \
       backend/scripts/migrate_event_schema_v2.py \
       backend/scripts/test_llm_providers.py
```

#### Backend tests artifacts (2 файла)

```bash
git rm backend/tests/metrics_report.json \
       backend/tests/results_20260206_144839.json
```

#### Frontend orphans (6 файлов)

> **Перед удалением**: повторно `grep -r 'GeoMap\|HeatmapGrid\|OccupancyIndicator\|InsightCard' frontend/src/` чтобы убедиться, что не появились новые импортёры.

```bash
git rm frontend/src/components/GeoMap.tsx \
       frontend/src/components/HeatmapGrid.tsx \
       frontend/src/components/OccupancyIndicator.tsx \
       frontend/src/components/InsightCard.tsx \
       frontend/src/utils/insights.ts \
       frontend/src/utils/weather.ts
```

После удаления GeoMap.tsx — рассмотреть удаление `react-leaflet` и `leaflet` из `package.json` (если других импортёров нет).

#### Backend hotels_xotelo (опционально)

```bash
# CLAUDE.md помечает как deprecated, но scaffolding оставлен
# Удалять только если уверены что RapidAPI не оживёт
git rm backend/app/parsers/hotels_xotelo.py
# + убрать импорт в parsers/__init__.py:63
# + убрать endpoint в routers/parser.py:71-94
```

### Verification после Bucket 4

```bash
# Backend
cd backend && source venv/Scripts/activate && pytest tests/ -v

# Frontend
cd frontend && npm run build

# Smoke-test
cd backend && PYTHONIOENCODING=utf-8 uvicorn app.main:app --port 8000
# → curl http://localhost:8000/health
# → открыть http://localhost:5173 (frontend), пройти все 8 страниц
```

Если что-то падает — откатиться: `git reset --hard HEAD~1`.

---

## Итоги

**Главный вывод**: проект в неплохой форме. Production-код практически не содержит мёртвых файлов, основной шум — в накопившихся одноразовых скриптах (`backend/scripts/`), 6 frontend-orphan'ах и нескольких папках-дубликатах в корне.

**Сценарий действий**:
1. **Сейчас (до 12.05)**: применить только Bucket 1 (untracked мусор), либо вообще ничего — отчёт уже даёт полную карту.
2. **После защиты** (с 13.05): Bucket 2 → 3 → 4, в указанном порядке, с verification после каждого.

**Освобождение по итогам всех 4 bucket'ов**:
- ~4.3 МБ untracked
- ~80 МБ legacy (в основном `cursovaya/` 11 МБ + `.screenshots/` 69 МБ)
- ~22 файла кода/доков, которые загромождают навигацию

Документ-карта (этот отчёт) сохраняется в `docs/AUDIT_FILES_2026_05_11.md` как reference на будущее.
