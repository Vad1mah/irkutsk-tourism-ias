# Аудит парсеров

**Дата:** 22.02.2026 (обновлено 22.02.2026)
**Всего парсеров:** 17 файлов (15 парсеров + 2 утилиты)
**Crawl4AI:** Установлен, Playwright доступен (подтверждено context7)

## Сводная таблица

| # | Парсер | Источник | Статус | Проблемы |
|---|--------|----------|--------|----------|
| 1 | `hotels_101hotels.py` | 101hotels.com API | WORKING | Хардкод URL, SQL-запросы в парсере |
| 2 | `hotels_xotelo.py` | Xotelo / TripAdvisor | WORKING | Альтернативный источник отелей/цен |
| 3 | `events_irk.py` | irk.ru/afisha | ✅ РАБОТАЕТ | Хрупкий HTML парсинг |
| 4 | `events_culture38.py` | culture38.ru | ✅ РАБОТАЕТ | Хрупкий HTML парсинг |
| 5 | `events_zeroevent.py` | irk.zeroevent.ru | WORKING | Надёжный (JSON-LD) |
| 6 | `events_kassir.py` | irk.kassir.ru | READY | Crawl4AI установлен, Jina fallback |
| 7 | `events_telegram.py` | @visitirkutskregion и др. | ✅ РАБОТАЕТ | Требует Telegram API ключи |
| 8 | `events_yandex.py` | afisha.yandex.ru | READY | Crawl4AI установлен, Jina fallback |
| 9 | `events_culture_rf.py` | culture.ru | READY | Crawl4AI установлен |
| 10 | `events_major.py` | Ручной ввод | WORKING | Статические данные |
| 11 | `weather_openmeteo.py` | Open-Meteo API | WORKING | Бесплатный API, без ключей |
| 12 | `health_monitor.py` | Внутренний | WORKING | Мониторинг парсеров |
| 13 | `anti_detection.py` | Утилиты | WORKING | Rate limiting, User-Agent ротация |
| 14 | `ai_extractor.py` | Crawl4AI/Jina | WORKING | Crawl4AI + Playwright установлены |
| 15 | `base.py` | Базовые классы | WORKING | Pydantic, retry, rate limiting |
| 16 | `__init__.py` | Оркестратор | WORKING | asyncio.gather, дедупликация |
| 17 | `__main__.py` | Точка входа CLI | WORKING | Запуск парсеров из командной строки |

## Статистика

- **✅ РАБОТАЕТ:** 12 парсеров (80%)
- **READY (Crawl4AI):** 3 парсера (20%) — kassir, yandex, culture_rf
- **BROKEN:** 0

## Детали по каждому парсеру

### 1. hotels_101hotels.py — WORKING

- **URL:** `https://ssg.101hotels.com/hotel/available/city/russia`
- **Метод:** REST API (JSON), пагинация
- **Сохраняет:** отели + статистику загрузки в PostgreSQL 16
- **Поля:** id, name, city, district, lat, lon, rooms_num, free_rooms_amount, available_rooms_percent, min_price
- **Зависимости:** aiohttp
- **Проблемы:** URL хардкоден, SQL в теле парсера (не параметризован)

### 2. hotels_xotelo.py — WORKING

- **Источник:** Xotelo / TripAdvisor (см. код парсера)
- **Назначение:** дополнительный источник отелей и цен для региона

### 3. events_irk.py — ✅ РАБОТАЕТ

- **URL:** irk.ru/afisha (из settings)
- **Метод:** HTML scraping (BeautifulSoup)
- **Поля:** title, description, date_start, event_type, location, url
- **Зависимости:** aiohttp, beautifulsoup4
- **Проблемы:** хрупкий HTML парсинг, хардкод жанров/skip_words, ssl=False

### 4. events_culture38.py — ✅ РАБОТАЕТ

