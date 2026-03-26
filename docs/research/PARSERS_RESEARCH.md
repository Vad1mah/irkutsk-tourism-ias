# Исследование источников данных и технологий парсинга

**Дата исследования:** 15.02.2026  
**Автор:** Студент ВКР  
**Проект:** Веб-сервис анализа туристической активности Байкальского региона

---

## 1. ОБЗОР СОВРЕМЕННЫХ ТЕХНОЛОГИЙ ПАРСИНГА

### 1.1 AI-powered инструменты (новейшие)

#### Crawl4AI
- **Репозиторий:** https://github.com/unclecode/crawl4ai
- **Документация:** https://docs.crawl4ai.com/
- **Статус:** #1 trending на GitHub
- **Возможности:**
  - Конвертация HTML в чистый Markdown для RAG/LLM
  - CSS, XPath и LLM-based extraction strategies
  - Параллельный краулинг с session management
  - Адаптивный краулинг (information foraging algorithms)
  - Stealth mode для обхода защит
- **Установка:** `pip install crawl4ai && crawl4ai-setup`
- **Применимость:** Идеально для извлечения событий с afisha.yandex.ru, kassir.ru

#### Browser-Use
- **Репозиторий:** https://github.com/browser-use/browser-use
- **Звёзды:** 78,000+ GitHub stars
- **Возможности:**
  - AI-агент управляет браузером через natural language
  - Visual Understanding System (анализ DOM + скриншоты)
  - Playwright backend для надёжной автоматизации
  - Поддержка OpenAI, Anthropic, Google, Ollama
- **Установка:** `pip install browser-use && playwright install`
- **Применимость:** Сложные динамические сайты с защитой

#### ScrapeGraph-AI
- **Репозиторий:** https://github.com/ScrapeGraphAI/scrapegraph-py
- **Звёзды:** 22,639+ GitHub stars
- **Возможности:**
  - LLM + граф-логика для интеллектуального парсинга
  - SmartScraperGraph, OmniScraperGraph, SearchGraph
  - Поддержка OpenAI, Gemini, Groq, Anthropic, локальные модели
  - Интеграция с LangChain, Llama Index
- **Установка:** `pip install scrapegraphai` (Python >=3.10)
- **Применимость:** Извлечение структурированных данных из сложных страниц

#### Firecrawl
- **Сайт:** https://firecrawl.dev/
- **Звёзды:** 82,600+ GitHub stars
- **Возможности:**
  - API для конвертации сайтов в Markdown/JSON
  - AI extraction с natural language prompts
  - Обход anti-bot защит, rotating proxies
  - Batch scraping с job tracking
- **Цена:** Free tier (500 страниц), затем платные планы
- **Применимость:** Массовый сбор данных с множества источников

#### Jina Reader API
- **URL:** https://r.jina.ai/
- **Возможности:**
  - Бесплатный API: `https://r.jina.ai/{URL}` → Markdown
  - Поддержка PDF
  - Image captioning для LLM
  - Web search: `https://s.jina.ai/{query}`
- **Цена:** Бесплатно
- **Применимость:** Быстрое извлечение контента без настройки

### 1.2 Browser Automation

#### Playwright (Python)
- **Документация:** https://playwright.dev/python/
- **Возможности:**
  - Chromium, Firefox, WebKit
  - Async/Sync API
  - wait_for_selector, wait_for_load_state, wait_for_response
  - Headless и headed режимы
- **Установка:** `pip install playwright && playwright install`
- **Применимость:** Динамические SPA, JavaScript-heavy сайты

#### Selenium
- **Статус:** Legacy, но всё ещё используется
- **Отличие от Playwright:** Только синхронный API, медленнее
- **Применимость:** Совместимость со старым кодом

### 1.3 Классические инструменты

#### Scrapy
- **Документация:** https://docs.scrapy.org/
- **Версия:** 2.14.1 (поддержка async/await)
- **Возможности:**
  - Асинхронный Twisted-based networking
  - Item pipelines
  - Middleware для прокси, user-agents
  - Distributed crawling
- **Установка:** `pip install scrapy`
- **Применимость:** Масштабный парсинг с pipeline обработки

#### HTTPX + BeautifulSoup
- **Возможности:**
  - Async HTTP клиент с connection pooling
  - asyncio.gather() для параллельных запросов
  - BeautifulSoup для парсинга HTML
- **Установка:** `pip install httpx beautifulsoup4 lxml`
- **Применимость:** Простые статические страницы

#### aiohttp + BeautifulSoup
- **Статус:** Уже используется в проекте
- **Применимость:** Текущие парсеры (101hotels, zeroevent)

### 1.4 Telegram парсинг

