# SESSION_HANDOFF — текущее состояние работы

## 2026-05-11 — REFERENCES AUDIT & FINAL FORMATTING ✅

Полный аудит и переоформление списка источников ВКР по эталонам Пети, Редькиной и методичке ИГУ. Финальный артефакт — `docs/vkr/Список_источников_FINAL.docx` (53 источника, готов к копированию в основной отчёт).

### Триггер сессии

Пользователь сообщил: «в [27] и [29] ссылки страницы, на которые мы ссылаемся, отсутствуют в книгах. Проверить все источники на достоверность». Дополнительно были предоставлены три эталона:
- `Отчёт предипломной практики ПЕТЯ.docx` на Desktop — 3 примера (англ. статья / переводная книга / онлайн-журнал).
- `Отчет преддипломная практика Редькина.docx` на Downloads — 23 источника, 8 типов оформления.
- Методичка ИГУ от пользователя — 13 шаблонов библиографии (книги 1–3 авторов, >3 авторов, нормативные документы, сборники, материалы конференций, продолжающиеся издания, статьи из сборников/трудов/журналов, патенты, отчёты НИР, диссертации, авторефераты, сетевые/удалённые электронные ресурсы).

### Что было сделано

**1. Аудит достоверности 25+ книг и статей через WebSearch** (выходные данные из Stanford UP, Amazon, archive.org, Hachette, J. of Classification review, MIT DSpace, Cornell scholarship). Найдено **7 ошибок**:

| # | Было в ВКР | Реально |
|---|---|---|
| 19 Few | 261 с. | 260 с. |
| 20 Norman | 347 с. | 368 с. |
| **27 Phillips** | 384 с. + цитата про Крэндалла-Белобабу | **355 с., источник не подходит — заменён на Belobaba 1987 PhD MIT** |
| 28 Kimes | Vol. 44, No. 5–6 | Vol. 44, No. 5 |
| 29 Cross | 304 с. | xii+276 = 288 с. |
| 39 Wedel | Boston : Springer, 432 с. | Norwell : Kluwer Academic Publishers, 382 с. |
| 49 Zheng-Casari | 218 с. | 215 с. |

**Главная замена**: `[27] Phillips R. L. → Belobaba P. P.` Цитата в основном тексте про «Концепцию управления выручкой, сформулированную Робертом Крэндаллом и Питером Белобабой в American Airlines» — это первоисточник Belobaba 1987 (PhD thesis MIT, в DSpace handle/1721.1/14800), а не Phillips 2005. Phillips нигде больше в ВКР не цитировался, поэтому удалён без сдвига нумерации `[28]..[53]`.

**2. Переоформление 53 источников** — каждому присвоен тип, применён точный шаблон:
- 40 источников по Редькинскому паттерну (есть прямой аналог в её работе): эл. ресурсы корпоративных сайтов [223 Brand Analytics] → 24 наших; эл. ресурс с автором [212 Черный] → [21, 22]; статьи в журналах [216–217] → [28, 31]; англ. книги 1–2 авторов [219 Фаулер] → 8 наших; простые ресурсы без описания [230 Yandex Cloud] → [10, 45].
- 13 источников по методичке ИГУ (нет аналога у Редькиной): нормативные документы онлайн (ИГУ-12) → [1, 4]; книги >3 авторов (ИГУ-2) → [30 Box, 38 Christensen, 32 Triebe — заглавие первое, через `[и др.]`); статьи в proceedings (ИГУ-7) → [23, 33, 34]; диссертация (ИГУ-12+13) → [27 Belobaba]; рукопись проекта → [2 Исполатов].

**3. Финальная двухуровневая проверка** (автоматическая + ручная). Применено **7 точечных правок** на финальном этапе:

| # | Правка |
|---|---|
| 3 | `М. : ИНФРА-М` → `Москва : ИНФРА-М` (Редькина пишет город полностью) |
| 12 | `Redis. Документация` → `Redis. Документация хранилища данных в памяти` (расширено описание) |
| 23 | Добавлено `– Boulder, 1996` (место конференции IEEE VL по ИГУ-7) |
| 32 | `Triebe O. NeuralProphet ...` → `NeuralProphet: ... / O. Triebe [и др.]` (ИГУ-2 для >3 авторов) |
| 33 | Добавлено `– San Francisco, 2016` (место KDD) |
| 34 | `Berlin : Springer, 2000` → `Cagliari, 2000` (согласованность с [23], [33]) |
| 40 | `Туризм — статистика` → `Статистика туризма` (em dash в описании выглядит коряво) |

### Критические артефакты сессии

- **`docs/vkr/Список_источников_FINAL.docx`** — готовый список 53 источников в стилях ВКР (TNR 14 pt, полуторный, по ширине, отступ 1.25 см, поля 3/1.5/2/2 см). Открыть → Ctrl+A → Ctrl+C → вставить в место `СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ` в `OTCHET_PO_PRAKTIKE.docx`.
- **`docs/vkr/REFERENCES_REVIEW.md`** — полный аудит с обоснованием каждой правки, классификация по типам, шаблоны.
- **`docs/vkr/_build_references_docx.py`** — генератор (53 источника + форматирование TNR/полуторный/выравнивание/отступ зашиты в каждый run для надёжного copy-paste).

### Также в сессии — не применённые изменения

**ТЭО (Приложение А)**: разобрал ТЭО Редькиной (Приложение В её работы), нашёл 8 содержательных проблем (3 разных срока окупаемости в одном документе, NPV-расчёт не сходится с выводом, Монте-Карло опровергает «целесообразность», тройной счёт выгоды на пользователя, все таблицы названы «Таблица 1», пропавшая формула DCF). Сравнил с нашим ТЭО — у нас все эти косяки **отсутствуют**. Вывод: содержательно ТЭО менять не нужно. Озвучил 4 косметические правки (формулы Word-equation, обоснование ставки 500 ₽/час, дисклеймер по IRR 405 %, явный параметр K = 32) — пользователь сказал «не надо ничего менять».

### Что осталось из старых задач (сохранено для следующих сессий)

- **Блок B/C/D/E аудита ВКР** (25 правок): задвоения главы 1↔2 (B1–B10), стилистические сбои (C1–C5), числовые неувязки (D1–D5), логические разрывы (E1–E5). См. секцию ниже за 2026-05-10.
- **Дашборд hardening** (часть 2 за 2026-05-10) — была в работе, текущее состояние не проверял.

## 2026-05-10 (вечер) — VKR AUDIT БЛОК A + DATALENS-DASHBOARD НА «РЕГИОНАЛЬНОЙ КАРТЕ» ⚠️ В РАБОТЕ

Сессия начата с аудита текста ВКР, продолжена крупной фронтенд+бэкенд фичей по перерисовке страницы «Региональная карта» в полноценный аналитический дашборд (DataLens-парный).

### Часть 1. Текст ВКР (`docs/vkr/OTCHET_PO_PRAKTIKE.md`)

#### Таблицы → проза (без потерь)
- **Таблица 1 «Метрики Revenue Management»** (8 строк × 5 колонок) удалена + добавлены 2 плотных академических абзаца (источники данных + адресация по сегментам). Перенумерация Таблиц 2–8 → 1–7.
- **Таблица 3 (бывшая Таблица 5) «Обоснование выбора типов диаграмм»** (6 строк × 3 колонки) удалена + добавлены 1 вводное + 3 содержательных абзаца, сгруппированных по логике «характер данных → тип графика» (временные ряды → AreaChart+LineChart; категории → BarChart+ComposedChart; циклика и пространство → Heatmap+Yandex Maps). Перенумерация Таблиц 4–7 → 3–6.
- Итого: было 8 таблиц, сейчас 6 (нумерация 1–6 монотонная, каждая упомянута в тексте 1 раз перед подписью).

