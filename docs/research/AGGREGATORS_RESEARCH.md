# Исследование туристических агрегаторов бронирования

**Дата:** 22 февраля 2026
**Цель:** Найти источники данных об отелях Прибайкалья, сопоставимые с 101Hotels по полноте (загрузка номеров, цены, координаты, рейтинги).

## Эталон: данные 101Hotels SSG API

Endpoint: `https://ssg.101hotels.com/hotel/available/{city|region}/russia/{slug}`

### Данные по отелю

| Поле | Описание | Пример |
|---|---|---|
| id | Уникальный ID отеля | 667475 |
| name | Название | Маяк |
| city_name | Город | Листвянка |
| city_url | Slug города | leestvyanka |
| coords | [lon, lat] | [104.837, 51.867] |
| rating | Рейтинг (0-10) | 9.5 |
| min_price | Мин. цена/ночь (руб.) | 16000 |
| rooms_num | Всего номеров | 72 |
| stars | Звёздность | 4 |
| rooms[] | Массив типов номеров | см. ниже |

### Данные по номеру (rooms[])

| Поле | Описание |
|---|---|
| id | ID типа номера |
| name | Название (Twin Baikal view) |
| capacity | Вместимость |
| free | Свободных номеров |
| min_price | Цена за номер |
| bed_categories | Типы кроватей |
| single_bed | Одноместная кровать (0/1) |

### Покрытие Прибайкалья (проверено 22.02.2026)

**Региональные endpoint-ы:**

| Регион | Slug | Всего отелей | Городов |
|---|---|---|---|
| Байкал | na_baikale | 66 | 22 |
| Иркутская область | irkutskaya_oblast | 161 | 20 |
| **Объединённые** | — | **~200+** | **~30** |

**По городам (из na_baikale):**

| Slug | Отелей | Slug | Отелей |
|---|---|---|---|
| leestvyanka | 16 | huzhir | 12 |
| baikalsk | 9 | nikola | 5 |
| ulan-ude | 3 | turka | 2 |
| suhaya | 2 | sahyurta | 2 |
| goryachinsk | 2 | gremyachinsk | 1 |
| taloe | 1 | murino_1 | 1 |
| utulik | 1 | enheluk | 1 |
| severobaykalsk | 1 | sarma | 1 |
| kurkut | 1 | ust-barguzin | 1 |
| buguldeyka | 1 | maksimiha | 1 |
| vidrino | 1 | mangutay | 1 |

**По городам (из irkutskaya_oblast):**

| Slug | Отелей | Slug | Отелей |
|---|---|---|---|
| irkutsk | 99 | leestvyanka | 19 |
| huzhir | 12 | baikalsk | 12 |
| bratsk | 6 | angarsk | 6 |
| nikola | 5 | sarma | 2 |
| buguldeyka | 2 | sahyurta | 2 |
| kurkut | 1 | agaluy | 1 |
| nizhneudinsk | 1 | ust-kut | 1 |
| sayansk | 1 | shelehov | 1 |
| murino_1 | 1 | utulik | 1 |
| mangutay | 1 | — | — |

## Обнаруженный баг

В `backend/app/constants.py` словарь `CITY_DISTRICTS_EN` содержал неправильные slug-и:

| Было (НЕ работало) | Стало (работает) |
|---|---|
| `listvyanka` → 404 | `leestvyanka` → 19 отелей |
| `khuzhir` → 404 | `huzhir` → 12 отелей |
| `baykalsk` → 404 | `baikalsk` → 12 отелей |
| `olkhon` → 404 | Удалён (нет такого slug-а) |
| `baykal` → 0 результатов | Удалён |

**Результат бага:** парсер собирал данные только по Иркутску (96 отелей), теряя ~60% данных.

## Полный анализ агрегаторов

### Проверка скрытых API (F12-подход)

Для 13 крупнейших сервисов проверены скрытые/внутренние JSON API endpoint-ы.

