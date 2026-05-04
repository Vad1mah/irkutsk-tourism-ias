# Глубокий аудит проекта Tourism Analytics

**Дата:** 27.03.2026
**Метод:** 3 раунда по 4 субагента + боевое тестирование (16 независимых проверок)
**Охват:** Backend (52 Python-файла), Frontend (31 TS/TSX-файл), Инфраструктура (Docker, nginx), ML-pipeline, Тесты

## Сводка

| Критичность | Количество |
|-------------|-----------|
| Critical | 26 |
| High / Important | 42 |
| Medium | 24 |
| **Итого** | **92** |

Подтверждённые (найдены 2+ раундами): 12

### Подтверждённо безопасные области (Battle Testing)

| Область | Результат |
|---------|-----------|
| SQL Injection (hotels, events) | Whitelist + SQLAlchemy ORM + LIKE escaping |
| XSS через Chat | ReactMarkdown default escaping, нет dangerouslySetInnerHTML |
| API Key auth (parser endpoints) | hmac.compare_digest, production block без ключа |
| Session ID prediction | crypto.randomUUID (CSPRNG) |
| Secrets в логах | SecretStr обёртки |
| days_ahead validation (/ensemble) | Pydantic ge=1, le=365 |
| Theme switching | CSS-переменные + isDark useEffect |
| Empty hotel stats | Корректный empty state |

---

## CRITICAL (26)

### ML: Target Leakage (утечка таргета в фичи)

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 1 | `feature_engineering.py:165` | `diff(d)` = `y[i] - y[i-d]` содержит текущий target y[i]. XGBoost учит тривиальный паттерн `y = diff_1 + lag_1` | 3A |
| 2 | `feature_engineering.py:178-182` | `rolling(7).mean()` включает y[i] — 1/7 target в фиче. Train-inference distribution shift | 3A |
| 3 | `feature_engineering.py:377-380` | diff fixup off-by-one: первые d тестовых строк содержат фактический test target | 3A |

**Fix:** `df["y"].shift(1).diff(d)` и `df["y"].shift(1).rolling(w).mean()` — исключить текущее значение.

### Блокировка Event Loop

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 4 | `main_agent.py:59-107` | Sync tools search_hotels/search_events вызывают chroma_service.search() → sync HTTP к GigaChat Embeddings API (200-1500ms блокировка) | 1A |
| 5 | `chroma_service.py:78` | embed_query() — sync HTTP в async контексте. search_async() существует, но не используется в llm_service | 1A |

**Fix:** Сделать search_hotels/search_events async, использовать chroma_service.search_async().

### Безопасность

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 6 | `nginx.conf:22-25` | `/assets/` блок перезаписывает ВСЕ security headers (CSP, X-Frame-Options, X-Content-Type-Options) из-за nginx add_header behavior | 2A |
| 7 | `rate_limit.py:42-47` | Rate limiting сломан в Docker full mode — все клиенты получают один IP (Docker bridge), TRUSTED_PROXIES не включает Docker subnet | 2A |

### Производительность

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 8 | `neuralprophet_service.py:143-145` | Двойной model.predict() — +30-50% время прогноза NeuralProphet | 2B |
| 9 | `ensemble_service.py:335` | compare_models использует sync forecast_ensemble (модели последовательно ~15s вместо ~5s параллельно) | 2B |
| 10 | `analytics.py:1114-1116` | 3 последовательных DB-запроса вместо asyncio.gather — 3x latency | 2B |
| 11 | `db_service.py:441-461` | 4 последовательных DB round-trip в get_total_metrics — 4x latency | 2B |

### Отказоустойчивость

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 12 | `session.py:17-28` | Нет таймаутов на SQL-запросы (connect_args, pool_timeout). PostgreSQL lock → все запросы зависают бесконечно | 2C |
| 13 | `chroma_service.py:29-46` + `main.py:93` | ChromaDB init без try/except — битый файл убивает весь startup, хотя 90% API не зависит от ChromaDB | 2C |
| 14 | `main.py:106-111` | weather_service._session не закрывается при shutdown — утечка file descriptors | 2C |
| 15 | `chroma_service.py:65-67` | /health crash при коррупции ChromaDB — мониторинг считает сервис мёртвым | 2C |

