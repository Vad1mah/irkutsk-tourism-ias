# Phase 4: Models UML/BPMN Update Implementation Plan

> Sub-skill: `superpowers:subagent-driven-development`.

**Goal:** Обновить 6 моделей системы (`models/UC/`, `DOMAIN`, `REQ`, `COMPONENT`, `BP`, `SEQUENCE`) под B2B-rebuild Phase 1-3 — добавить новые UC, сущности, требования, компоненты и процессы, чтобы модели соответствовали реальному коду.

**Spec:** [`docs/superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md`](../specs/2026-05-04-rebuild-frontend-b2b-design.md) §16.

**Note:** Это документация (`.md` файлы), не код. Работаем над `*_MODEL.md` рядом с `.drawio` диаграммами. `.drawio` могут быть отредактированы вручную позже — план фокусируется на текстовых моделях.

---

## File Structure

### Будут модифицированы
- `models/UC/USE_CASE_MODEL.md` — добавить UC11, UC12.
- `models/DOMAIN/DOMAIN_MODEL.md` — добавить 5 сущностей.
- `models/REQ/REQUIREMENTS_MODEL.md` — добавить FR3.8/3.9, FR4.7 corrected, FR6.3 extended, NFR7.
- `models/COMPONENT/COMPONENT_MODEL.md` — добавить Health-monitor + Methodology Service.
- `models/BP/BP_MODEL.md` — добавить БП5.
- `models/SEQUENCE/SEQUENCE_MODEL.md` — добавить sequence для UC11.

---

## Tasks

### Task M1: UC — добавить UC11, UC12

В `models/UC/USE_CASE_MODEL.md`:

**UC11: Анализ событий с corrected impact**
- Актёр: Отельер, Администратор региона.
- Триггер: пользователь запрашивает события, которые повлияли на загрузку.
- Основной поток:
  1. Пользователь открывает Analytics → tab «События».
  2. Система вызывает `/api/analytics/events-impact?method=seasonal_corrected`.
  3. MethodologyService вычисляет baseline по похожим дням недели в окне ±3 нед.
  4. Возвращает топ событий с `delta_pct`, `confidence`, `n_samples`, `ci_lower/upper`.
  5. UI отображает таблицу с цветным delta (зелёный/красный) + filter "только impact ≥ 5%".
- Альт. поток A1: данные в БД отсутствуют для baseline → возвращается `confidence='low'`, UI помечает строку "недостаточно данных".

**UC12: Сегментный benchmark отеля**
- Актёр: Отельер.
- Триггер: пользователь открывает карточку конкретного отеля.
- Основной поток:
  1. Пользователь переходит на `/hotels/{id}`.
  2. Система вызывает `/api/hotels/{id}/segment-benchmark`.
  3. Backend определяет сегмент: район × размерная категория (mini ≤15 / mid 16-50 / large 51+ номеров).
  4. Вычисляет средние метрики по сегменту, исключая сам отель.
  5. UI показывает таблицу: own value vs segment_avg vs delta.
- Альт. поток A1: в сегменте 0 объектов кроме самого отеля → empty state "В сегменте нет других объектов для сравнения".

### Task M2: DOMAIN — 5 новых сущностей

В `models/DOMAIN/DOMAIN_MODEL.md`:

- **BookingSnapshot:** срез occupancy на момент времени для будущих дат заезда. Используется для proxy-pickup. Поля: snapshot_taken_at, target_date, district, occupancy_pct.
- **EventImpactRecord:** рассчитанная impact-запись. Поля: event_id, district, baseline_occupancy_mean, observed_occupancy, delta_pct, ci_lower, ci_upper, n_samples, confidence, method, computed_at.
- **SegmentBenchmark:** агрегированные метрики по сегменту. Поля: district, size_bucket (mini/mid/large), n_in_segment, avg_occupancy, avg_min_price, computed_at.
- **ParserHealthRecord:** Redis-stored запись о статусе парсера. Поля: parser_id, status (ok/warn/fail), items_collected, error, last_run.
- **MethodologyRecord:** методологическая запись для прозрачности. Поля: metric_name, formula_text, version, valid_from, source_endpoint.