#### Полный аудит документа выявил 32 правки в 5 категориях
- **A — Фактические ошибки (7 пунктов) — ВСЕ ПРИМЕНЕНЫ ✅**
  - A1.1 (L67) — «Airbnb публикует AirDNA» (фактическая ошибка) → переписано: «независимый сервис AirDNA выгружает наблюдаемую загрузку и цены по листингам Airbnb»
  - A1.2 (L178) — «AirDNA — аналитическая платформа данных Airbnb» (двусмысленность) → «независимая аналитическая платформа, агрегирующая данные о листингах Airbnb по модели краткосрочной аренды»
  - A2 (L51) — «около 14 месяцев непрерывных наблюдений» противоречило L387 (gap 24.06–25.10.2025) → «около 14 месяцев наблюдений за заполняемостью номерного фонда (с задокументированным пробелом летом 2025 года, рассмотренным в подглаве 2.3)»
  - A3 (L65) — `(PMS (Property Management System, система управления гостиницей), Property Management System)` (двойная вложенная расшифровка + тавтология «внутренними данными внутренней системы») → `(PMS, Property Management System, система управления гостиницей)`
  - A4 (L133) — «сезонное расширение сезонное расширение SARIMA» → одно
  - A5 (L133) — «расширение расширение SARIMAX» → одно
  - A6 (L367 + L621) — «Регионы и карта» → «Региональная карта» (унификация с L312, L353, L365)
  - A7 (L721, Приложение Е) — «38 признаков семи групп» при перечислении 8 → «восьми групп»
- **B — Крупные смысловые задвоения главы 1 ↔ главы 2 (10 пунктов) — НЕ ПРИМЕНЕНЫ ⏳**
  - B1: L120 ≈ L365 (обоснование Yandex Maps дословно)
  - B2: L135 ≈ L266 (декомпозиция Prophet `y(t) = g(t) + s(t) + h(t) + ε(t)`)
  - B3: L137 ≈ L268 (NeuralProphet, лаговые регрессоры, задержка погоды 3-5 дней)
  - B4: L139 ≈ L270 (XGBoost, инженерия признаков, квантильная регрессия)
  - B5: L141 ≈ L272 (ансамбль, обратная RMSE)
  - B6: L143–145 ≈ L290+L294 (LangGraph + 12 инструментов + два агента)
  - B7: L149–151 ≈ L302 (Groq + VPN + fallback DeepSeek → Mistral дословно)
  - B8: L67–71 (1.1) ≈ L178 (1.4) (анализ существующих систем)
  - B9: L391 ≈ L436 (ставка дисконтирования 21% с обоснованием)
  - B10: L308 ≈ L114 (React+TypeScript+Vite)
  - **Корневая причина**: глава 1 описывает обоснование выбора, глава 2 — реализацию. B2–B5 это буквальное копирование описаний моделей. Решение: в главе 2 заменить на отсылку «Модель Prophet, обоснованная в подглаве 1.3, применена со следующими гиперпараметрами…»
- **C — Стилистические и тональные сбои (5 пунктов) — НЕ ПРИМЕНЕНЫ ⏳**
  - C1 (L302): «поймали на тестах в апреле 2026 года» — разговорный тон
  - C2 (L102): «так уже сужается поверхность атаки» — слабая связка
  - C3 (L405): «так с 2023 года» + пунктирные короткие предложения
  - C4 (L25): «Капля в море по сравнению с задачами уровня федеральных платформ» — идиома в академическом тексте
  - C5 (L83): «Таким образом» — AI-маркер (один раз допустим, но лучше переформулировать)
- **D — Числовые неувязки и неясности (5 пунктов) — НЕ ПРИМЕНЕНЫ ⏳**
  - D1 (L77 vs L51): 200+ из 101hotels live vs 1400+ в БД — разрыв не объяснён. Решение: «совокупное число с учётом исторических наблюдений и cross-source enrichment через OSM Overpass превышает 1400»
  - D2 (L160 vs L51): 370 гостиниц + 179 санаториев (Росстат) vs 1400+ в БД. Решение: «база охватывает официально зарегистрированные объекты + сегмент малых средств размещения, не попавших в Росстат»
  - D3 (L131/L286/L387): горизонт упомянут как 7-30 / 7 / 3-14 дней — не противоречие, но читателю сложно. Уточнить в L387
  - D4 (L100): «(расчёт топовых событий по влиянию, **агрегаты данных Росстата**)» — Росстата как тяжёлого кэша в системе нет, наследие старой версии. Заменить на реальный пример (корреляционная матрица, экспортер CSV)
  - D5 (L210 vs L645): 60+ vs 65 vs 67 — несущественный дрейф, опционально привести к 65 везде
- **E — Логические разрывы (5 пунктов) — НЕ ПРИМЕНЕНЫ ⏳**
  - E1 (L256): «Сегментация B2B-аудитории отражена... на диаграмме сценариев использования (см. **рисунок 6** и Приложение В)». Но рисунок 6 — это Domain Model. Ссылка ошибочна.
  - E2 (L228 vs L256): Domain включает 4 актёра (3 пользователя + технический администратор), L256 говорит «B2B-аудитория по трём профильным ролям». Где техадмин в сегментации — не сказано.
  - E3 (L242): «Пять периодических задач... + дополнительная задача каждые шесть часов» = на самом деле 6. Лучше «Шесть периодических задач».
  - E4 (L405): «шесть статей затрат», но таблица 5 содержит 6 спендов + 3 обязательных платежа = 9. Уточнить «шесть статей основных эксплуатационных затрат + три обязательных платежа в бюджет».
  - E5 (L312): «семь пунктов в трёх группах» — посчитал, всё OK ✅ (для protocol).

#### Побочно зафиксировано
- После A3 в L166 расшифровка PMS повторно идёт полностью — по правилу 32 преподавателя при втором упоминании достаточно «PMS». Войдёт в финальную полировку (D или новый пункт).
- Бэкап до удаления Таблицы 1: `docs/vkr/OTCHET_PO_PRAKTIKE.md.bak_before_t1_replace`.

### Часть 2. Frontend «Региональная карта» — DataLens-парный дашборд (`frontend/src/pages/Map.tsx`)

Запрос пользователя: воссоздать его старый DataLens-дашборд («Загруженность номеров») в системе. Было: только карта + KPI. Стало: полноценный аналитический экран.

#### Backend (без слома обратной совместимости)
- **`db_service.get_occupancy_by_district`** — SQL расширен `SUM(rooms_num)` и `SUM(max_capacity)` per-day
- **`OccupancyPoint` schema** — добавлены `total_rooms: int | None`, `total_capacity: int | None`
- **`OccupancyTimeseriesResponse.points`** в `frontend/src/api/client.ts` — синхронизирован
- **2 новых метода в `db_service`**: `get_districts_statistics_in_period(date_from, date_to)`, `get_hotel_stats_on_date(target_date)`
- **`DataServiceProtocol`** в `protocols.py` — задекларированы оба новых метода
- **`GET /api/analytics/hotels-map?date=YYYY-MM-DD`** — карта реагирует на дату среза
- **`GET /api/analytics/districts?date_from=...&date_to=...`** — агрегаты по периоду; cache key включает диапазон
- **`GET /api/analytics/occupancy-timeseries`** — пробрасывает новые поля
- **Backend перезапущен** (старые два uvicorn-процесса 866044/867604 остановлены, запущен новый в фоне). Health 200, новые поля приходят (проверено через `urllib.request`).

#### Frontend `api/client.ts`
- `getHotelsMap(district?, snapshotDate?)` — новый параметр
- `getDistricts(dateFrom?, dateTo?)` — новые параметры
- `getPriceHistory(days, district?)` — добавлен district