### Безопасность Rate Limiting

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 16 | `rate_limit.py:137-147` | Redis ZADD unconditional — rejected requests считаются, продлевая penalty window | 1B |
| 17 | `rate_limit.py:80` | Rate key по полному пути — /api/query и /api/query/stream имеют отдельные лимиты (20 LLM вызовов/мин вместо 10) | 1B |

### Парсеры

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 18 | `anti_detection.py:134-164` | asyncio.Lock held во время asyncio.sleep — блокированный домен парализует ВСЕ парсеры | 1D |
| 19 | `scheduler.py:218-223` | Initial collection без scheduler protection — overlap с scheduled jobs → DDoS источников | 1D |

### Thread Safety

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 20 | `ensemble_service.py:332-341` | _calibrating flag не thread-safe при concurrent asyncio.to_thread — race condition на _weights | 1A |

### Тесты и качество

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 21 | `test_security.py` | Тесты реимплементируют логику вместо тестирования реального кода — могут проходить при сломанном production | 3B |
| 22 | `tests/` | частичное покрытие: ~94 unit-теста, включая test_routers.py | 3B |
| 23 | `tests/` | 0 async тестов — вся async логика (db, cache, routers, agent) не покрыта | 3B |
| 24 | `db_service.py` | 15+ методов DBService без единого unit-теста | 3B |

### Данные

| # | Файл | Описание | Раунды |
|---|------|----------|--------|
| 25 | `db_service.py:587-593` | Нет Alembic миграций — только create_all. Изменение схемы на production невозможно без потери данных | 3D |
| 26 | `db_service.py:282, 320` | insert_event допускает пустой PK ("") — все события без ID перезаписывают друг друга | 3D |

---

## HIGH / IMPORTANT (42)

### AI-агент

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 27 | `main_agent.py:544-554` | MemorySaver cleanup через internal .storage; _SESSION_TTL мёртвый код | 1A |
| 28 | `llm_service.py:310` | Gemini response.text ValueError при safety-blocked ответах | 1A |
| 29 | `main_agent.py:447-451` | При исчерпании tool limit LLM не знает что нужно отвечать текстом — пустой ответ | 1A |
| 30 | `forecast_agent.py:210` | get_feature_importance() sync вызов в async node | 1A |
| 31 | `main_agent.py:496-503` | Sync fallback удваивает latency при реальных ошибках tools | 1A |
| 32 | `llm_service.py:86-101` | Indirect prompt injection через ChromaDB данные — tool results не санитизируются | 1A, 2A |

### Роутеры

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 33 | `forecast.py` (9 endpoints) | Нет валидации district против VALID_DISTRICTS в forecast endpoints | 1B |
| 34 | `events.py:55-69` | Один невалидный event date крашит весь /api/events (500 для всех) | 1B |
| 35 | `forecast.py:352-357` | /api/forecast/compare не возвращает confidence intervals (lower/upper всегда 0) | 1B |
| 36 | `forecast.py:53` | random.seed() модифицирует глобальное состояние — race condition при concurrent requests | 1B |

### Безопасность

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 37 | `nginx.conf` + `main.py` | Нет ограничения размера тела запроса — memory DoS (100MB body в RAM до валидации) | 2A, BT |
| 38 | `query.py:67-96` | SSE без лимита параллельных соединений per IP — slowloris-подобная атака | 2A |
| 39 | `nginx.conf` | HSTS отсутствует (заявлен в документации, но не реализован) | 2A |

### Производительность

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 40 | `analytics.py:440-441` | Sequential get_kpi queries — +40% latency | 2B |
| 41 | `analytics.py:128-132` | Duplicate get_monthly_statistics при фильтре по году | 2B |
| 42 | `db_service.py:145` | ORDER BY computed expression (ABS) без индекса — full table scan | 2B |
| 43 | `forecast.py:133-138` | Weather для ВСЕХ исторических дат (+200-500ms HTTP) | 2B |
| 44 | `xgboost_service.py:232-243` | Double feature_engineering при retrain (+200ms) | 2B |
| 45 | `poi_service.py:86-87` | Новый aiohttp.ClientSession на каждый запрос (+100-300ms overhead) | 2B |
| 46 | `analytics.py:331-332` | Sequential recommendation queries | 2B |