| Агрегатор | Проверенные endpoint-ы | HTTP статус | Результат |
|---|---|---|---|
| **101Hotels** | /city/{slug}, /region/{slug} | 200 | Открытый JSON API, данные о загрузке |
| **Ostrovok.ru** | /api/v2/, /api/site/serp/v3/, serp.ostrovok.ru | 404 | Всё закрыто, требуется ETG Partnership |
| **Sutochno.ru** | /api/search, /api/v1/, /api/v2/, /graphql | 403 | Полная блокировка |
| **Яндекс.Путешествия** | /api/search/, /api/hotels/, /hotels/search/api | SmartCaptcha | Антибот-защита |
| **Hotellook** | /api/v2/cache, /lookup, /static, /hotels.json | 404 | API требует токен партнёра |
| **Travelpayouts** | /data/hotels.json, /data/cities.json | 403/200 | cities.json открыт, hotels.json закрыт |
| **TVIL.ru** | /api/search, /api/v1/catalog | 200 (HTML) | Нет JSON API, возвращает HTML |
| **Otello.ru** | /api/search | 404 | Нет открытого API |
| **Tropki.ru** | /api/hotels | 403 | Заблокировано |
| **Bronevik.com** | /api/search | 404 | B2B SOAP, требует NDA |
| **Tutu.ru** | /api/search | 200 (HTML) | Нет JSON API |
| **Kvartirka.com** | /api/search | 404 | Нет открытого API |
| **МирТурбаз** | /api/search | 404 | Нет открытого API |

### Полный реестр: 30+ агрегаторов

#### Tier 1 — Открытый API с данными о загрузке

| Агрегатор | База | Покрытие Прибайкалья | Данные о загрузке | Доступ |
|---|---|---|---|---|
| **101Hotels** | ~200k объектов | ~200+ отелей | rooms, free, capacity, price, rating | Открытый JSON |

#### Tier 2 — Крупные агрегаторы (требуют Playwright)

| Агрегатор | База | Покрытие | Данные | Доступ |
|---|---|---|---|---|
| **Ostrovok.ru** | 2.6M объектов, с 2010 | 182+ в Листвянке | Цена, рейтинг, координаты, типы номеров | JS SPA → Playwright |
| **Sutochno.ru** | 390k, с 2011 | 244 в Хужире | Цена, рейтинг, описание, площадь | JS → Playwright |
| **TVIL.ru** | 300k, с 2008 | Неизвестно | Цена, описание, фото | JS → Playwright |

#### Tier 3 — API по заявке / партнёрство

| Агрегатор | Условия | Данные | Оценка |
|---|---|---|---|
| **Travelpayouts/Hotellook** | Free по заявке, 9% конверсия | Цены от 70 агентств | Нет данных загрузки |
| **Яндекс.Путешествия** | Partner API | Полные данные | Самый закрытый |
| **TopHotels.ru** | REST API (сторонний) | Рейтинги, отзывы | Только рейтинги |

#### Tier 4 — Enterprise B2B (NDA + договор)

| Агрегатор | Данные | Условия |
|---|---|---|
| **Bronevik.com** (100k+) | Полные: rooms, rates, availability | SOAP XML, NDA, договор |
| **Ostrovok B2B / ETG APIv3** | Полные: search, availability | Партнёрская регистрация |
| **Booking.com Demand API** | Полные вкл. occupancy | Партнёрство, рос. карты не работают |

#### Tier 5 — Не подходят

| Агрегатор | Причина |
|---|---|
| Т-Путешествия (Тинькофф) | Нет API для отелей |
| ОтEllo (1.8M, Сбер) | Нет публичного API |
| OneTwoTrip (2M+) | Нет свободного API |
| Tutu.ru | Нет API для отелей |
| Ozon Travel (3M+) | Нет API для внешних |
| МТС Travel | Нет API |
| Тропки (МТС) | Поисковик, не агрегатор |
| LevelTravel | Пакетные туры |
| TezTour | Международные туры |
| Fun&Sun | Туроператор |
| Дельфин | Туроператор, санатории |
| Мультитур | Туроператор |
| Путевка.ком | Санатории / курорты |
| МирТурбаз | Только базы отдыха |
| Trip.com | Международный |
| Skyscanner | Мета-поиск, перелёты |
| Авито | Маркетплейс, нет структурированных данных |
| 60 минут | Почасовые отели, только Москва |
| BaikalBooking.ru | Мало объектов, нет API |
| WorldHotels.ru | ~63 объекта в Листвянке (HTML), нет API |
| ЖилиБыли | Нет API |
| Квартирка (70k) | Нет API, только квартиры |

