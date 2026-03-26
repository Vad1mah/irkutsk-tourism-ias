# План реализации парсеров

> **Статус: исторический план. Реализация завершена 25.03.2026.**

**Обновлено:** 25.03.2026  
**Статус:** ✅ ВСЕ ОСНОВНЫЕ ФАЗЫ ЗАВЕРШЕНЫ

### Результаты тестирования:
| Источник | Событий | Статус |
|----------|---------|--------|
| Яндекс Афиша | 19 | ✅ |
| Kassir.ru | 17 | ✅ |
| Культура РФ | 20 | ✅ NEW |
| Telegram (6 каналов) | 29 | ✅ |
| Culture38 | 6 | ✅ |
| OpenMeteo (погода) | 28/день | ✅ |
| Zeroevent | ~50 | ✅ (rate limit) |
| **ВСЕГО** | **~150** | ✅ |

---

## ОБЩИЙ ПРОГРЕСС

| Фаза | Описание | Статус | Прогресс |
|------|----------|--------|----------|
| 1 | Улучшение существующих | ✅ Готово | 100% |
| 2 | AI-powered парсинг | ✅ Готово | 100% |
| 3 | Telegram интеграция | ✅ Готово | 100% |
| 4 | VK интеграция | ❌ N/A | — |
| 5 | Погода и доп. данные | ✅ Готово | 100% |
| 6 | Автоматизация (cron) | ✅ Готово | 100% |

---

## ФАЗА 1: Улучшение существующих парсеров ✅

### 1.1 Базовый класс парсера
- [x] Создать `base.py` с общей логикой
- [x] Retry механизм с exponential backoff
- [x] Единый формат логирования
- [x] Rate limiting

### 1.2 Рефакторинг events_irk.py
- [x] Более устойчивый CSS/XPath селекторы
- [x] Fallback стратегии парсинга (через base.py)
- [x] Валидация извлечённых данных (ParsedEvent)

### 1.3 Унификация выходного формата
- [x] Единая схема ParsedEvent для всех парсеров
- [x] Валидация через Pydantic

**Созданные файлы:**
- `backend/app/parsers/base.py` - базовый класс, ParsedEvent, утилиты

---

## ФАЗА 2: AI-powered парсинг ✅

### 2.1 Интеграция Crawl4AI
- [x] Установка: `pip install crawl4ai && crawl4ai-setup`
- [x] Создать `ai_extractor.py` wrapper
- [x] Jina Reader API как бесплатный fallback

### 2.2 Парсер Яндекс Афиши
- [x] Файл: `events_yandex.py`
- [x] URL: `afisha.yandex.ru/irkutsk`
- [x] Данные: название, дата, место, цена, категория
- [x] Метод: Crawl4AI / Jina Reader / HTML fallback

### 2.3 Парсер Kassir.ru
- [x] Файл: `events_kassir.py`
- [x] URL: `irk.kassir.ru`
- [x] Данные: события, площадки, цены
- [x] Метод: Crawl4AI / Jina Reader / HTML fallback

**Созданные файлы:**
- `backend/app/parsers/ai_extractor.py` - Crawl4AI wrapper, Jina Reader
- `backend/app/parsers/events_yandex.py` - Яндекс Афиша
- `backend/app/parsers/events_kassir.py` - Kassir.ru

---

## ФАЗА 3: Telegram интеграция ✅

### 3.1 Получение credentials
- [N/A] Зарегистрировать приложение на my.telegram.org (используется Web Preview fallback)
- [N/A] Получить api_id и api_hash (не требуется для Web Preview)
- [N/A] Добавить в .env: TELEGRAM_API_ID, TELEGRAM_API_HASH (опционально)

### 3.2 Парсер Telegram каналов
- [x] Файл: `events_telegram.py`
- [x] Каналы: @visitirkutskregion, @baikalgo, @baikalgora, @glagol38
- [x] Telethon для MTProto (с авторизацией)
- [x] Web Preview fallback (без авторизации)
- [x] Извлечение событий из текста постов

### 3.3 Расширение на другие каналы
- [x] Конфигурируемый список BAIKAL_CHANNELS
- [x] TelegramChannel dataclass с приоритетами

**Созданные файлы:**
- `backend/app/parsers/events_telegram.py` - Telegram парсер

---

## ФАЗА 4: VK интеграция (не реализована)

### 4.1 Получение токена
- [N/A] Создать Standalone приложение на vk.com/dev (решено не реализовывать — достаточно 8 парсеров)
- [N/A] OAuth авторизация
- [N/A] Добавить токен в .env