### Отказоустойчивость

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 47 | `ensemble_service.py:96-103` | Partial model failure скрыта — нет поля failed_models/warnings | 2C |
| 48 | `forecast.py:612-618` | forecast_agent.run() без asyncio.timeout — зависает при недоступном LLM | 2C |
| 49 | `cache_service.py:43-45` | /health врёт про Redis (флаг _connected не обновляется после disconnect) | 2C |
| 50 | `Home.tsx:113-116` | Нет retry button при ошибке загрузки на главной странице | 2C |
| 51 | `weather_service.py:94-111` | Нет retry для OpenMeteo — single failure → degraded forecast кэшируется 30 мин | 2C |
| 52 | `client.ts:37-61` | Нет request timeout на фронтенде — fetch висит до браузерного таймаута (300s) | 2C |

### Type Safety

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 53 | `analytics.py:834` + `client.ts:219` | trend nullable / period missing vs non-nullable TS type | 2D |
| 54 | `schemas.py:216` | CompareAllResponse.metrics: dict[str, Any] — нет валидации ML метрик | 2D |
| 55 | `schemas.py:132` | DistrictStats dead model с wrong field names | 2D |
| 56 | `schemas.py:165` | Recommendation model без savings/increase (dead/stale) | 2D |
| 57 | `schemas.py:87,183` | date vs str inconsistency в forecast schemas (ForecastPoint vs EnsemblePoint) | 2D |
| 58 | `analytics.py` (13+ endpoints) | Нет response_model — no server-side API contract enforcement | 2D |

### ML

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 59 | `feature_engineering.py:160` | shift(lag) по индексу строк, не по датам — ошибка при gaps в данных | 3A |
| 60 | `xgboost_service.py:train()` | Нет minimum training size guard — 1 строка для 25+ фичей | 3A |
| 61 | `prophet_service.py:53-58` | Prophet не включает российские госпраздники (NeuralProphet включает) | 3A |
| 62 | `neuralprophet_service.py:226-283` | Trained quantiles [0.1, 0.9] не используются — CI эвристический | 3A |
| 63 | `xgboost_service.py:57-66` | Data hash по first_3/last_5 — изменения в середине данных не детектируются | 3A |

### Парсеры

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 64 | `scheduler.py:68-70, 100-101` | _reindex_chroma из нескольких concurrent tasks — race condition | 1D |
| 65 | `hotels_101hotels.py:132-160` | Нет rate limiting между page requests — IP blocking | 1D |
| 66 | `health_monitor.py:42-50` | count=0 + success=True → error increment → false CRITICAL alerts | 1D |
| 67 | `events_telegram.py:251-271` | LLM call per message — 50-200 вызовов per run, timeout 60s | 1D |
| 68 | `__init__.py:179` | Dedup truncates title to 50 chars — merges distinct events | 1D |

### Инфраструктура

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 69 | `docker-compose.yml:63` | Frontend порт 127.0.0.1:80:8080 (исправлено) | 3C |
| 70 | `docker-compose.yml` | Resource limits заданы для postgres и backend (2G memory) | 3C |
| 71 | `Dockerfile` (backend) | Нет multi-stage build — gcc/g++ в production образе (+200MB) | 3C |
| 72 | `db_service.py:424-430` | save_statistics ON CONFLICT не обновляет max_capacity | 3D |

### Frontend

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 73 | `Chat.tsx:130-136` | SSE AbortError triggers fallback API call + ghost toast | 1C |
| 74 | `Forecast.tsx:479` | Unscoped invalidateQueries() — refetch storm (15+ queries) | 1C |

### Battle Testing

| # | Сценарий | Описание | BT |
|---|----------|----------|----|
| 75 | Турист T-3 | get_weather возвращает текущую погоду, не прогноз (tool limitation) | BT |
| 76 | Атакующий A-1 | Prompt injection — нет anti-injection instructions в system prompt | BT |

---

## MEDIUM (24)