---

## Глубокое исследование (Этап 2 — 22.02.2026)

### Новые обнаруженные API-источники

#### Xotelo — бесплатный API цен отелей (ГЛАВНАЯ НАХОДКА)

**URL:** https://xotelo.com
**Тип:** RESTful JSON API, данные из TripAdvisor + OTA
**Авторизация:** Не требуется для `/list`, `/rates`, `/heatmap`
**Ограничения:** `/search` — только через RapidAPI

**Проверенные endpoint-ы:**

| Endpoint | Метод | Авторизация | Статус |
|---|---|---|---|
| `/api/list?location_key=KEY` | GET | Нет | 200 OK |
| `/api/rates?hotel_key=KEY&chk_in=DATE&chk_out=DATE` | GET | Нет | 200 OK |
| `/api/heatmap?hotel_key=KEY&chk_out=DATE` | GET | Нет | Недоступен |
| `/api/search?query=TEXT` | GET | RapidAPI | 401 |

**Покрытие Прибайкалья (проверено 22.02.2026):**

| Локация | TripAdvisor Key | Отелей |
|---|---|---|
| Иркутск | g298527 | **480** |
| Листвянка | g298528 | **111** |
| Иркутская область | g2323984 | **1262** |

**Данные с `/list` endpoint:**
- name — название отеля
- key — hotel_key (формат `g{location}-d{hotel}`)
- accommodation_type — тип (Hotel, Small Hotel, Cottage, Inn, Tourist Base)
- geo.latitude, geo.longitude — координаты
- review_summary.rating — рейтинг (0-5)
- review_summary.count — количество отзывов
- mentions — теги (Mid-range, Business, Romantic и т.д.)
- merchandising_labels — метки (Breakfast included и т.д.)
- image — URL фото
- url — ссылка на TripAdvisor

**Данные с `/rates` endpoint:**
- rates[].code — код OTA (BookingCom, Expedia, Agoda и т.д.)
- rates[].name — название OTA
- rates[].rate — цена за ночь/номер
- currency — валюта (поддерживает RUB)

**ПРОБЛЕМА:** Для российских отелей `/rates` возвращает пустой массив `rates: []`. Причина: большинство международных OTA (Booking.com, Expedia, Agoda) ограничили работу с Россией из-за санкций. Тем не менее, данные с `/list` (480+ отелей с координатами и рейтингами) ценны для cross-reference.

**Вывод по Xotelo:** Использовать `/list` для получения метаданных отелей (рейтинги, координаты, типы, фото), cross-reference с 101Hotels для сопоставления данных. Цены пока недоступны для российских отелей.

---

#### SerpAPI Google Hotels (250 бесплатных запросов/мес)

**URL:** https://serpapi.com/google-hotels-api
**Тип:** REST API, парсинг Google Hotels
**Бесплатный тариф:** 250 запросов/месяц
**Данные:** цена, рейтинг, отзывы, фото, координаты, удобства

```python
import requests
params = {
    "engine": "google_hotels",
    "q": "Irkutsk hotels",
    "check_in_date": "2026-07-01",
    "check_out_date": "2026-07-02",
    "currency": "RUB",
    "api_key": "YOUR_KEY"
}
response = requests.get("https://serpapi.com/search", params=params)
data = response.json()
```

**Вывод:** Хороший источник для периодических снапшотов цен Google Hotels. 250 запросов/мес — достаточно для ежедневного мониторинга ~8 отелей или еженедельного — ~35 отелей.

---

#### LiteAPI (бесплатный Sandbox)