### 4.2 Парсер VK
- [N/A] Файл: `events_vk.py` (не реализован — покрытие источников достаточное)
- [N/A] Группы: irk_me, афиша Иркутска
- [N/A] Метод: wall.get с пагинацией
- [N/A] Извлечение событий из постов

---

## ФАЗА 5: Погода и дополнительные данные ✅

### 5.1 OpenMeteo интеграция
- [x] Файл: `weather_openmeteo.py`
- [x] 16-дневный прогноз
- [x] Исторические данные (Archive API)
- [x] Координаты: Иркутск, Листвянка, Ольхон, Байкальск
- [x] Оценка влияния погоды на туризм (get_weather_impact)

### 5.2 Статистика туризма
- [N/A] Файл: `stats_tourism.py` (не реализован — данные агрегируются через analytics endpoints)
- [N/A] Росстат данные (ручной сбор)
- [N/A] Кэширование в PostgreSQL (миграция YDB → PostgreSQL завершена 22.02.2026)

**Созданные файлы:**
- `backend/app/parsers/weather_openmeteo.py` - погода Open-Meteo

---

## ФАЗА 6: Автоматизация

### 6.1 APScheduler
- [x] Установка: `pip install apscheduler`
- [x] Cron-задачи для каждого парсера (`backend/app/scheduler.py`)
- [x] Расписание: события (6ч), отели (2ч), погода (3ч), Telegram (1ч)

### 6.2 Мониторинг
- [x] Логирование успехов/ошибок (`health_monitor.py`)
- [x] Метрики: количество событий, время парсинга
- [x] Алерты при сбоях (health_monitor + structured logging)

---

## ТЕКУЩАЯ ЗАДАЧА

**Статус:** ВСЕ ОСНОВНЫЕ ФАЗЫ ЗАВЕРШЕНЫ ✅

### Реализовано в Фазе 6:
1. ✅ APScheduler для автоматического запуска парсеров
2. ✅ Расписание: события (6ч), отели (2ч), погода (3ч), Telegram (1ч)
3. ✅ Все парсеры протестированы и работают

### Опционально (будущее):
1. Интегрировать VK API (требует токен)
2. Получить Telegram API credentials для Telethon
3. Установить Crawl4AI для улучшенного парсинга

---

## СОЗДАННЫЕ ФАЙЛЫ (12.02.2026)

```
backend/app/
├── scheduler.py          # ✅ НОВЫЙ - APScheduler (автоматизация)
└── parsers/
    ├── __init__.py           # ✅ Обновлён (экспорт всех парсеров)
    ├── base.py               # ✅ НОВЫЙ - базовый класс, ParsedEvent
    ├── ai_extractor.py       # ✅ НОВЫЙ - Crawl4AI, Jina Reader
    ├── anti_detection.py     # ✅ НОВЫЙ - защита от блокировок
    ├── health_monitor.py     # ✅ НОВЫЙ - мониторинг парсеров
    ├── events_yandex.py      # ✅ НОВЫЙ - Яндекс Афиша
    ├── events_kassir.py      # ✅ НОВЫЙ - Kassir.ru
    ├── events_culture_rf.py  # ✅ НОВЫЙ - Культура РФ (12.02.2026)
    ├── events_telegram.py    # ✅ НОВЫЙ - Telegram каналы
    ├── weather_openmeteo.py  # ✅ НОВЫЙ - погода
    ├── events_zeroevent.py   # Существовал
    ├── events_culture38.py   # Существовал
    ├── events_irk.py         # Существовал
    ├── events_major.py       # Существовал
    └── hotels_101hotels.py   # Существовал

docs/
├── PARSERS_RESEARCH.md   # ✅ НОВЫЙ - исследование
└── PARSERS_IMPLEMENTATION_PLAN.md  # ✅ НОВЫЙ - план
```

---

## ЗАМЕТКИ

### Проблемы и решения

| Проблема | Решение |
|----------|---------|
| KudaGo не поддерживает Иркутск | Используем Яндекс Афишу + локальные источники |
| Timepad требует токен | Отложено на фазу 5 |
| Защита от ботов на kassir.ru | Crawl4AI stealth mode |

### Полезные команды

```bash
# Установка AI-парсеров
pip install crawl4ai && crawl4ai-setup
pip install playwright && playwright install

# Тест Crawl4AI
python -c "from crawl4ai import AsyncWebCrawler; print('OK')"
```

---

*Обновляется по мере выполнения задач.*