| # | Файл | Описание | Раунд |
|---|------|----------|-------|
| 77 | `llm_service.py:120-142` | Misleading error при неинициализированном LLM сервисе | 1A |
| 78 | `forecast_agent.py:133` | Смешение date объектов и строк в all_dates | 1A |
| 79 | `chroma_service.py:65-67` | get_collection_count/clear/delete не проверяют None | 1A |
| 80 | `main_agent.py:282` | Variable shadowing в TOOLS_BY_NAME | 1A |
| 81 | `ensemble_service.py:28-36` | Веса моделей не персистятся (сбрасываются при рестарте) | 1A |
| 82 | `query.py:96` | SSE response без Cache-Control: no-cache и X-Accel-Buffering: no | 1B |
| 83 | `documents.py:52` | list_documents через empty-string semantic search (не get/peek) | 1B |
| 84 | `query.py:25` | mode parameter принимает любую строку (не Literal["tools", "rag"]) | 1B |
| 85 | `export.ts:47-49` | SVG blob URL не revoke при toBlob failure — memory leak | 1C |
| 86 | `Chat.tsx:36-47` | localStorage parse без shape validation | 1C |
| 87 | `docker-compose.yml:30` | Redis-пароль в CLI healthcheck (виден через docker inspect) | 2A |
| 88 | `docker-compose.yml:8` | Предсказуемые дефолтные пароли (tourism_pass, redis_pass) | 2A |
| 89 | `client.ts:239` + `Analytics.tsx:47` | Fetch 500 hotels, filter client-side (50-100KB wasted) | 2B |
| 90 | `Analytics.tsx:32-73` | 8 concurrent API calls on mount — connection pool contention | 2B |
| 91 | `feature_engineering.py:119-125` | O(n*30) holiday lookups (предвычислить множество) | 2B |
| 92 | `main_agent.py:538` | Unbounded session message size в MemorySaver | 2B |

---

## Приоритезированный план исправлений

### Фаза A — Критические ML-баги (влияют на корректность прогнозов)
1. Fix target leakage в diff features (#1) — `shift(1).diff(d)`
2. Fix target leakage в rolling features (#2) — `shift(1).rolling()`
3. Fix diff fixup off-by-one в test split (#3)
4. Добавить minimum training size guard в XGBoost (#60)
5. Добавить российские госпраздники в Prophet (#61)

### Фаза B — Безопасность (могут быть эксплуатированы)
6. Fix nginx /assets/ headers (#6) — добавить security headers
7. Fix rate limiting в Docker mode (#7) — Docker subnet в TRUSTED_PROXIES
8. Fix rate limit counting rejected requests (#16) — Lua script
9. Fix rate limit per-path bypass (#17) — pattern-based key
10. Добавить client_max_body_size в nginx (#37)
11. Добавить concurrent SSE limit per IP (#38)
12. Добавить HSTS header (#39)

### Фаза C — Event Loop и производительность
13. Async search_hotels/search_events (#4, #5)
14. Fix double NeuralProphet predict (#8)
15. Parallelize analytics DB queries (#10, #11, #40, #46)
16. Combine get_total_metrics into single SQL (#11)
17. Fix compare_models to use async ensemble (#9)

### Фаза D — Отказоустойчивость
18. Добавить SQL query timeout (#12)
19. Wrap ChromaDB init в try/except (#13)
20. Close weather_service session on shutdown (#14)
21. Fix /health при коррупции ChromaDB (#15)
22. Fix /health Redis status (#49)
23. Добавить request timeout на фронтенде (#52)

### Фаза E — Данные и инфраструктура
24. Внедрить Alembic (#25)
25. Fix empty PK в insert_event (#26)
26. Fix save_statistics missing max_capacity (#72)
27. Добавить resource limits в docker-compose (#70)
28. Multi-stage build для backend Dockerfile (#71)

### Фаза F — Тесты
29. Переписать test_security.py на реальный код (#21)
30. Добавить router tests через client fixture (#22)
31. Добавить async тесты (#23)
32. Добавить db_service unit tests (#24)

### Фаза G — UX и мелкие фиксы
33. Fix SSE AbortError в Chat (#73)
34. Scope invalidateQueries в Forecast (#74)
35. Добавить retry button на Home (#50)
36. Добавить get_weather_forecast tool (#75)
37. Добавить anti-injection в system prompt (#76)