#### Telethon
- **Документация:** https://docs.telethon.dev/
- **Возможности:**
  - MTProto протокол (не Bot API)
  - Парсинг публичных каналов
  - iter_messages() для получения постов
- **Требуется:** api_id, api_hash с my.telegram.org
- **Установка:** `pip install telethon`

### 1.5 VK парсинг

#### vk_api
- **Документация:** https://vk-api.readthedocs.io/
- **Методы:** wall.get, groups.getById
- **Требуется:** access_token (Standalone app)
- **Установка:** `pip install vk_api`

---

## 2. ИСТОЧНИКИ ДАННЫХ ДЛЯ ПРОЕКТА

### 2.1 Текущие источники (реализованы)

| Источник | Файл парсера | Метод | Статус |
|----------|--------------|-------|--------|
| 101hotels.com | hotels_101hotels.py | JSON API | ✅ Работает |
| irk.zeroevent.ru | events_zeroevent.py | JSON-LD schema.org | ✅ Работает |
| culture38.ru | events_culture38.py | HTML (BeautifulSoup) | ✅ Работает |
| irk.ru/afisha | events_irk.py | HTML (BeautifulSoup) | ⚠️ Хрупкий |
| Вручную | events_major.py | Статичные данные | ✅ Работает |

### 2.2 Новые источники (к реализации)

#### Приоритет 1 (Высокая ценность)

| Источник | URL | Данные | Рекомендуемый метод |
|----------|-----|--------|---------------------|
| Яндекс Афиша | afisha.yandex.ru/irkutsk | Все события города | Crawl4AI / Playwright |
| Kassir.ru | irk.kassir.ru | Билеты, цены | Crawl4AI / BeautifulSoup |
| Telegram @visitirkutskregion | t.me/visitirkutskregion | Официальные анонсы | Telethon |
| Telegram @baikalgo | t.me/baikalgo | Туристические события | Telethon |

#### Приоритет 2 (Средняя ценность)

| Источник | URL | Данные | Рекомендуемый метод |
|----------|-----|--------|---------------------|
| VK Иркутск | vk.com/irk_me | Городские события | vk_api |
| BaikalTravel | baikaltravel.ru/events | Туры, события Бурятии | aiohttp |
| Telegram @baikalgora | t.me/baikalgora | Горнолыжка | Telethon |
| Telegram @glagol38 | t.me/glagol38 | Культура | Telethon |

#### Приоритет 3 (Дополнительно)

| Источник | URL | Данные | Рекомендуемый метод |
|----------|-----|--------|---------------------|
| Timepad | api.timepad.ru | Бизнес-события | REST API (токен) |
| OpenMeteo | open-meteo.com | Погода 14 дней | REST API |
| Booking.com | booking.com | Цены отелей | Browser-Use (сложно) |

### 2.3 API источники (проверено)

| API | Поддержка Иркутска | Доступ | Статус |
|-----|-------------------|--------|--------|
| KudaGo | ❌ НЕТ | Бесплатный | Не подходит |
| Timepad | ✅ ДА | Требует токен | Возможно |
| 2GIS Places | ✅ ДА | Платный | Не приоритет |
| Jina Reader | ✅ Любой URL | Бесплатный | Рекомендуется |
| OpenMeteo | ✅ ДА | Бесплатный | Рекомендуется |

---

## 3. TELEGRAM КАНАЛЫ РЕГИОНА

### 3.1 Официальные туристические

| Канал | Подписчики | Контент | Частота |
|-------|------------|---------|---------|
| @visitirkutskregion | 1,673 | Официальный туризм | 2-3/день |
| @baikalgo | 1,852 | Туры, места, афиша | 3-5/день |
| @baikalgora | 745 | Горнолыжка, активности | 1-2/день |

### 3.2 Культура и новости

| Канал | Подписчики | Контент | Частота |
|-------|------------|---------|---------|
| @glagol38 | ~1,000 | Культурная жизнь | 2-3/день |
| @OkoloBaikala | ~500 | Информация о Байкале | 1/день |
| @baikal_teleport | ~300 | Новости региона | 2/день |
| @baikal24 | ~2,000 | Новости ИА Байкал24 | 5+/день |

### 3.3 Рекомендации по извлечению

```python
# Паттерны для поиска событий в постах
EVENT_PATTERNS = [
    r'(\d{1,2})\s+(января|февраля|марта|...).*?(концерт|выставка|фестиваль)',
    r'(Когда|Где|Вход):\s*(.+)',
    r'Билеты:?\s*(\d+)\s*руб',
]
```

---

## 4. ТЕХНИЧЕСКИЕ РЕШЕНИЯ

