# DEPLOYMENT.md — Развёртывание ИАС туристической аналитики

> Актуально для: multi-stage Docker, PostgreSQL 16, Redis 7, ChromaDB.
> Дата актуализации: 2026-05-03.

## 1. Минимальные требования к серверу

| Ресурс | Минимум | Рекомендуется | Обоснование |
|--------|---------|---------------|-------------|
| CPU | 2 vCPU | 4 vCPU | Prophet/NeuralProphet при первом прогреве загружают все ядра; XGBoost параллелен |
| RAM | 4 GB | 8 GB | NeuralProphet ~500 MB; Chroma + LangGraph + ensemble-кэш ~2 GB; PostgreSQL buffer ~1 GB |
| Диск | 10 GB | 20 GB | PG ~1–2 GB, Chroma volume ~500 MB, образы ~3–4 GB, логи (json-file × 4 сервиса) ~600 MB |
| ОС | Linux amd64 | Ubuntu 22.04 / Debian 12 | Стек тестирован на amd64 |
| Docker | 24.0+ | 27.0+ | Нужен BuildKit (по умолчанию с 23.0) |
| docker compose | v2.20+ | v2.30+ | Используются `profiles`, `depends_on.condition: service_healthy` |

## 2. Подготовка окружения

### 2.1. Клонирование репозитория

```bash
git clone <repo-url> /opt/tourism
cd /opt/tourism
```

### 2.2. Настройка переменных окружения

```bash
cp backend/.env.example backend/.env
```

Шаблон — `backend/.env.example`. Обязательные переменные для production:

| Переменная | Назначение | Пример |
|------------|------------|--------|
| `DATABASE_URL` | asyncpg-строка к PostgreSQL | `postgresql+asyncpg://tourism:pass@postgres:5432/tourism` |
| `LLM_PROVIDER` | `mistral` (рекомендуется), `gigachat`, `groq`, `deepseek`, `gemini`, `openrouter` | `mistral` |
| `MISTRAL_API_KEY` | API-ключ Mistral (работает из РФ без VPN) | `<your-key>` |
| `REDIS_PASSWORD` | Пароль Redis (должен совпадать со значением в `docker-compose.yml`) | `redis_pass` |
| `API_KEY` | Защита parser/admin endpoints (`X-API-Key`). Пустой = auth выключен (только dev!) | `<random-32-bytes>` |
| `RATE_LIMIT_REQUESTS` | Запросов/мин для rate-limiting | `60` |

> **Geo-замечание:** GigaChat (`gigachat.devices.sberbank.ru`) отвечает только с российских IP. На зарубежных хостингах GigaChat недоступен — использовать Mistral/DeepSeek или российские облака (Yandex Cloud, Cloud.ru).

## 3. Запуск

### 3.1. Только базы (PostgreSQL + Redis)

```bash
docker compose up -d postgres redis
docker compose ps   # postgres и redis должны быть healthy
```

### 3.2. Полный стек (backend + frontend)

```bash
docker compose --profile full up -d
```

Порядок старта управляется `depends_on: condition: service_healthy` — backend ждёт готовности БД и Redis.

### 3.3. Пересборка после изменений кода

```bash
docker compose --profile full build backend
docker compose --profile full up -d backend
```

## 4. Проверка работоспособности

### 4.1. Health-check

```bash
curl http://localhost:8000/health
# {"status":"ok","db_connected":true,"redis_connected":true,...}
```

> Backend в compose биндится на `127.0.0.1:8000` — доступен только локально. Для внешнего доступа поднимать reverse proxy (nginx/caddy) с TLS.

### 4.2. Swagger / ReDoc

```
http://localhost:8000/docs
http://localhost:8000/redoc
```

### 4.3. Frontend

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:80/
# 200
```

### 4.4. Smoke-тест ключевых endpoints

```bash
# Ensemble-прогноз
curl "http://localhost:8000/api/forecast/ensemble?district=Иркутский&days=7"

# KPI B2B-дашборда
curl "http://localhost:8000/api/analytics/kpi"

# RevPAR/ADR
curl "http://localhost:8000/api/analytics/revenue-summary"

# AI-агент
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"text": "Загрузка отелей по Иркутскому району"}'
```

## 5. Бэкап и восстановление

### 5.1. Бэкап PostgreSQL

```bash
docker exec tourism-postgres pg_dump \
  -U tourism -d tourism -Fc \
  -f /tmp/tourism_$(date +%Y%m%d_%H%M%S).dump
