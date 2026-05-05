# Phase 3: Frontend Rebuild Implementation Plan

> **Sub-skill:** `superpowers:subagent-driven-development`. Tasks tracked via TodoWrite.

**Goal:** B2B-rebuild фронта — Layout восстановление AI-чата, переработка Home/Analytics/Map/Forecast/Events/HotelDetail/About, Yandex Maps интеграция, локализация терминологии, gap-aware визуализации.

**Architecture:** React 18 + Vite 7 + TypeScript 5.9 + Tailwind 4 + Recharts + ECharts. Phase 1 backend готов, Phase 2 агент готов. Фронт вызывает существующие endpoint'ы.

**Spec:** [`docs/superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md`](../specs/2026-05-04-rebuild-frontend-b2b-design.md) §3-9.

---

## File Structure

### Будут модифицированы
- `frontend/src/components/Layout.tsx` — вернуть `/chat` в навигацию; реструктурировать sidebar.
- `frontend/src/pages/Home.tsx` — one-page scroll + KPI с дельтами + factual+forecast график + pickup proxy + corrected events impact + методология блок; убрать «Что доступно по сегментам».
- `frontend/src/pages/Analytics.tsx` — 4 tabs (Регионы/Сезонность/События/Сегменты); фильтр достоверности RMS; gap-aware heatmap.
- `frontend/src/pages/Map.tsx` — Yandex Maps + popup'ы + фильтры; удалить radar/treemap/heatmap-by-days.
- `frontend/src/pages/Forecast.tsx` — локализация feature_importance имён; factual vs forecast; methodology tooltip.
- `frontend/src/pages/Events.tsx` — расширенный modal (фото, адрес, цена, время); corrected impact на карточках.
- `frontend/src/pages/HotelDetail.tsx` — сегментный benchmark.
- `frontend/src/pages/About.tsx` — методология блок + источники из /metadata + out-of-scope.
- `frontend/src/api/client.ts` — добавить новые endpoint'ы (Phase 1 D-серия + parser/health).
- `frontend/package.json` — добавить `@pbe/react-yandex-maps`.

### Будут созданы
- `frontend/src/components/YandexMap.tsx` — обёртка Yandex Maps JS API.
- `frontend/src/components/MethodologyTooltip.tsx` — re-usable info-icon для метрик.
- `frontend/src/components/GapAwareLineChart.tsx` — wrapper recharts с разрывом линии в gap-периодах.
- `frontend/src/utils/localizeFeatures.ts` — feature_importance EN→RU маппинг.

---

## Раздел A: Инфраструктура (5 задач)

### Task A1: Install @pbe/react-yandex-maps + verify TS

```bash
cd frontend && npm install @pbe/react-yandex-maps
cd frontend && npx tsc --noEmit
```

Commit: `feat(frontend): install @pbe/react-yandex-maps for Map page rebuild`.

### Task A2: API client — добавить новые endpoint'ы

В `frontend/src/api/client.ts` добавить методы для:
- `getMetadata()` → `/api/analytics/metadata`
- `getParserHealth()` → `/api/parser/health`
- `getBookingPace(district, daysAhead, lookbackDays)` → `/booking-pace`
- `getOccupancyTimeseries(district, days)` → `/occupancy-timeseries`
- `getPriceDistribution(district, days)` → `/price-distribution`
- `compareDistricts(districts: string[], days)` → `/compare-districts`
- `getSegments()` → `/segments`
- `getHotelSegmentBenchmark(hotelId)` → `/hotels/{id}/segment-benchmark`
- `getForecastValidation(district, daysBack)` → `/forecast/{district}/validation`
- `getEventsImpact(method, windowWeeks)` → `/events-impact?method=`

TypeScript types — derive from response shape.

Commit: `feat(api): typed clients for Phase 1 D-series endpoints`.

### Task A3: Localize feature names util

Create `frontend/src/utils/localizeFeatures.ts`:
```typescript
export const FEATURE_LOCALIZATION: Record<string, string> = {
  lag_1: 'Лаг 1 день',
  lag_7: 'Лаг 7 дней',
  lag_30: 'Лаг 30 дней',
  rolling_min_7: 'Скользящий мин. 7д',
  rolling_max_7: 'Скользящий макс. 7д',
  rolling_mean_7: 'Скользящее среднее 7д',
  is_weekend: 'Выходной',
  is_holiday: 'Праздник',
  holiday_indicator: 'Праздник',
  temperature: 'Температура',
  trend: 'Тренд',
  week_of_year: 'Неделя года',
  day_of_week: 'День недели',
  month: 'Месяц',
  precipitation: 'Осадки',
};

export function localizeFeature(name: string): string {
  return FEATURE_LOCALIZATION[name] ?? name;
}
```

Test with vitest: assert localizeFeature('lag_1') === 'Лаг 1 день'.

Commit: `feat(utils): EN→RU feature name localization`.

### Task A4: GapAwareLineChart wrapper

Создать `frontend/src/components/GapAwareLineChart.tsx` — Recharts LineChart wrapper, который при наличии `is_gap=true` точек делает разрыв линии (использует `null` для y-value на gap-точках) и добавляет shaded area + textual annotation.

Commit: `feat(components): GapAwareLineChart with break + annotation in gap periods`.

### Task A5: MethodologyTooltip component

Re-usable info-icon component which on hover shows methodology text. Used inline for ADR/RevPAR/impact methodology disclaimers.