### Task M3: REQ — обновить требования

В `models/REQ/REQUIREMENTS_MODEL.md`:

- **FR3.6 (расширить):** RMS-метрики включают proxy-disclaimer (метрика помечается как proxy в API ответе и UI).
- **FR3.7:** Calendar heatmap день недели × месяц с gap-aware рендером.
- **FR3.8 (новое):** Сегментный benchmark по `district × size_bucket` (mini/mid/large по числу номеров).
- **FR3.9 (новое):** Daily proxy-pickup из дельт snapshot'ов (booking-pace endpoint + frontend visualization).
- **FR4.7 (уточнить):** Расчёт impact события методом seasonal_corrected с baseline на похожих днях недели в окне ±N нед., исключая другие event-дни и gap-периоды.
- **FR6.3 (расширить):** Methodology Service фиксирует методики расчётов и версии формул в выгрузке (для воспроизводимости исследовательских запросов).
- **NFR7 (новое):** Методологическая прозрачность — каждая выводимая метрика имеет видимое пояснение источника, формулы и ограничений (через MethodologyTooltip + блок "Методология" на About).

### Task M4: COMPONENT — добавить 2 новых сервиса

В `models/COMPONENT/COMPONENT_MODEL.md`:

- **MethodologyService** (новый компонент): `backend/app/services/methodology_service.py`. Stateless. Методы: `compute_seasonal_baseline()`, `corrected_impact()`. Используется analytics router для events-impact?method=seasonal_corrected.
- **ParserHealthService** (новый компонент): `backend/app/services/parser_health_service.py`. Redis-backed. Методы: `report()`, `list_all()`. Используется BaseParser.run_with_health() lifecycle hook.

Обновить existing components:
- **AnalyticsRouter:** добавлены endpoint'ы `/metadata`, `/booking-pace`, `/occupancy-timeseries`, `/price-distribution`, `/compare-districts`, `/segments`, обновлён `/events-impact` методом seasonal_corrected.
- **HotelsRouter:** добавлен `/{id}/segment-benchmark`.
- **ForecastRouter:** добавлен `/{district}/validation`, удалены 4 dead endpoint'а.
- **EventsRouter:** удалены 3 dead endpoint'а.
- **MainAgent:** 12 tools (было 6).

### Task M5: BP — добавить БП5

В `models/BP/BP_MODEL.md`:

- **БП5: Методологическая калибровка** (новый процесс).
  - Триггер: cron / ручной запуск.
  - Этапы:
    1. MethodologyService периодически пересчитывает baseline по новым данным.
    2. EventImpactRecord обновляются для исторических событий с обновлённым baseline.
    3. Audit log: какие методики были применены, какие версии формул.
  - Выход: обновлённая EventImpactRecord для UI и API.

### Task M6: SEQUENCE — sequence для UC11

В `models/SEQUENCE/SEQUENCE_MODEL.md`:

Добавить sequence diagram для UC11 (Анализ событий с corrected impact):

```
User → AnalyticsRouter: GET /events-impact?method=seasonal_corrected
AnalyticsRouter → DataService: get_events()
DataService → AnalyticsRouter: events list
AnalyticsRouter → DataService: get_occupancy_by_district() per district
DataService → AnalyticsRouter: occupancy histories
AnalyticsRouter → MethodologyService: compute_seasonal_baseline(target, weekday, history, event_dates)
MethodologyService → AnalyticsRouter: SeasonalBaseline {mean, std, n_samples, confidence}
AnalyticsRouter → MethodologyService: corrected_impact(observed, baseline)
MethodologyService → AnalyticsRouter: {delta_pct, ci_lower/upper, baseline_mean, n_samples, confidence, method}
AnalyticsRouter → User: list of events with corrected impact
```

---

## Execution

Все 6 задач — текстовые `.md` файлы. Один subagent может сделать всё в одном dispatch.