docker cp tourism-postgres:/tmp/. ./backups/
```

Рекомендуется ежедневный cron + ротация (хранить 7 дней).

### 5.2. Бэкап ChromaDB

ChromaDB хранится в volume `chroma_data`. Перед бэкапом — остановить backend (избежать corruption при записи):

```bash
docker compose stop backend
docker run --rm \
  -v tourism_chroma_data:/data \
  -v "$(pwd)/backups:/backup" \
  alpine tar czf /backup/chroma_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
docker compose start backend
```

### 5.3. Восстановление PostgreSQL

```bash
docker compose stop backend
docker exec -i tourism-postgres pg_restore \
  -U tourism -d tourism --clean --if-exists \
  < ./backups/tourism_20260503_120000.dump
docker compose start backend
```

## 6. Диагностика и рестарт

### Логи

```bash
docker compose logs -f                    # все сервисы
docker compose logs -f --tail=100 backend # только backend
docker compose logs backend 2>&1 | grep -i "error\|exception\|critical"
```

### Рестарт

```bash
docker compose restart backend                          # мягкий
docker compose stop backend && docker compose start backend  # полный (если lifespan завис)
```

### Ресурсы

```bash
docker stats --no-stream
```

### Типичные проблемы

| Симптом | Причина | Решение |
|---------|---------|---------|
| `Connection refused` на `/health` сразу после старта | Backend ещё проходит warmup (~30 сек: ensemble-кэш, ChromaDB) | Подождать 60 сек, повторить |
| `could not connect to server` в логах backend | PostgreSQL не готов | `docker compose ps` → проверить healthy |
| `WRONGPASS invalid username-password pair` | `REDIS_PASSWORD` в `.env` не совпадает с `command:` в compose | Привести к одному значению |
| `LLM provider error` | Неверный API-ключ или провайдер недоступен | Проверить `LLM_PROVIDER` и соответствующий API-ключ |
| OOM (контейнер killed) | Не хватает RAM | Увеличить `deploy.resources.limits.memory` в compose |
| `chromadb collection not found` после restart | Прогрев `lifespan` ещё идёт | Подождать или вызвать `/api/parser/reindex` с API-key |

## 7. Известные ограничения

### Миграции БД

Alembic настроен (`backend/alembic/env.py`), но автогенерация ревизий пока не сделана. На старте backend вызывает `SQLAlchemy create_all()` — таблицы создаются если их нет, существующие не мигрируются.

**При изменении схемы:**

1. `docker compose stop backend`
2. Применить DDL вручную, **или** дропнуть и пересоздать (потеря данных):
   ```bash
   docker exec -it tourism-postgres psql -U tourism -d tourism \
     -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
   ```
3. `docker compose start backend` — `create_all` поднимет таблицы.
4. Восстановить данные из dump (5.3).

Добавление Alembic-ревизий — направление развития на следующую итерацию ВКР.

### Пробел данных июль–сентябрь 2025

Парсеры были остановлены — за этот период данных нет. Следствие:
- R² моделей отрицательный на горизонте >30 дней.
- Демонстрация — на краткосрочных прогнозах (3–14 дней).
- Архитектура готова к работе с полными данными после восполнения пробела.

## 8. Восстановление данных после простоя backend

Если backend был остановлен >7 дней — APScheduler не запускал парсеры. Данные о размещении за период простоя восстанавливаем из YDB-таблицы старого парсера (`hotels_statistics`):

```bash
cd /opt/tourism/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/import_from_ydb_101hotels.py
```

Скрипт идемпотентен (`ON CONFLICT DO UPDATE`) — безопасно перезапускать. Логирует количество upserted/skipped строк.

После импорта запустить backend — `lifespan` сделает warmup ensemble-кэша и переиндексирует ChromaDB:

```bash
docker compose --profile full up -d backend
docker compose logs -f backend | grep -i "warmup\|ensemble\|cache"
```

События за период простоя восстановить нельзя (внешние источники без истории) — APScheduler пройдёт парсеры событий один раз и догонит то, что доступно.

## 9. Volumes

| Volume | Содержимое | Точка монтирования |
|--------|------------|--------------------|
| `pg_data` | PostgreSQL data | `/var/lib/postgresql/data` |
| `redis_data` | Redis AOF | `/data` |
| `chroma_data` | ChromaDB persist | `/app/chroma_data` |

`docker compose down` сохраняет volumes. Полный сброс с потерей данных:

```bash
docker compose down --volumes
```
