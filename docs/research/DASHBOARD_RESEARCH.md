# Исследование: дашборды и визуализация данных

**Дата:** 22.02.2026
**Статус:** Реализовано — Recharts + ECharts (решение пересмотрено)

## Контекст

Визуализация: **Recharts** (Area, Bar, Composed и др.) и **ECharts** (GeoMap карта отелей на странице Map). Ранее для карты использовался Yandex DataLens (iframe на Map.tsx).

Задача: определить оптимальный подход к визуализации для ВКР — встроить всё в React или использовать внешний BI-инструмент.

## Текущее состояние фронтенда

### Реализованные визуализации

| Страница | Визуализации | Библиотека |
|----------|-------------|------------|
| Analytics (ранее Dashboard + Situation) | KPI карточки, прогноз загрузки (AreaChart), загрузка по районам (BarChart), цены (ComposedChart), погода, топ отелей, корреляции, тепловая карта | Recharts + CSS |
| Forecast (объединены бывшие Seasonality и Forecast) | Сравнение моделей (LineChart), сезонность, feature importance, динамика цен (AreaChart) | Recharts |
| Events | Список с фильтрами, бейджи типов | Нет графиков |
| Home | AI-чат (Markdown), KPI карточки, виджет погоды | Нет графиков |
| Map | Гео-карта отелей, аналитика регионов (radar, treemap, heatmap) | Recharts + ECharts |
| Chat | SSE streaming чат | Нет графиков |
| HotelDetail | Карточка отеля | По необходимости |
| About | Описание системы для комиссии | Нет графиков |

Во фронтенде **8 страниц**: Analytics, Forecast, Map, Events, Home, Chat, HotelDetail, About.

### Чего не хватает

1. Сравнение моделей прогнозирования (Prophet vs NeuralProphet vs XGBoost vs Ensemble)
2. Календарь событий
3. Фильтры по датам на всех страницах
4. Детализация по конкретному отелю
5. Экспорт данных (CSV/PDF)

## Исследованные варианты

### 1. React-библиотеки (встроенные)

#### Recharts (текущая)
- 26K+ stars, активно поддерживается
- Простой API, хорошая документация
- Нет heatmap и гео-карт
- Уже используется в проекте

#### Tremor
- Нативная интеграция с TailwindCSS 4 (наш стек)
- Построен поверх Recharts + Radix UI
- 20+ готовых аналитических компонентов
- Тёмная тема из коробки, 300+ production-ready блоков
- Apache 2.0
- Нет heatmap/гео-карт
- **Миграция с Recharts минимальна**

#### Apache ECharts (echarts-for-react)
- 65K+ stars, 50+ типов графиков
- Нативные гео-карты (GeoJSON) — ключевое преимущество
- Heatmaps, time series с zoom/brush
- Canvas рендеринг (быстро на больших данных)
- Декларативный API (не React-идиоматичный)

#### Nivo
- Полностью React-нативный
- Отличные heatmaps (@nivo/calendar, @nivo/heatmap)
- Менее популярен, сложнее API

#### shadcn/ui Charts
- Copy-paste модель, TypeScript + Tailwind
- Построен на Recharts (те же ограничения)

### 2. Внешние BI-инструменты

#### Apache Superset (self-hosted)
- 30+ визуализаций, SQL, масштабируемость
- Требует Docker: Python + Redis + PostgreSQL + Celery
- **Overkill для ВКР**

#### Metabase (self-hosted)
- Интуитивный UI, не нужен SQL
- Embedding ограничен в бесплатной версии
- Добавляет инфраструктурную сложность

#### Grafana
- Заточен под мониторинг, не аналитику
- **Не подходит**

### 3. Yandex DataLens (ранее, заменено на Recharts + ECharts)

- Embed (iframe) доступен только в платном бизнес-плане Yandex Cloud
- Open-source версия не поддерживает встраивание
- На защите нужен интернет + аккаунт Yandex
- Не демонстрирует навыки фронтенд-разработки
- **Рискованно для ВКР**

## Сравнительная таблица

| Критерий | Tremor + ECharts | Superset | Recharts + ECharts (факт) |
|----------|-----------------|----------|----------|
| Визуальное качество | Отличное | Хорошее | Отличное |
| Интерактивность | Полная | iframe | Полная |
| Зависимость от внешних сервисов | Нет | Self-hosted | Нет |
| Для защиты ВКР | Идеально | Избыточно | Идеально |
| Стоимость | Бесплатно (OSS) | Бесплатно (OSS) | Бесплатно (OSS) |
| Трудозатраты | 5-7 дней | 10+ дней | выполнено |
| Кастомизация UI | Полная | Ограниченная | Полная |
| Работа без интернета | Да | Да (local) | Да |

## Первоначальное решение (22.02.2026)

Планировалась комбинация **Tremor + ECharts**. Однако при реализации выяснилось, что Recharts (уже установленный) покрывает все потребности и лучше интегрируется с существующей кодовой базой.

## Итоговое решение (реализовано)

**Recharts + ECharts** — стек визуализации (вместо DataLens):

1. **Recharts** — основные графики:
   - AreaChart — прогнозы загрузки с CI-bands (Ensemble)
   - LineChart — сравнение моделей (Prophet vs NeuralProphet vs XGBoost)
   - BarChart — загрузка по районам, feature importance
   - ComposedChart — корреляция событий и загрузки
   - RadarChart — сравнение районов
   - Treemap — распределение отелей

2. **Кастомный HeatmapGrid** — тепловая карта загрузки по районам/датам (CSS Grid + вычисление цвета)

3. **ECharts** — GeoMap и связанные виджеты; DataLens не используется (iframe убран), всё в React

## Маппинг типов визуализаций (реализовано)

| Потребность | Компонент | Страница |
|-------------|-----------|----------|
| Прогноз загрузки (CI-bands) | AreaChart | Analytics, Forecast |
| KPI метрики | Кастомные карточки | Analytics, Home |
| Загрузка по районам | BarChart | Analytics |
| Сравнение моделей ML | LineChart (multi) | Forecast |
| Аналитика регионов | RadarChart + Treemap | Map |
| Тепловая карта загрузки | HeatmapGrid (custom) | Map, Analytics |
| Корреляция событий | ComposedChart | Analytics |
| Feature importance | BarChart (horizontal) | Forecast |
| Метрики моделей | Таблица | Forecast |

## Причины пересмотра решения

| Tremor + ECharts (план) | Recharts (факт) |
|------------------------|-----------------|
| 2 новых зависимости | Уже установлен |
| Tremor несовместим с TailwindCSS 4 | Нет конфликтов |
| ECharts тяжёлый (~800KB) | Recharts (~150KB) |
| Требуется изучение двух API | Один знакомый API |
| GeoJSON для карты | ECharts GeoMap + карточки районов |

## Ссылки

- Recharts: https://recharts.org/
- Tremor: https://tremor.so/ (не используется)
- ECharts: https://echarts.apache.org/ (GeoMap на Map)
