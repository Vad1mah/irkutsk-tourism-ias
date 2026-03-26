# Диаграммы последовательности (Sequence Diagram)

## Назначение

Диаграмма последовательности отображает взаимодействие объектов во времени. Показывает порядок передачи сообщений между объектами для реализации сценария Use Case.

## Элементы диаграммы

| Элемент | Обозначение | Описание |
|---------|-------------|----------|
| Объект (Lifeline) | Прямоугольник с подчёркнутым именем | Участник взаимодействия ":ИмяКласса" |
| Линия жизни | Пунктирная вертикальная линия | Период существования объекта |
| Фокус управления | Узкий прямоугольник на линии жизни | Период активности объекта |
| Сообщение (вызов) | Сплошная стрелка → | Вызов операции |
| Сообщение (возврат) | Пунктирная стрелка ⟵ | Возврат результата |
| Условие | [условие] | Сторожевое условие |
| Рамка | sd [Название] | Граница диаграммы |

## Правила анализа пригодности (для Sequence)

| Правило | Описание |
|---------|----------|
| Boundary ↔ Boundary | **ЗАПРЕЩЕНО!** Формы не общаются напрямую |
| Entity → Boundary | **ЗАПРЕЩЕНО!** Данные возвращаются через Control |
| Entity → Control → Boundary | **ПРАВИЛЬНО!** Возврат данных через контроллер |
| Actor → Boundary | Разрешено |
| Boundary → Control | Разрешено |
| Control → Entity | Разрешено |

## Цветовая схема

| Цвет | Тип объекта |
|------|-------------|
| Синий | Пользователь / Внешний API |
| Оранжевый | Boundary (UI элементы) |
| Зелёный | Сервисы (FastAPI, AI-агент, Chroma) |
| Фиолетовый | Entity (PostgreSQL, данные) |
| Серый | Системные актёры (Планировщик) |
| Красный | Администратор |

## Диаграммы по Use Case

### UC1. Построить прогноз загруженности

**Участники:** Пользователь, Home (AI-чат), FastAPI, MainAgent (LangGraph), Chroma, EnsembleService, Prophet, NeuralProphet, XGBoost, LLM (Mistral), PostgreSQL, Redis, ОбластьОтвета, График

**Ключевые сообщения:**
1. открыть() → загрузить() → return форма (через FastAPI)
2. ввестиВопрос(текст) → нажатьОтправить()
3. отправитьЗапрос() → MainAgent.invoke(query)
4. [RAG] ChromaService.search() → return документы
5. [прогноз] ForecastAgent.invoke(district, days)
   5.1 collect_data() → PostgreSQL.get_statistics() + WeatherService.get_forecast()
   5.2 run_models() → EnsembleService.forecast_ensemble() → [Prophet, NeuralProphet, XGBoost] параллельно
   5.3 analyze_factors() → определить main_factors
   5.4 generate_explanation() → PydanticOutputParser → ForecastExplanation
6. LLM.generate() → return ответ с объяснением
7. PostgreSQL.save(запрос, ответ)
8. отобразитьОтвет() → [естьПрогноз] отобразитьГрафик(Ensemble + CI bands)

### UC2. Просмотреть справочник размещения

**Участники:** Пользователь, Map (Аналитика), FastAPI, PostgreSQL, Redis, КарточкаОбъекта

**Ключевые сообщения:**
1. открыть() → загрузитьСписок() → [Redis кэш?] → PostgreSQL.select() → return список
2. выбратьФильтр(район) → отфильтровать() → return результат
3. кликнутьНаКарточку(id) → показатьДетали() → return → отобразить()
4. [тепловая карта] загрузитьHeatmap() → Analytics.get_occupancy_heatmap()

### UC3. Просмотреть календарь событий

**Участники:** Пользователь, Events (Каталог), FastAPI, PostgreSQL, ФильтрИсточника, ПоискТекста, КарточкаСобытия

**Ключевые сообщения:**
1. открыть() → загрузитьСобытия() → PostgreSQL.select() → return список
2. выбратьИсточник(source) → отфильтровать() → return результат
3. ввестиПоиск(текст) → поиск() → return результат
4. кликнутьНаСобытие(id) → показатьДетали() → return → отобразить()

### UC4. Сравнить модели прогнозирования

**Участники:** Пользователь, Forecast (Прогнозы), FastAPI, EnsembleService, Prophet, NeuralProphet, XGBoost, PostgreSQL

**Ключевые сообщения:**
1. выбратьРайон(district) → выбратьГоризонт(days)
2. загрузитьEnsembleForecast() → EnsembleService.forecast_ensemble()
3. загрузитьСравнение() → EnsembleService.compare_models() → return метрики (RMSE, MAE, R²)
4. отобразитьГрафикCI() → отобразитьМетрики() → отобразитьFeatureImportance()

### UC5. Просмотреть аналитику по районам

**Участники:** Пользователь, Map (Аналитика), FastAPI, PostgreSQL, AnalyticsRouter

**Ключевые сообщения:**
1. открыть() → загрузитьРайоны() → return список районов с метриками
2. выбратьРежим(обзор|heatmap|сравнение)
3. [heatmap] загрузитьТепловуюКарту() → Analytics.get_occupancy_heatmap()
4. [radar] загрузитьRadarChart() → return метрики по районам

### UC6. Настроить источники данных

**Участники:** Администратор, ПанельАдмина, FastAPI, PostgreSQL

**Ключевые сообщения:**
1. открыть() → загрузитьИсточники()
2. редактировать(id) → изменитьПараметры()
3. сохранить() → обновить()
4. проверитьДоступность(url) → return статус

### UC7. Просмотреть логи/мониторинг

**Участники:** Администратор, FastAPI, Scheduler, HealthMonitor

**Ключевые сообщения:**
1. /health → return статус сервисов (DB, Redis, Chroma)
2. /api/parser/status → return статистика парсеров
3. scheduler.get_stats() → return расписание и счётчики

### UC8. Выполнить сбор данных (фоновый)

**Участники:** APScheduler, DataCollectorScheduler, BaseParser, 101Hotels, Xotelo, irk.ru, culture38.ru, zeroevent.ru, kassir.ru (Crawl4AI), Telegram, OpenMeteo, PostgreSQL, Chroma, GigaChatEmbeddings

**Ключевые сообщения:**
1. APScheduler.trigger() → DataCollectorScheduler.collect_events()
2. asyncio.gather(collect_events, collect_hotels, collect_weather, collect_telegram)
3. парситьРазмещение() → 101Hotels API (региональный) → return JSON → дедупликация
4. парситьXotelo() → Xotelo API → return JSON (1262 объекта, cross-reference)
5. парситьСобытия() → [irk, culture38, zeroevent, kassir, telegram, yandex, culture_rf] → return events
6. сохранитьВБД(данные) → PostgreSQL batch insert
7. сформироватьЭмбеддинги() → GigaChatEmbeddings → ChromaDB.add()

## Связь с другими моделями

| Модель | Связь |
|--------|-------|
| Use Case | Каждая диаграмма реализует один UC |
| Robustness | Boundary/Control/Entity → участники диаграммы |
| Domain Model | Entity объекты = классы предметной области |
| UI | Boundary объекты = экраны интерфейса |

## Файлы

- `sequence_diagrams.drawio` - 7 диаграмм (по одной на каждый Use Case)