**URL:** https://liteapi.travel
**Тип:** REST API, 2M+ отелей
**Бесплатный тариф:** Sandbox (тестовый ключ), Production — нужна кредитная карта
**Данные:** rooms, rates, availability, cancellation policies, amenities

**Вывод:** Требует credit card для Production. Для академического проекта — Sandbox для тестирования достаточен.

---

#### Makcorps Hotel API (30 дней бесплатно)

**URL:** https://makcorps.com
**Тип:** REST API, данные из 200+ сайтов бронирования
**Бесплатный тариф:** 30-дневный триал
**Endpoint-ы:** `/hotel`, `/city`
**Данные:** цены с Booking.com, Expedia, Hotels.com и др.

**Вывод:** Полезен для одноразового исследования цен за 30 дней триала. Можно собрать исторические данные для обучения моделей.

---

### Уточнённые данные по ранее исследованным агрегаторам

#### Ostrovok.ru / ETG / RateHawk — уточнения

- **Postman Workspace:** найден публичный workspace ETG (Emerging Travel Group) с коллекциями запросов:
  - `Hotels Search Engine Results Page`
  - `Hotel Data Dump`
  - `Hotel Incremental Data Dump`
  Доступ к содержимому требует аутентификации в Postman.

- **RateHawk Sandbox (Q4 2025):** Бесплатный sandbox для тестирования с mock-данными. Регистрация на ratehawk.com/registration. Тестовый API-ключ ограничен бронированием демо-отеля (ID `8473727` или `test_hotel_do_not_book`).

- **Python SDK:**
  - `EmergingTravel/papi-sdk-python` (MIT, 8 stars) — официальный SDK для ETG APIv3
  - `gurza/etg-python-sdk` (MIT) — альтернативный SDK
  Оба поддерживают Ostrovok.ru, B2B.Ostrovok.ru, RateHawk.com, ZenHotels.com.

- **Рекомендация:** Зарегистрироваться как партнёр RateHawk (бесплатно), получить sandbox-ключ, протестировать поиск отелей Прибайкалья. Если данных достаточно — интегрировать через papi-sdk-python.

#### Sutochno.ru — уточнения

- **GitHub парсеров:** Не найдено ни одного проекта.
- **API:** Полностью закрыт (все `/api/*` endpoint-ы — 403).
- **Единственный вариант:** Playwright/Crawl4AI headless browser. Данные на сайте: цена, описание, площадь, фото, координаты, рейтинг.

#### Яндекс.Путешествия — уточнения

- **Internal API endpoints (F12-approach):**
  - `/api/hotels/searchOffers` — SmartCaptcha
  - `/api/hotels/hotelInfo` — SmartCaptcha
  - `/api/hotels/search` — SmartCaptcha
  - `/api/hotels/reviews` — SmartCaptcha
  Все защищены SmartCaptcha, недоступны без headless browser + captcha solving.

- **Яндекс Карты JS API:** Бесплатный (25,000 запросов/день). Даёт базовую инфо: название, адрес, координаты, категория. Не даёт цены и занятость.
- **Яндекс XML Search:** ~1000 бесплатных запросов/день. Даёт ссылки на страницы отелей в поиске.
- **Коммерческий Places API:** от 195,000 ₽/год — не для учебного проекта.

#### Bronevik.com — уточнения

- 80,000–100,000 объектов в базе
- **SOAP XML API** (не REST)
- Требует: заявка → NDA → подключение
- Нет GitHub SDK для Python

#### Hotellook/Travelpayouts — уточнения

- Бесплатный доступ по заявке (support@travelpayouts.com)
- Требования: 9% конверсия поиск→бронирование, 5% кнопка→покупка
- Rate limit: 200 req/hour
- **Booking.com данные НЕДОСТУПНЫ** через этот API (требования бренда)
- Поддержка: cityId, hotelId, IATA codes
- Ответ через `searchId` — до 15 минут!

#### Apify Booking.com Scrapers