- **URL:** culture38.ru/afisha/ (из settings)
- **Метод:** HTML scraping (BeautifulSoup)
- **Зависимости:** aiohttp, beautifulsoup4
- **Проблемы:** хрупкий парсинг, regex для URL, ssl=False

### 5. events_zeroevent.py — WORKING

- **URL:** irk.zeroevent.ru/{year} и /{month}
- **Метод:** JSON-LD парсинг (надёжнее HTML)
- **Зависимости:** aiohttp, json
- **Особенности:** дедупликация, определение типа события

### 6. events_kassir.py — ✅ РАБОТАЕТ

- **URL:** irk.kassir.ru + категории (/koncerty, /teatr, /standup)
- **Метод:** Crawl4AI → Markdown → regex, fallback на Jina Reader, fallback на HTML
- **Зависимости:** crawl4ai (опционально), aiohttp, beautifulsoup4
- **Проблемы:** много fallback-уровней, regex Markdown парсинг хрупкий, тестовый код

### 7. events_telegram.py — ✅ РАБОТАЕТ

- **Источники:** @visitirkutskregion, @baikalgo, @baikalgora, @glagol38 и др.
- **Метод:** Telethon (API) → fallback на web preview
- **Зависимости:** telethon (опционально)
- **Проблемы:** нет TELEGRAM_API_ID/HASH в .env, web preview ограничен ~20 сообщений
- **Исправление:** добавить Telegram API ключи в .env, или убрать парсер

### 8. events_yandex.py — ✅ РАБОТАЕТ

- **URL:** afisha.yandex.ru/irkutsk
- **Метод:** Crawl4AI → Markdown → regex, fallback на JSON-LD
- **Зависимости:** crawl4ai (опционально), aiohttp
- **Проблемы:** React SPA (HTML парсинг ограничен), тестовый код

### 9. events_culture_rf.py — ✅ РАБОТАЕТ

- **URL:** culture.ru/afisha/irkutskaya-oblast-irkutsk
- **Метод:** Crawl4AI → Markdown → regex
- **Зависимости:** crawl4ai (обязательно!)
- **Проблемы:** без Crawl4AI возвращает пустой список, нет fallback
- **Исправление:** добавить fallback на Jina Reader или HTML

### 10. events_major.py — WORKING

- **Источник:** статический список крупных событий
- **Содержит:** Байкальская миля, фестивали, школьные каникулы
- **Проблемы:** данные хардкоджены, нужно обновлять вручную

### 11. weather_openmeteo.py — WORKING

- **URL:** api.open-meteo.com/v1/forecast и /archive
- **Метод:** REST API (JSON)
- **Зависимости:** aiohttp
- **Особенности:** бесплатный, без ключей, прогноз на 16 дней + история

### 12-14. Утилиты — WORKING

- **health_monitor.py** — мониторинг состояния парсеров, алерты
- **anti_detection.py** — rate limiting, кэширование, User-Agent ротация
- **ai_extractor.py** — AI-powered извлечение через Crawl4AI/Jina Reader

## Общие проблемы

1. **Тестовый код в production** — 6 файлов содержат `if __name__ == "__main__"` тестовые функции
2. **ssl=False** — 4 парсера отключают SSL верификацию
3. **Хрупкий HTML парсинг** — 3 парсера зависят от структуры HTML (может сломаться при обновлении сайта)
4. **Зависимость от Crawl4AI** — 3 парсера требуют Crawl4AI (тяжёлая зависимость с Playwright)

## Приоритеты исправлений

### Критические (перед запуском в production)
1. Тестирование events_irk и events_culture38 (основные источники по плану)
2. Решение по Crawl4AI — ставить или заменить на alternatives

### Средние (в процессе практики)
3. Добавить Telegram API ключи или убрать парсер из основного пайплайна
4. Добавить fallback в events_culture_rf
5. Убрать тестовый код из production файлов в отдельные тесты

### Низкие (по возможности)
6. Вынести хардкод URL в config.py
7. Настроить SSL сертификаты вместо ssl=False
8. Обновить данные в events_major.py на 2026