### 4.1 Архитектура парсеров

```
backend/app/parsers/
├── __init__.py           # Экспорт всех парсеров
├── base.py               # Базовый класс парсера
├── # События
├── events_zeroevent.py   # ✅ Существует
├── events_culture38.py   # ✅ Существует
├── events_irk.py         # ✅ Существует
├── events_major.py       # ✅ Существует
├── events_yandex.py      # 🆕 К реализации
├── events_kassir.py      # 🆕 К реализации
├── events_telegram.py    # 🆕 К реализации
├── events_vk.py          # 🆕 К реализации
├── # Отели
├── hotels_101hotels.py   # ✅ Существует
├── # Погода
├── weather_openmeteo.py  # 🆕 К реализации
└── # Утилиты
    └── ai_extractor.py   # 🆕 Crawl4AI wrapper
```

### 4.2 Выбор инструмента по типу источника

| Тип сайта | Инструмент | Причина |
|-----------|------------|---------|
| Статический HTML | aiohttp + BS4 | Быстро, просто |
| JSON API | aiohttp / httpx | Нативная поддержка |
| JavaScript SPA | Playwright | Выполняет JS |
| Защищённый сайт | Crawl4AI / Browser-Use | Stealth mode |
| Telegram | Telethon | MTProto протокол |
| VK | vk_api | Официальный SDK |

### 4.3 Обработка защит от ботов

```python
# Стратегии обхода защит
ANTI_BOT_STRATEGIES = {
    "user_agent_rotation": True,
    "request_delays": (1, 3),  # секунды
    "proxy_rotation": False,   # при необходимости
    "stealth_mode": True,      # Crawl4AI
    "browser_fingerprint": True,  # Playwright
}
```

---

## 5. ПЛАН РЕАЛИЗАЦИИ

### Фаза 1: Улучшение существующих парсеров (1-2 дня)
- [ ] Рефакторинг events_irk.py (более устойчивый парсинг)
- [ ] Добавление retry логики во все парсеры
- [ ] Унификация формата вывода

### Фаза 2: AI-powered парсинг (2-3 дня)
- [ ] Интеграция Crawl4AI
- [ ] Парсер Яндекс Афиши
- [ ] Парсер Kassir.ru

### Фаза 3: Telegram интеграция (1-2 дня)
- [ ] Получение Telegram API credentials
- [ ] Парсер @visitirkutskregion
- [ ] Парсер @baikalgo

### Фаза 4: VK интеграция (1 день)
- [ ] Получение VK API токена
- [ ] Парсер городских пабликов

### Фаза 5: Погода и дополнительные данные (1 день)
- [ ] OpenMeteo интеграция
- [ ] Исторические данные погоды

### Фаза 6: Автоматизация (1 день)
- [ ] APScheduler для cron-задач
- [ ] Мониторинг и алерты

---

## 6. ЗАВИСИМОСТИ

### Новые пакеты для requirements.txt

```txt
# AI-powered scraping
crawl4ai>=0.8.0
browser-use>=0.11.0
scrapegraphai>=1.71.0

# Browser automation
playwright>=1.49.0

# Async HTTP
httpx>=0.28.0

# Telegram
telethon>=1.42.0

# VK
vk_api>=11.9.0

# Scheduling
apscheduler>=3.10.0
```

---

## 7. НАУЧНАЯ ЗНАЧИМОСТЬ

### Для ВКР важно отметить:

1. **Комбинированный подход** к сбору данных:
   - Классические методы (HTML parsing, API)
   - Современные AI-powered инструменты
   - Социальные сети и мессенджеры

2. **Адаптивность системы**:
   - Множество источников снижает риск потери данных
   - AI-extraction устойчив к изменениям вёрстки

3. **Масштабируемость**:
   - Асинхронная архитектура
   - Модульная структура парсеров

4. **Актуальность технологий**:
   - Crawl4AI, Browser-Use — 2025-2026 год
   - LLM-based extraction — передний край

---

## 8. ССЫЛКИ И РЕСУРСЫ

### Документация инструментов
- Crawl4AI: https://docs.crawl4ai.com/
- Browser-Use: https://browser-use.com/
- Playwright Python: https://playwright.dev/python/
- Telethon: https://docs.telethon.dev/
- Scrapy: https://docs.scrapy.org/

### Исследованные источники данных
- irk.zeroevent.ru — афиша Иркутска
- culture38.ru — культура области
- afisha.yandex.ru/irkutsk — Яндекс Афиша
- irk.kassir.ru — билеты
- t.me/visitirkutskregion — официальный туризм
- t.me/baikalgo — туристический проект

---

*Документ будет обновляться по мере реализации парсеров.*