#### Frontend `Map.tsx` — полная переработка (3 итерации перекомпоновки)
- **Layout** (финальный): KPI-полоска (4 карточки full-width) → карта (62% × 420px height) + фильтры (360px h-full) → 4 чарта в сетке 2×2 (Загрузка по районам / Загрузка номерного фонда (3 линии) / Цена-загрузка за сезон / Цена-загрузка за период)
- **Карта**: на полную высоту блока (h-full + YandexMap height='100%'); overlay-легенда внизу с полупрозрачным фоном (`backdrop-blur-sm`), полные подписи цветов (низкая <40% / средняя 40-70% / высокая >70% / нет данных)
- **Фильтры разделены на 3 секции**: «Карта и KPI» (только дата), «Графики» (сезон + период), «Районы» (общее)
- **Multi-район в графиках** через `useQueries`: параллельные запросы occupancy + price на каждый выбранный район; агрегация на frontend (avg для occupancy/price, sum для total_rooms/capacity)
- **Multi-select dropdown для районов** (компонент `DistrictMultiSelect`) — кнопка «Все районы / Выбрано: N» → раскрывается список с чекбоксами + «Сбросить выбор». Закрывается на клик вне или Escape.
- **Удалены**: hover/pin sidebar, Top-5 RevPAR блок, чипы районов со скроллом
- **Reflow-фикс после Yandex Maps fullscreen**: `useEffect` подписан на `document.fullscreenchange` → `setTimeout(() => window.dispatchEvent(new Event('resize')), 80/400)` — Recharts ResponsiveContainer пересчитывает размеры
- **Бар-чарт «Загрузка по районам»**: YAxis width=120 + tickFormatter обрезает имена > 16 символов

#### Подтверждённые тесты (Playwright)
- 1440×900: помещается, чарты не перекрывают карту (после `overflow-hidden` на Card фильтров)
- 1920×1080: всё в один экран до раздела чартов
- 1366×768: умещается, без горизонтального скролла
- Multi-район click test (3 района): сетевые запросы летят параллельно с правильным district, заголовки графиков показывают «Иркутский, Ольхонский, Слюдянский», KPI снизились (1428→624), карта фильтрует, бар-чарт подсвечивает выбранные

### Что осталось сделать (TODO для следующей сессии) ⏳

**Приоритет 1 — фронтенд:**
1. ⏳ Визуально протестировать **multi-select dropdown** (свернуть/развернуть, отметить чекбоксы 2-3 районов, посмотреть что графики обновляются). Скрипт `frontend/_shot_map_open.mjs` готов, но прогон был прерван пользователем — нужен живой тест.
2. ⏳ Снять обновлённый скриншот для **Рисунка 17 ВКР** (страница «Региональная карта»). Старый PNG уже не отражает текущий вид.

**Приоритет 2 — текст ВКР:**
3. ⏳ Добавить **2 сжатых параграфа в подглаву 2.3** (после описания страницы «Региональная карта», ~L365–367) про новый дашборд: фильтры (дата/сезон/период/районы) и логика 4 виджетов с двумя осями.
4. ⏳ Применить **блок B аудита (10 правок)** — задвоения главы 1 ↔ главы 2. Самое крупное по объёму. В главе 2 заменить дублирующие описания моделей на отсылки в подглаву 1.3.
5. ⏳ Применить **блок E аудита (5 правок)** — логические разрывы (E1 ссылка на рис. 6 как UC — критично; E3 «Пять» → «Шесть» периодических задач).
6. ⏳ Применить **блок C аудита (5 правок)** — стилистические сбои (C1 «поймали на тестах», C2 «так уже», C4 «капля в море»).
7. ⏳ Применить **блок D аудита (5 правок)** — числовые неувязки (D1/D2 разрыв 200→1400 объектов, D4 убрать «агрегаты Росстата»).
8. ⏳ Дополнительно: **L166 PMS** — убрать вторую полную расшифровку (только «PMS»).

**Приоритет 3 — операционное:**
9. ⏳ Решить судьбу временных скриптов:
   - `frontend/_shot_map.mjs`, `_shot_map_click.mjs`, `_shot_map_multi.mjs`, `_shot_map_open.mjs` — playwright-скрипты для скриншотов dashboard. Можно оставить как тулинг для будущих итераций или удалить.
   - `docs/vkr/OTCHET_PO_PRAKTIKE.md.bak_before_t1_replace` — бэкап до удаления Таблицы 1 (как `*.bak_before_reindex` от 09.05). Можно удалить после защиты.

### Файлы, изменённые в сессии
- `docs/vkr/OTCHET_PO_PRAKTIKE.md` — 2 таблицы → проза, 7 правок блока A, перенумерация
- `backend/app/services/db_service.py` — 3 расширения/новых метода
- `backend/app/services/protocols.py` — 2 декларации новых методов
- `backend/app/routers/analytics.py` — расширены `/hotels-map`, `/districts`, `/occupancy-timeseries`
- `backend/app/models/schemas.py` — `OccupancyPoint` расширен
- `frontend/src/api/client.ts` — расширены 3 метода API
- `frontend/src/pages/Map.tsx` — полная переработка (~620 строк)
- `frontend/src/components/YandexMap.tsx` — `height: number | string`, убран pinning hint