Commit: `feat(components): MethodologyTooltip for inline metric explanations`.

---

## Раздел B: Layout + AI-чат возврат (1 задача)

### Task B1: Layout.tsx — вернуть /chat + реструктурировать

В `Layout.tsx` (~94-138):
- Добавить новую группу «AI-помощник» с пунктом `Аналитический чат` (route `/chat`, icon `MessageSquare`).
- Перенести `Региональная карта` в группу «Аналитика».
- Hero-логотип сохранить.
- Health-indicator сохранить.

Commit: `feat(layout): restore Chat in nav, regroup Map under Analytics`.

---

## Раздел C: Home.tsx переработка (5 задач)

### Task C1: убрать «Что доступно по сегментам»

Удалить блок Home.tsx:336-409 (3 segment cards). Заменить на nav-tile-grid с 4 пунктами «Куда смотреть дальше» (Аналитика, Прогноз, Карта, Чат).

### Task C2: KPI tiles — заменить иконку $ + добавить дельты

`Home.tsx:128, 135` — заменить `DollarSign` на `Banknote` (или нейтральный icon). Добавить дельта-индикатор (стрелка + %) сравнение с прошлым периодом.

### Task C3: Composite forecast+factual chart

Композитный график: за прошлые 14 дней — factual, за следующие 14 — forecast. Вертикаль «сегодня» как разделитель. Tooltip читаемый (белый текст на тёмном card-bg). Подпись «прогноз загрузки, %».

### Task C4: Events impact с corrected method

`Home.tsx:254` Топ-5 событий → calls `getEventsImpact('seasonal_corrected')` (вместо naive). Показывать `delta_pct` с правильным знаком, поясняющий tooltip с методологией.

### Task C5: Pickup proxy + методология блок

Добавить под графиком прогноза двухколонник: pickup proxy за 30 дней + corrected events impact. Внизу страницы — methodology блок с источниками и gap-периодами (читает `/metadata`).

---

## Раздел D: Analytics.tsx — 4 tabs (4 задачи)

### Task D1: Tabs structure

Реструктуризация Analytics.tsx как 4-tab страница: Регионы / Сезонность / События / Сегменты. Tabs UI через готовый компонент или inline.

### Task D2: Tab «Регионы» — RMS-сводка с фильтром достоверности

RMS-таблица (уже есть) + чекбокс «показывать только high+medium confidence». Mini bar chart 5 топ районов сверху.

### Task D3: Tab «Сезонность» — calendar heatmap с gap-aware

Heatmap day-of-week × month с правильной обработкой gap (диагональная штриховка). Quartile bands (high/mid/low season) на основе p25/p75. YoY-сравнение.

### Task D4: Tab «События» + Tab «Сегменты»

Tab «События» — Top-N с corrected impact + demand calendar.
Tab «Сегменты» — bar chart by accommodation_type + box-plot цен + segmental benchmark.

---

## Раздел E: Map.tsx — Yandex Maps (3 задачи)

### Task E1: Yandex Maps integration

YandexMap component с GeoObject markers (отели), popup при клике (имя/районы/свободно/цена), satellite layer toggle. API key из env.

### Task E2: Sidebar фильтры

Фильтры дата/район/сезон/период. Sidebar layout с KPI (свободно, всего, объектов, загрузка).

### Task E3: Удалить радар/treemap/heatmap-by-days

Удалить view-mode «Comparison» (radar), «Overview» (treemap), «Heatmap (14 дней)». Оставить только основной map view + Top-3 районов.

---

## Раздел F: Forecast.tsx (2 задачи)

### Task F1: Локализация feature names + увеличить шрифт

XGBoost feature importance — использовать `localizeFeature()`. Шрифт меток с 10px → 12px. Увеличить ширину Y-axis до 140px.

### Task F2: Factual vs Forecast block

Использовать `getForecastValidation(district, 14)` — показать RMSE/MAE и mae_per_day chart. Подпись «как модель отрабатывает на свежих данных».

---

## Раздел G: Events.tsx (1 задача)

### Task G1: Расширенный modal + corrected impact

Modal события — добавить фото (если `image_url`), адрес (`address`), время (`time_start`), цену (`price_min`/`price_max`), age_restriction. На карточке — `corrected_impact` (если есть).

---

## Раздел H: HotelDetail.tsx (1 задача)

### Task H1: Сегментный benchmark

Добавить блок «Сравнение с сегментом» — calls `getHotelSegmentBenchmark(hotelId)`. Показать таблицу: own vs segment_metrics с дельтой.

---

## Раздел I: About.tsx (1 задача)

### Task I1: Методология блок + источники

- Блок методологии: формула RevPAR, прокси-ADR пояснение, corrected impact методология, gap-обработка.
- Источники данных: динамические из `/metadata` + `/parser/health` (last_run, status).
- Out-of-scope блок: список того, что НЕ делает система (true ADR, comp set, channel mix, и т. д.).

---

## Раздел J: Phase 3 верификация (1 задача)

### Task J1: TypeScript build + smoke + SESSION_HANDOFF

- `cd frontend && npx tsc --noEmit && npm run build`.
- Запустить frontend на :5173 и backend на :8000, открыть страницы в Playwright или вручную.
- Update SESSION_HANDOFF.md.

---

## Execution

Subagent-driven: batched где задачи однотипные (например, все 5 страниц-update в одном subagent если изменения тривиальны). При конфликтах файлов — последовательно.