- `cloud9_ai/booking-hotel-scraper` — от $2/1000 результатов
- `runtime/booking-scraper` — $29/мес
- Данные: цена, рейтинг, отзывы, удобства, фото
- **Бесплатный триал** есть, но ограничен

---

## Итоговая матрица источников данных

### По доступности (от простого к сложному)

| # | Источник | Стоимость | Данные | Покрытие | Приоритет |
|---|---|---|---|---|---|
| 1 | **101Hotels SSG API** | Бесплатно | Загрузка, цены, координаты, рейтинги | 200+ отелей | **ОСНОВНОЙ** |
| 2 | **Xotelo /list API** | Бесплатно | Рейтинги, координаты, типы, фото | 1262 объекта | **CROSS-REF** |
| 3 | **SerpAPI Google Hotels** | 250 req/мес free | Цены, рейтинг, удобства | По запросу | МОНИТОРИНГ |
| 4 | **Makcorps** | 30 дней free | Цены с 200+ сайтов | По запросу | ОДНОРАЗОВО |
| 5 | **RateHawk Sandbox** | Бесплатно (mock) | Search, availability | Тест | ТЕСТ |
| 6 | **LiteAPI Sandbox** | Бесплатно (mock) | Rooms, rates | Тест | ТЕСТ |
| 7 | **Travelpayouts** | По заявке | Цены от 70 OTA | Широкое | ПО ЗАЯВКЕ |
| 8 | **Ostrovok.ru** | Playwright | Цены, рейтинг, типы | 180+ | ПОСЛЕ Crawl4AI |
| 9 | **Sutochno.ru** | Playwright | Цены, описание, площадь | 244+ | ПОСЛЕ Crawl4AI |

### По типу данных

| Тип данных | 101Hotels | Xotelo | SerpAPI | Makcorps |
|---|---|---|---|---|
| Загрузка номеров | **✅** (free rooms) | ❌ | ❌ | ❌ |
| Цены | **✅** | ❌ (РФ) | ✅ | ✅ |
| Координаты | **✅** | **✅** | ✅ | ❌ |
| Рейтинг | **✅** | **✅** (TripAdvisor) | ✅ (Google) | ❌ |
| Типы номеров | **✅** | ❌ | ✅ | ✅ |
| Фото | ❌ | **✅** | ✅ | ❌ |
| Отзывы | ❌ | ✅ (count) | ✅ | ❌ |
| Удобства | ❌ | ❌ | ✅ | ❌ |

## Выводы (обновлённые)

1. **101Hotels — основной и единственный источник данных о загрузке номеров** (ни один другой API не предоставляет поле `free rooms` бесплатно).

2. **Xotelo — ценный дополнительный источник метаданных.** 1262 объекта в Иркутской области с координатами, рейтингами TripAdvisor, типами размещения и фото. Cross-reference с 101Hotels позволит обогатить данные.

3. **SerpAPI Google Hotels — мониторинг цен.** 250 запросов/мес достаточно для еженедельных снапшотов по ключевым отелям для валидации прогнозов.

4. **Makcorps — 30-дневный сбор исторических цен.** Полезен как одноразовый инструмент для создания обучающего датасета по ценам.

5. **RateHawk Sandbox** — стоит зарегистрироваться для изучения возможностей ETG API и оценки их данных по Прибайкалью.

6. **Playwright-парсеры (Ostrovok, Sutochno)** — отложены до установки Crawl4AI / стабильного интернета.

## Рекомендованный план интеграции

### Фаза 1 (текущая неделя)
- ✅ Региональный парсинг 101Hotels (200+ отелей)
- Написать парсер Xotelo `/list` для cross-reference
- Зарегистрировать SerpAPI (бесплатный ключ)

### Фаза 2 (следующая неделя)
- Написать парсер SerpAPI Google Hotels для мониторинга цен
- Зарегистрироваться на RateHawk, получить sandbox-ключ
- 30-дневный триал Makcorps для сбора цен

### Фаза 3 (после установки Crawl4AI)
- Парсер Ostrovok.ru через Playwright
- Парсер Sutochno.ru через Playwright
- Подать заявку на Travelpayouts API