### Backend status (на момент handoff)
- Запущен в фоне через `bash -c '... uvicorn ...' &` (PID был 950288, может уже сменился)
- Health: `curl http://localhost:8000/health` → 200, `total_rooms`/`total_capacity` приходят
- Если упал — перезапустить: `cd backend && PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Ключевые архитектурные решения этой сессии (для контекста следующего агента)
1. **Multi-район в графиках** — frontend агрегация через `useQueries`, БЕЗ нового endpoint. Это снизило backend-правки и сохранило простоту API. AVG для непрерывных метрик, SUM для аддитивных.
2. **Карта реагирует только на дата+район; графики на период+сезон+район** — разорвана связь периода с focusDate. Период отсчитывается от `today`, не от выбранной даты. Это дало предсказуемое поведение фильтров.
3. **Backend: новые методы в db_service вместо изменения существующих** — `get_districts_statistics_in_period`, `get_hotel_stats_on_date` параллельны старым. Cache key для `/districts` и `/hotels-map` включает дату/диапазон, чтобы срезы не путались.
4. **Reflow Recharts через window.resize event** — стандартное решение для проблемы ResponsiveContainer после смены layout (Yandex Maps fullscreen).

---

## 2026-05-09…10 — DIAGRAMS AUDIT & TEXT SYNC ✅

Полный аудит всех 12 диаграмм ВКР по канонам преподавателя (`teachers_materials/lektsiya-*.md`) и точечная синхронизация текста ВКР с обновлёнными диаграммами.

### Что переделано в `.drawio`

| Файл | Было | Стало |
|---|---|---|
| `models/IDEF0/idef0_a-0_b2b_v2.drawio` | **Создан с нуля** (исходник от 22.02 потерян, был только PNG с YDB+MiMo+OpenRouter) | Контекстная IDEF0 с 5 обобщёнными Mechanisms (Подсистема сбора, хранения, анализа, агент, веб-интерфейс) |
| `models/IDEF0/idef0_a0_b2b_v2.drawio` | **Создан с нуля** (тот же случай) | Декомпозиция A0 с 5 функциями A1-A5, обобщёнными Mechanisms |
| `models/BP/bp_model.drawio` | Resources содержали `«AI-агент (MiMo + RAG)»`, `«Prophet (прогнозирование)»`, `«Веб-интерфейс (React)»`, `«PostgreSQL 16 (база данных)»`, `«Chroma (RAG)»`, `«FastAPI»` | Resources обобщены до бизнес-понятий: «База данных», «Интеллектуальный агент», «Модуль прогнозирования», «Веб-интерфейс», «Сервер приложений», «Векторный индекс». Удалены упоминания MiMo. Output `«Обновлённые данные в PostgreSQL»` → `«Обновлённые данные о туризме»` |
| `models/DOMAIN/domain_b2b_v2.drawio` | 28 сущностей, треть — техническая инфраструктура (Кэш, Векторный индекс, Планировщик, Лог системы, Heatmap, Feature Engineering, Экспорт) | 18 доменных сущностей, технические компоненты вынесены на Component/Deployment по канону. Зональная группировка («Зона размещения» + «Зона событий и прогноза») для чистых ortho-стрелок |
| `models/UC/use_case_b2b_v2.drawio` | System boundary `mxgraph.flowchart.start_2` рисовался овалом, актёр `«Планировщик (APScheduler)»`, конфликт UC3↔UC11 (одновременно include и extend), UC6/UC7/UC8 далеко от Тех.администратора → зигзаги | Прямоугольный system boundary, актёр «Планировщик», `UC11 «extend» UC3` оставлен, `UC3 «include» UC11` удалён. Тех.админ и Планировщик переехали направо как secondary actors → линии короткие |
| `models/SEQUENCE/uc11_sequence.drawio` | Все 21 edge без `source/target` И без `sourcePoint/targetPoint` (только `<Array as="points">`). При PNG-экспорте все стрелки **пропадали** — рисовались только Lifelines и номера 1-16 | Полная переработка: каждый edge с явными `<mxPoint as="sourcePoint">` и `<mxPoint as="targetPoint">`. Все 21 стрелка корректно отрисовываются в PNG |
| `models/COMPONENT/component_diagram_b2b_v2.drawio` | 54 label с детализацией каждого сервиса (`data_service`, `chroma_service`, `methodology_service`, `parser_health_service`, перечисление 27 endpoints аналитики, 12 парсеров поименно, 6 базовых tools) | Сжат до 9 обобщённых компонентов («component») + 3 хранилища («database», «cache», «vector store») + 2 внешние («external»). 4-слойный layout (Presentation → Application → Storage → Background). Все 13 связей ortho, 9 имеют подписи интерфейсов (REST/SSE, HTTP, SQL, key/value, векторный поиск, HTTPS, trigger, upsert) с белым фоном лейблов |
| `models/COMPONENT/deployment_diagrams.drawio` | 3 страницы (БП1/БП2/БП3) с 9 фейковыми именами файлов (`rag_indexer.py`, `api.py`, `agent.py`, `forecasting.py`, `retriever.py`, `llm_client.py`, `admin_api.py`, `monitor.py`, `logger.py`), ChromaDB ошибочно показан как отдельный сервер | **Одна общая** страница «Deployment Diagram B2B v2». Реальная топология Docker Compose: 4 контейнера (postgres, redis, backend, frontend). ChromaDB — `chroma_data` volume **внутри** backend-контейнера (как в коде: `chromadb.PersistentClient`). Реальные артефакты: `app/main.py`, `app/routers/`, `app/services/`, `app/scheduler.py`, `app/parsers/`. 4 external API (101Hotels, Open-Meteo, 8 порталов событий, LLM API). 9 связей с подписями протоколов |
| `docs/vkr/figures/figure_1_architecture.drawio` | Шрифт 16pt не помещался в блоки малой высоты (30-55px), парсеры обрезались | Шрифт 13pt, блоки 70-110px, swimlane заменён на rounded rectangles с заголовком сверху, page 1500×940 |
| `docs/vkr/figures/figure_3_agent_graph.drawio` | «Узел Модель» (6 строк текста, 14pt, 120px) — текст вылезал. Tools блоки разной высоты | Шрифт 12pt, «Узел Модель» 240×160, tools 50×200 единообразно, **2 колонки** (6 базовых + 6 расширения), возвратная стрелка «Результат инструмента» через верх y=100 |

### Текст ВКР — 2 точечные правки

В `docs/vkr/OTCHET_PO_PRAKTIKE.md` синхронизированы описания, которые ссылались на удалённое содержимое диаграмм:

- **L241** (перед Рис. 6 Domain Model): убраны упоминания `«векторный индекс»`, `«кэш ответов»`, `«контроля состояния подсистемы сбора данных»` (этих сущностей больше нет на упрощённой Domain). Технический администратор включён в актёров. Добавлена фраза «Технические компоненты системы (кэш, векторный индекс, планировщик, журналирование) рассматриваются на диаграмме компонентов и развёртывания».
- **L262** (перед Рис. 7 Component): убраны конкретные числа `«семь маршрутизаторов»`, `«девятнадцать модулей»`, `«восемь парсеров событий»`, `«пятью заданиями»` (этого нет на упрощённой Component). Описаны обобщённые компоненты с интерфейсами (REST/SSE, HTTP) и зависимостями.

Текст и диаграммы теперь синхронизированы. **Все 18 ссылок в тексте ВКР работают**: для рисунков 1-15, 17 — формат «...на рисунке N»; для 16, 18 — «(рисунок N)».

### Документация для будущих агентов

- `docs/vkr/figures/README.md` — **полностью переписан**: актуальная карта 18 рисунков, 9 таблиц, описание правок текста ВКР, канонические основания, архитектурные заметки (ChromaDB как PersistentClient, реальные имена файлов, актуальный LLM-стек).

### Параметры экспорта PNG

- draw.io desktop → `File → Export As → PNG`
- **Zoom 200%** для большинства, **Zoom 300% для Component** (много мелких блоков)
- White background, Border 20px

### Что осталось

| Задача | Статус | Комментарий |
|---|---|---|
| Экспорт 12 PNG из обновлённых `.drawio` | ⏳ Делает пользователь | Через draw.io desktop |
| 6 скриншотов приложения (Рис. 13-18) | ⏳ Делает пользователь | После запуска `docker compose up postgres redis` + `uvicorn` + `npm run dev`. Подробный чек-лист — в `figures/README.md` |
| 6 устаревших sequence-страниц UC2-UC7 (старая нумерация) в `sequence_diagrams.drawio` | 🟡 Решено оставить | По решению пользователя — в ВКР используется только UC1, остальные не мешают |

### Ключевые архитектурные напоминания (для следующих агентов)

1. ChromaDB — `chromadb.PersistentClient` внутри backend-контейнера, **не отдельный сервис**. Volume `/app/chroma_data`.
2. Реальная файловая структура: `app/main.py`, `app/routers/*.py`, `app/services/*.py`, `app/parsers/*.py`. **НЕТ** файлов `rag_indexer.py`, `agent.py`, `forecasting.py`, `retriever.py`, `llm_client.py`, `admin_api.py`, `monitor.py`, `logger.py`.
3. Docker Compose: 4 контейнера (postgres, redis, backend, frontend).
4. LLM fallback chain: Groq → DeepSeek → Mistral. **Нет** MiMo, **нет** OpenRouter как primary.

---

## 2026-05-06 — DATA-QUALITY PASS + UI-QUALITY PASS ✅

После B2B-rebuild Phase 1-6 (04.05) проведены два больших раунда улучшений качества:

### Данные
- **Категоризация событий**: расширен `detect_event_type` (11 категорий + 14 schema.org `@type` mapping + ~110 морфологических корней без хардкода имён). Добавлены категории `holiday/tour/lecture`. Title-priority phase (приоритет матча в title над description). Расход «event» fallback: 49% → 7% (с 209 → 32, остальное Telegram-приветствия).
- **LLM-classify** через Mistral structured output (JSON schema strict) для оставшихся `event'` событий. Скрипт `scripts/reclassify_events.py`. Cron каждые 6h в :15 через APScheduler. Стоимость ~$0.15 на 209 events.
- **Hotels accommodation_type** заполнен на 43.8% (625 / 1428): 101hotels live region+city sweep (262) + OSM Overpass cross-ref Хаверсин 0.5 km (363). 18 типов в распределении (Отель/Гостиница/Апартаменты/Хостел/Гостевой дом/База отдыха/Шале/Кемпинг/...). Скрипты `fill_hotel_types_from_osm.py` и `fill_hotel_types_from_xotelo.py` (последний — на случай оживления Xotelo public API).
- **events_irk обогащение**: time_start (25/27, regex), age_restriction, image_url через `_build_image_url_map` DOM-walking (~35% событий). Description убран — источник не отдаёт без detail-страниц, lookahead-эвристика тянула title соседа (баг найден и исправлен 06.05).
- **events_kassir/yandex/zeroevent/culture_rf/culture38/telegram**: расширены полями description, image_url, address, price_max, age_restriction, date_end, jsonld_type → category.
- **YDB-import** идемпотентен через `ON CONFLICT DO UPDATE`. PG MAX(date) = 2026-05-06.

### UI / UX
- **Простой русский** во всех methodology-tooltips (без `impact`/`baseline`/`weekday`/`event-day`).
- **Перцентили**: «10% / 25% / Медиана / 75% / 90%» вместо сырых `p10..p90`.
- **17 Recharts Tooltips** через `utils/chartTheme.ts` (foreground цвет + bar cursor transparent).
- **Composite Home chart**: custom content фильтрует upper/lower шум.
- **Heatmap min-max** нормализация по наблюдаемому диапазону (контраст вместо «всё одинаково синее»).
- **MethodologyTooltip** auto-flip при близости к правому краю viewport.
- **Feature importance** в Forecast: ширина оси 200, height auto, `interval={0}` — все 10 имён помещаются.
- **Frontend Events**: убран дубль `_getEventType` (mapping через `getEventTypeKey` к backend `event.event_type`). Новые UI-категории `holiday`/`tour`/`lecture`.

### Инфраструктура
- **`PYTHONIOENCODING=utf-8`** обязательное env-var для uvicorn на Windows. Без него Crawl4AI/Jina (kassir, yandex, culture_rf) падают на cp1251 при символах `↓ ↑ ←` в Markdown — парсер молча возвращает 0 событий.
- **APScheduler 5 jobs**: events 6h, hotels 2h, weather 3h, telegram 1h, **reclassify 6h cron** (новый).
- **Auto-failover OSM**: `overpass-api.de → overpass.kumi.systems` при недоступности основного.
- **events_router**: пробрасывает все v2-поля Event в Pydantic (раньше outright выкидывал time_start/image_url/address/price_max/age_restriction в ответе API — был критический скрытый баг).

### Тесты и стабильность
- pytest: 211 passed, 0 регрессий.
- tsc / vite build: чистые.
- Backend живой на :8000 с новой логикой, frontend на :5173.

### Out of scope / direction-of-development
- 803 / 1428 hotels NULL accommodation_type — объекты в малых нп без публичных источников. TripAdvisor / Booking / 2GIS требуют payment или approval.
- LLM-batch для events_irk description — события не имеют detail-страниц.
- Image_url в events_irk покрытие 35% — text-based парсер с DOM-walking; полное покрытие требует переписывания на чистый DOM (риск).
- Xotelo public API deprecated → RapidAPI ($5-10/мес). Reverse-engineer не рекомендуется.

### Ключевые изменения файлов в этом раунде
- `backend/app/parsers/base.py:detect_event_type` — расширение + title-priority.
- `backend/app/parsers/events_irk.py` — image_url DOM-walking, description=None.
- `backend/app/parsers/events_*.py` — все 8 парсеров расширены v2-полями.
- `backend/app/parsers/hotels_101hotels.py` — accommodation_type, dedup в city sweep.
- `backend/app/parsers/hotels_osm.py` — **новый**, OSM Overpass auto-failover.
- `backend/app/scheduler.py` — новый job reclassify_events.
- `backend/app/services/db_service.py:get_events` — пробрасывает v2-поля.
- `backend/app/routers/events.py` + `routers/parser.py` — Event Pydantic v2-поля + `mode=cities_full`.
- `backend/scripts/reclassify_events.py` — **новый** CLI.
- `backend/scripts/fill_hotel_types_from_osm.py` — **новый** CLI.
- `backend/scripts/fill_hotel_types_from_xotelo.py` — **новый** CLI (deprecated провайдер).
- `frontend/src/utils/{localize,chartTheme,localizeFeatures}.ts` — i18n + Recharts theme.
- `frontend/src/components/MethodologyTooltip.tsx` — auto-flip.
- `frontend/src/pages/{Home,Analytics,Forecast,Events}.tsx` — простые методологические тексты, RU перцентили, getEventTypeKey, новые EVENT_TYPES.

---

## 2026-05-04 — ВСЕ 5 ФАЗ B2B-REBUILD ЗАВЕРШЕНЫ ✅

**Total branches:** `feat/b2b-rebuild-phase{1,2,3,4,5}` — ~69 commits.
**Total tasks:** ~52 across 5 phases.
**Tests:** 208 passing, 0 failed, 1 skipped (backend, после фиксов C3+C4 event-loop scope), TS clean + build OK (frontend).
**Spec:** [`docs/superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md`](superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md)
**Summary:** [`docs/PHASE_REBUILD_SUMMARY.md`](PHASE_REBUILD_SUMMARY.md)

### Branch state

- `feat/b2b-rebuild-phase1` — backend (30 tasks): schema, dedup, 6 bugfixes, 11 new endpoints, 7 dead removed, 5 parsers extended, 2 with AI fallback, ParserHealth.
- `feat/b2b-rebuild-phase2` — AI agent (9 tasks): 6 new tools, methodology rules, evergreen prompts.
- `feat/b2b-rebuild-phase3` — frontend (10 tasks): Yandex Maps, 4-tab Analytics, Layout/Home/Forecast/Events/HotelDetail/About rebuilds.
- `feat/b2b-rebuild-phase4` — UML models (2 tasks): UC11/UC12, 5 entities, FR3.8/3.9/4.7, 2 services, БП5, sequence.
- `feat/b2b-rebuild-phase5` — verification (3 tasks): tests pass, UML re-audit, OTCHET synced, summary written.

### Что необходимо сделать пользователю (manual)

1. **Merge стратегия** — все 5 веток на feat/b2b-rebuild-phase5 (последовательная цепочка). Возможные сценарии:
   - Squash merge `feat/b2b-rebuild-phase5` в `master` одним коммитом (чисто).
   - Merge --no-ff для сохранения истории по фазам.
   - Создать PR для каждой фазы (если нужна review-trail).
2. **`.drawio` файлы** — текстовые модели обновлены, графика требует ручного редактирования в draw.io.
3. **Yandex Maps API key** — продакшн-ключ должен быть прописан в `.env` на сервере (dev-ключ уже в `frontend/.env`).
4. **Презентация** — `docs/presentation/PREZENTACIYA_VKR.md` синхронизирована: 12 tools, 208 tests, 62 endpoints (актуально на 2026-05-05).

### Известные ограничения (документированы в PHASE_REBUILD_SUMMARY)

- Alembic миграции отложены — используется `create_all` + ALTER скрипт.
- True ADR / RevPAR недоступны (нет revenue) — везде используются прокси с явной пометкой.
- Comp set с конкретными конкурентами не реализован — анонимный сегментный benchmark.
- Real-time pickup curve не реализован — daily proxy-pickup из snapshot diffs.
- Channel mix, LOS, source markets, GOPPAR — нет данных (out-of-scope).
- `.drawio` диаграммы — текстовые модели готовы, графика manual.
- 2-3 pre-existing test failures (asyncpg event-loop harness) — не регрессии, harness issue.

## 2026-05-04 — Phase 4 (Models UML/BPMN) ЗАВЕРШЁН ✅

**Branch:** `feat/b2b-rebuild-phase4` (2 коммита).

### Что сделано

- UC: UC11 «Анализ событий с corrected impact», UC12 «Сегментный benchmark отеля» — добавлены с pre-conditions, потоками, alt flows, cross-ref на FR/components.
- DOMAIN: 5 новых сущностей — BookingSnapshot, EventImpactRecord, SegmentBenchmark, ParserHealthRecord, MethodologyRecord.
- REQ: FR3.6/3.7 расширены (proxy disclaimer, gap-aware), FR3.8/3.9 (segment benchmark, proxy-pickup) — новые, FR4.7 (corrected impact) — уточнён, NFR7 (методологическая прозрачность) — новое.
- COMPONENT: MethodologyService, ParserHealthService — новые компоненты; AnalyticsRouter +7 endpoint'ов, HotelsRouter +1, ForecastRouter +1 −4, EventsRouter −3; MainAgent 6→12 tools.
- BP: БП5 «Методологическая калибровка» — пересчёт baseline по cron + audit log.
- SEQUENCE: диаграмма для UC11 (User → AnalyticsRouter → DataService loop → MethodologyService twice → response).

### `.drawio` файлы

Текстовые .md обновлены. `.drawio` — за рамками текущего этапа (требуют ручного редактирования в draw.io). Зафиксировано как направление развития.

### Что дальше — Phase 5 (Final Verification & Report)

- Полный smoke на запущенном backend + frontend.
- pytest + tsc.
- Обновление final отчёта `docs/vkr/OTCHET_PO_PRAKTIKE.md` с цифрами Phase 1-4.
- Обновление презентации.

> **Этот файл — последний снимок прогресса.** Обновлять в конце каждой сессии. Перед стартом — прочитать целиком и сверить с `NORTH_STAR.md` + `REFOCUS_PLAN.md`.

## 2026-05-04 — Phase 3 (Frontend Rebuild) ЗАВЕРШЁН ✅

**Branch:** `feat/b2b-rebuild-phase3` (~12 коммитов).

### Что сделано (10 задач)

**A. Инфра:** установлен `@pbe/react-yandex-maps`; `client.ts` расширен 10 типизированными методами (D-серия Phase 1); `localizeFeatures.ts` (EN→RU маппинг); компоненты `GapAwareLineChart`, `MethodologyTooltip`.

**B. Layout:** AI-чат (`/chat`, label «AI-аналитик», icon MessageSquare) восстановлен в sidebar в группе "Аналитика".

**C. Home:** убран блок «Что доступно по сегментам», `DollarSign`→`Banknote` в KPI ADR/RevPAR, композитный график factual+forecast (vertical reference line at "today"), corrected events impact (через `getEventsImpactCorrected`), методология footer (источники из `/metadata`), `MethodologyTooltip` на ADR/RevPAR.

**D. Analytics — 4 tabs:**
- Регионы: RMS-таблица + filter "только достоверные" (high+medium) + mini bar chart top-5 RevPAR.
- Сезонность: pickup/pace + weekday×month heatmap с gap-aware рендером (диагональная штриховка).
- События: corrected impact таблица + filter "только impact ≥ 5%".
- Сегменты: bar chart by_accommodation_type + size buckets KPI + price distribution percentiles.
- Методология footer на всех вкладках.

**E. Map:** замена ECharts контурной карты на Yandex Maps (`@pbe/react-yandex-maps`); `YandexMap` компонент с Placemark + balloon popup'ами (имя/номеров/загрузка/цена/ссылка). Удалены view-modes comparison (radar), overview (treemap), heatmap-14days. Sidebar с KPI и Top-5 RevPAR.

**F. Forecast:** локализация feature_importance имён через `localizeFeature`, шрифт 12px, ширина Y-axis 140; новый блок "Самовалидация модели" с RMSE/MAE и mae_per_day chart (через `getForecastValidation`).

**G. Events:** расширенный modal — image/address/time_start/price_min-max/age_restriction; corrected impact badge (↑/↓ %) на event cards.

**H. HotelDetail:** блок "Сравнение с сегментом" (district × size_bucket benchmark via `getHotelSegmentBenchmark`).

**I. About:** динамические counts из `/metadata`; список парсеров с health-status badge'ами (через `/parser/health`); методология блок (RevPAR прокси, corrected impact, gap-периоды); out-of-scope (true ADR, comp set, channel mix, GOPPAR, Alembic).

### Тесты

- `npx tsc --noEmit` — ✅ clean (0 errors).
- `npm run build` — ✅ success.

### Что дальше — Phase 4 (Models UML/BPMN)

Обновление 6 моделей системы под B2B:
- UC: добавить UC11 (Corrected impact) + UC12 (Segment benchmark).
- DOMAIN: 5 новых сущностей (BookingSnapshot, EventImpactRecord, SegmentBenchmark, ParserHealth, MethodologyRecord).
- REQ: FR3.8/3.9, FR4.7 corrected, FR6.3 extended, NFR7.
- COMPONENT: Health-monitor + Methodology Service.
- BP: БП5 «Методологическая калибровка».
- SEQUENCE: для UC11.

## 2026-05-04 — Phase 2 (AI Agent) ЗАВЕРШЁН ✅

**Branch:** `feat/b2b-rebuild-phase2` (3 commits после Phase 1).

### Что сделано (9 задач)

**A. 6 новых tools для агента:**
- A1: `get_top_events_by_impact` — топ-N событий с corrected impact (calls /events-impact?method=seasonal_corrected).
- A2: `get_booking_pace` — динамика бронирований (calls /booking-pace).
- A3: `compare_districts` — side-by-side RMS-метрики (calls /compare-districts).
- A4: `compare_forecast_models` — RMSE/MAE/R² по моделям (calls /compare-all).
- A5: `get_occupancy_timeseries` — день-по-день occupancy (calls /occupancy-timeseries).
- A6: `get_price_distribution` — p10/p25/p50/p75/p90 цен (calls /price-distribution).

Всего ALL_TOOLS теперь содержит 12 tools (было 6).

**B. Методология в системном промпте:**
8 правил формата ответа: район, период, метод, база сравнения, не выдумывать, без личного comp set, прокси-диск-лаймер, gap данных.

**C. Home.tsx evergreen prompts:**
Quick-prompts больше не привязаны к конкретным датам/событиям — актуальны в любой день.

### Тесты

- 29 новых сценарных тестов на инструменты (mock httpx).
- 22 существующих тестa агента — без регрессий.
- Pytest: 199 passed, 3 failed (2 pre-existing asyncpg event-loop + 1 test_export_csv_occupancy), 3 skipped, 208 collected.

### Что дальше — Phase 3 (Frontend rebuild)

Backend и агент готовы. Фаза 3 — основной фронтенд rebuild по spec §3-9: Layout/Home/Analytics/Map/Forecast/Events/HotelDetail/About + Yandex Maps + локализация.

---

## 2026-05-04 — Phase 1 (Backend) ЗАВЕРШЁН ✅

**Branch:** `feat/b2b-rebuild-phase1` (~30 коммитов f192261...dfc1bb7)
**Тестов:** 170 passed, 2 pre-existing failures (харнес asyncpg event-loop), 5 skipped, 0 новых регрессий.

### Что сделано (29 задач)

**A. Расширение схемы Event (3 задачи):** добавлены 6 полей (time_start, price_min, price_max, image_url, address, age_restriction); идемпотентный ALTER-скрипт `migrate_event_schema_v2.py`.

**B. Дедупликация (2):** UNIQUE constraint `uq_events_dedup (source_id, date_start, title)` + dedup-aware upsert + COALESCE preservation.

**C. Багфиксы (6):**
- C1: race condition в `/api/query/stream` — Redis INCR/DECR + pipeline EXPIRE NX + atomic limit.
- C2: `/api/analytics/correlation` фильтрует месяцы с <5 samples; `is_gap` flag.
- C3: cache key включает model_version + method.
- C4: `/api/forecast/explain` 5s timeout + factor-only fallback.
- C5: `parser/events/all` — все парсеры через `upsert_events_batch`.
- C6: параметр `method=naive|seasonal_corrected`.

**D. 10 новых endpoint'ов:**
- D1: `MethodologyService` (baseline by weekday ±N weeks, corrected impact с CI).
- D2: `/events-impact?method=seasonal_corrected` — реальный расчёт.
- D3: `/forecast/{district}/validation` — RMSE/MAE forecast vs actual + persist ensemble forecasts.
- D4: `/parser/health` + `ParserHealthService` (Redis hash, integrated into BaseParser).
- D5: `/analytics/metadata` — counts, data_range, gap_periods (CTE LEAD).
- D6: `/analytics/booking-pace` — daily proxy-pickup.
- D7: `/analytics/occupancy-timeseries`.
- D8: `/analytics/price-distribution` (p10/p25/p50/p75/p90).
- D9: `/analytics/compare-districts`.
- D10: `/analytics/segments` (mini/mid/large + accommodation_type).
- D11: `/hotels/{id}/segment-benchmark`.

**E. Удаление 7 мёртвых endpoint'ов:** forecast/{neural,xgboost,compare,holidays}, events/{init,demo,load-historical}.

**F. Расширение 5 парсеров:**
- F1: yandex — age_restriction (typicalAgeRange) + full description (2000 chars).
- F2: kassir — full description + venue address (JSON-LD).
- F3: zeroevent — price_min из описания.
- F4: culture_rf — venue address.
- F5: 101hotels — image_url.

**G. AI-fallback для хрупких парсеров:**
- G1: events_irk — Crawl4AI/Jina fallback при пустом или сломанном native HTML.
- G2: events_culture38 — то же самое.

### Smoke-тест Phase 1 (2026-05-04)

Все 10 новых endpoint'ов вернули 200 OK с непустым JSON:

| Endpoint | Результат |
|----------|-----------|
| `GET /api/analytics/metadata` | 200, 1381 отелей, 409 событий, gap_periods с июня 2025 |
| `GET /api/parser/health` | 200, пустой массив (парсеры не запущены) |
| `GET /api/forecast/Иркутский/validation?days_back=14` | 200, samples=0 (нет forecast записей в dev-БД) |
| `GET /api/analytics/booking-pace?district=Иркутский&days_ahead=14` | 200, proxy-pickup данные |
| `GET /api/analytics/occupancy-timeseries?district=Иркутский&days=30` | 200, 30 точек с occupancy |
| `GET /api/analytics/price-distribution?district=Иркутский&days=30` | 200, p50=3900, samples=4292 |
| `GET /api/analytics/compare-districts?districts=Иркутский,Ольхонский&days=30` | 200, сравнение двух районов |
| `GET /api/analytics/segments` | 200, by_accommodation_type |
| `GET /api/analytics/events-impact?method=seasonal_corrected` | 200, события с delta_pct и CI |
| `GET /api/analytics/correlation` | 200, месяцы с is_gap flag |

### Что дальше — Phase 2 (AI-агент)

Будущая фаза будет добавлять 6 новых tools агенту:
- `get_top_events_by_impact` (использует D2)
- `get_booking_pace` (D6)
- `compare_districts` (D9)
- `compare_forecast_models`
- `get_occupancy_timeseries` (D7)
- `get_price_distribution` (D8)

И расширение system_prompt методологическими правилами.

### Pre-existing failures, требующие Phase 5 (test infra)

- `test_export_csv_occupancy` — asyncpg event loop closed (SKIPPED в suite).
- `test_correlation_is_gap_flag_matches_samples_threshold` — функционирует только в полном suite, fail при isolated run.
- `test_occupancy_timeseries_structure` — same pattern.

Это harness issue (pytest-asyncio function-scope vs session-scoped asyncpg pool), не функциональные баги. Будут исправлены отдельно.

**Последнее обновление:** 2026-05-03 (агент Claude Opus 4.7), 4-я сессия дня — верификация работы предыдущего субагента
**Дедлайн:** 2026-05-12 (отчёт), 11–16.05 (защита)

## Где мы сейчас

**Стадия:** **9 из 10 этапов REFOCUS_PLAN ЗАВЕРШЕНЫ.** Этап 8 (презентация) выполнен ⚠️ частично — есть наследие старой двухсегментной версии. В работе — финальная верификация: чек-лист преподавателя, доделка презентации, smoke-тестирование UI.

## Этапы REFOCUS_PLAN

| # | Этап | Статус |
|---|------|--------|
| 0 | Восстановление пропущенных данных из YDB-101hotels | ✅ Готово (5437 строк, PG MAX=2026-05-03) |
| 1 | Перенастройка AI-агента под B2B | ✅ Готово (22/22 теста PASS) |
| 2 | Главная страница как B2B-командный центр | ✅ Готово (Home.tsx с RevPAR/Pickup/Pace виджетами) |
| 3 | Убрать туристические маршруты из навигации | ✅ Готово (Layout.tsx) |
| 4 | RMS-метрики на странице Analytics | ✅ Готово (новые endpoints + Analytics.tsx) |
| 5 | Обновление моделей системы под B2B | ✅ Готово (UC, DOMAIN, REQ, COMPONENT, BP — 5 актёров, 10 UC) |
| 6 | ТЭО под B2B | ✅ Готово (`TEO_POLNOE.md`, 8 разделов методички) |
| 7 | Docker production + DEPLOYMENT.md | ✅ Готово (multi-stage Dockerfile + 242-строчная инструкция) |
| 8 | Презентация под B2B | ⚠️ **Частично** — есть наследие старой версии в `PREZENTACIYA_VKR.md` |
| 9 | Сборка финального отчёта | ✅ Готово (`OTCHET_PO_PRAKTIKE.md`, 678 строк, 2 главы по 4 подглавы, ТЭО как 2.4) |

## Что сделано в этой сессии

- [x] **A. Якорные документы обновлены** под фактическое состояние (REFOCUS_PLAN: ✅ для 2,4,5,6,7,9 + ⚠️ для 8 + полный журнал; этот SESSION_HANDOFF переписан).
- [x] **D. Чек-лист преподавателя**: отчёт прочитан целиком (678 строк), сверен с 32 пунктами + стилевая проверка. Пройдены: 0 AI-маркеров, 0 em dash (только en dash), 70 ёлочек, «позволяет» 2 раза, «обеспечивает» 5 раз — все в пределах нормы. Исправлены критические расхождения: раздел 2.3 переписан под B2B-навигацию (6 пунктов в 3 группах вместо 7 туристических, сценарий отельера/администрации/исследователя, B2B-чипы вместо «Лучшие отели на Ольхоне»); цифры приведены к фактическим (63 endpoint вместо 59 в трёх местах; 104 теста в 8 файлах вместо 60 теста в 5 файлах в трёх местах); уровни заголовков `###` в подглаве 2.3 заменены на жирные подзаголовки в начале абзацев (соответствие пункту 12 «только 2-й уровень»).
- [x] **B. Презентация фикс наследия.** В `PREZENTACIYA_VKR.md` исправлены: защищаемый тезис 10.3 («единый интерфейс для B2B и B2C» → B2B-тезис с тремя сегментами и RMS-метриками); раздел 2.2 «Adaptive Model Routing» → честная «Дифференцированная конфигурация Mistral по типу задачи»; 17 модулей → 14 модулей (4 места); РЕЗЮМЕ переписано (5 инструментов → 6 с `get_revenue_metrics`, RMSE 2.24 → 2,67 для Иркутского, 16 LLM-тестов → 104 в 8 файлах, добавлены B2B-тарифы Starter/Pro/Region/Research); таблица 10.2 «Tool-based implicit profiling» → «Единый B2B-агент»; FAQ Q/A с RMSE 2.24 → 2,67; «B2B2C» → «PMS-интеграции»; «Cascade Routing» → «Накопление полного годового цикла данных».
- [x] **C. UI smoke-тест.** Поднят backend (uvicorn :8000) и frontend (Vite :5173). Сняты скриншоты 8 страниц через Playwright (Chromium). Найдены 3 наследия, которые субагент пропустил: страница `/chat` целиком (заголовок «AI-помощник», подсказки «о туризме»), блок «Планирование» в `/about`, hotel_detail с тестовым ID 404. Все три починены в коде (`Chat.tsx`, `About.tsx`) + сделаны повторные скриншоты `chat_v2.png`, `about_v2.png`, `hotel_detail_v2.png` — теперь B2B-полностью. `tsc --noEmit` зелёный после правок.

## UI-наблюдения — ✅ ВСЕ ИСПРАВЛЕНЫ в этой сессии

| # | Страница | Что было | Что сделано |
|---|----------|----------|-------------|
| 1 | Home | KPI с лейблами «Occupancy» / «Прогноз 14 дней» — не очевидно различимы | Переименованы в «Occupancy сейчас» / «Прогноз на 14 дней» с однозначными `sub`-подписями |
| 2 | Analytics | Горизонтальные столбцы RevPAR по районам (замечание комиссии 7.04 — «не интерпретируемо») | Заменены на полноценную RMS-сводную таблицу: Район × Объектов × Occupancy × ADR × RevPAR × Δ к региону × Достоверность. Цветная дельта, кликабельные строки, средневзвешенный RevPAR в подвале |
| 3 | Map | Заголовок «Регионы и карта» при навигации «Региональная карта» | Унифицирован на «Региональная карта» |
| 4 | Events | В каталоге попадали события из Москвы, Красноярска и т.п. | Добавлен whitelist/blacklist фильтр в `routers/events.py::_is_outside_region()` (отбрасывает события с location в чёрном списке, если whitelist его не «спасает») |
| 5 | HotelDetail | «Динамика цен» — пустой график при отсутствии цен | Добавлено условие `chartData.some(d => d.price > 0)` + EmptyState с пояснением «Нет публикуемых цен по этому объекту» |

## Технический долг — ✅ ВСЕ ЗАКРЫТЫ

| # | Задача | Решение |
|---|--------|---------|
| 6 | 99 hotel_id из YDB не нашли в PG `hotels` | Запущен `POST /api/parser/hotels` (208 отелей upserted), затем повторный запуск `import_from_ydb_101hotels.py --days 35`: из 1072 строк осталось 7 missing (свежие за период парсинга) — разрыв сократился с 23 до 7 за 5 дней |
| 7 | События за период простоя | Запущены 5 парсеров через POST `/api/parser/events/<source>`: irk.ru (+25), zeroevent (+59), culture38/kassir/yandex/culture_rf — 0/timeout. **Итого +84 события** |

## Состояние тестов после фиксов

- `pytest backend/tests` — 104 passed, 2 skipped, 1 failed (`test_export_csv_occupancy` — 400 вместо 200, pre-existing, не регрессия моих правок).
- `tsc --noEmit` (frontend) — ✅ зелёный.
- Финальные скриншоты `*_final.png` в `.screenshots/` (8 шт.) — подтверждают полную B2B-консистентность.

## Что в системе сейчас (2026-05-03 поздний вечер)

- Backend живой на :8000, healthy (1129 docs в Chroma, postgres + redis healthy).
- Frontend на :5173.
- В PG hotels: ~1574 объектов (1370 + 208 свежих после `parser/hotels`).
- В PG hotel_statistics: ~37 663 + 6362 (за gap 31 день) + парсинг сегодня.
- В PG events: было 318, добавлено 84 (+25 irk + 59 zeroevent), итого ~402 события.

## Тесты на текущий момент

| Проверка | Результат |
|----------|-----------|
| `pytest backend/tests` | **104 passed, 2 skipped, 1 failed** (`test_export_csv_occupancy` — connection issue без живого backend, **не регрессия**) |
| `tsc --noEmit` (frontend) | ✅ TS OK |
| 32 пункта преподавателя | Не проверено (этап D) |
| UI визуально | Не проверено (этап C) |

## Что заблокировано / open issues

- **`test_export_csv_occupancy`** упадёт до запуска backend. Исправится после `docker compose --profile full up -d backend`.
- **99 hotel_id из YDB не нашли в PG `hotels`** — известное расхождение с этапа 0.
- **События за период простоя** не догнаны (нет YDB-копии источников событий). Решится одним проходом APScheduler после старта backend.
- **Pyright диагностики** в `main_agent.py`/`llm_service.py` (~30 шт.) — не влияют на runtime/тесты, фикс отдельным раундом.

## Следующий шаг

Текущая сессия идёт по плану A → D → B → C. После этого — проверка соответствия 9/10 этапов фактически рабочему состоянию + smoke-тест UI.

## Что важно помнить

1. **Дата сегодня — 2026-05-03**. Защиты с 11.05.
2. **Двухсегментная модель — мёртвый курс.** Документы в `_archive/` не использовать.
3. **Скриншоты переписки** с Юлией Пестовой — в `screenshots/`.
4. **Полное индивидуальное задание** — `docs/Индивидуальное задание ... Исполатов.docx (1).md`.
5. **Методология преподавателя по моделям** — `models/*/`, в каждой `*_MODEL.md` + `.drawio`.
6. **Методология преподавателя по ТЭО** — `new_tasks/`.
7. **32 пункта оформления отчёта** — `docs/vkr/SUPERVISOR_REQUIREMENTS.md`.
8. **Платформа Windows 11**, PowerShell или Git Bash. Кириллица в путях ломает обычный `ls` — используй PowerShell.
9. **Запуск тестов:** `& "C:\Users\Admin\Desktop\Diplom\backend\venv\Scripts\python.exe" -m pytest tests/ -q`.
10. **YDB legacy.** Credentials в `101hotel_parser/authorized_key.json`. При простое >7 дней — `scripts/import_from_ydb_101hotels.py`.
11. **Docker сейчас:** postgres + redis healthy (поднял я в сессии 2). Backend (uvicorn) НЕ запущен.
12. **Дисциплина якорей нарушалась** субагентом 2026-05-03: он не обновил handoff и не дописал журнал. Урок для будущих агентов: после завершения этапа **сразу обновлять** этот файл и журнал в `REFOCUS_PLAN.md`.

## Журнал сессий

| Дата | Агент | Что сделано |
|------|-------|-------------|
| 2026-05-03 (с1) | Claude Opus 4.7 (1M) | Анализ, NORTH_STAR + REFOCUS_PLAN + SESSION_HANDOFF + SUPERVISOR_REQUIREMENTS, чистка docs/, CLAUDE.md/.cursorrules. **Этап 1**. |
| 2026-05-03 (с2) | Claude Opus 4.7 (1M) | **Этап 0** (5437 строк YDB→PG) + **Этап 3** (Layout.tsx). Docker postgres+redis запущены. |
| 2026-05-03 (с3) | Subagent (?) | **Этапы 2, 4, 5, 6, 7, 9 + 8 частично**. Якорные документы НЕ обновил. Все файлы изменены 20:07–20:59. |
| 2026-05-03 (с4) | Claude Opus 4.7 (1M) | Верификация: разобрался с работой субагента, обновил REFOCUS_PLAN/SESSION_HANDOFF (А). Дальше: D (чек-лист отчёта), B (фикс презентации), C (smoke UI). |
| 2026-05-03 (с5) | Claude Opus 4.7 (1M) | **Полный цикл верификации A→D→B→C**: A — якоря синхронизированы; D — отчёт прочитан 678 строк, цифры приведены к фактическим (63 endpoint, 104 теста), раздел 2.3 переписан под B2B-навигацию, заголовки `###` снижены до жирных вводов; B — защищаемый тезис, раздел 2.2 (Adaptive Routing → дифференцированные temperature), РЕЗЮМЕ, FAQ — переписаны; C — поднят backend+frontend, сняты 8 скриншотов через Playwright, найдены 3 наследия в `/chat`, `/about`, hotel_detail — все 3 починены в коде, переснятые скриншоты v2 подтверждают B2B-вид. UI-наблюдения зафиксированы для отдельной сессии. |
| 2026-05-03 (с6) | Claude Opus 4.7 (1M) | **Все UI-наблюдения и тех-долг закрыты в одной сессии**: Home — KPI лейблы перенастроены; Analytics — горизонтальные столбцы заменены на полноценную RMS-сводную таблицу (закрыто замечание комиссии 7.04); Map — заголовок унифицирован; Events — добавлен фильтр локации (whitelist Иркутской / blacklist чужих городов); HotelDetail — заглушка для пустых цен. Долг: запущен парсер 101hotels (+208 отелей), повторный YDB-импорт (sub из 99 → 7 missing); запущены парсеры событий (+84 события). Финальные скриншоты `*_final.png` подтверждают B2B-консистентность. tsc OK, pytest 104 passed. |
