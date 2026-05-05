# B2B-Rebuild Cumulative Summary

**Period:** 2026-05-04  
**Branch:** `feat/b2b-rebuild-phase5` (69 commits ahead of master)  
**Status:** ALL PHASES COMPLETE.

## Phase 1: Backend (30 tasks)

- Event schema + 6 fields, dedup constraint added.
- 10 new B2B endpoints: `booking-pace`, `occupancy-timeseries`, `price-distribution`, `compare-districts`, `events-impact` (seasonal_corrected), `segments`, `metadata`, `hotel/{id}/segment-benchmark`, `forecast/{district}/validation`, `parser/health`.
- 7 dead/placeholder endpoints removed.
- 5 parsers extended with AI fallback and dedup logic.
- `ParserHealthService` (Redis-backed, TTL 7 days).
- `MethodologyService` (stateless, `compute_seasonal_baseline`, `corrected_impact`).
- `BookingSnapshot` proxy-pickup model added.

## Phase 2: AI Agent (9 tasks)

- 6 new tools: `get_top_events_by_impact`, `get_booking_pace`, `compare_districts`, `compare_forecast_models`, `get_occupancy_timeseries`, `get_price_distribution` (total 12 tools).
- 8 methodology rules in B2B system prompt (proxy labels, seasonal_corrected, gap-periods, segment benchmark).
- Evergreen quick-prompts on Home (no hardcoded dates or event names).

## Phase 3: Frontend (10 tasks)

- `@pbe/react-yandex-maps` installed; 10 typed API clients generated.
- Layout: Chat restored in sidebar nav.
- Home rebuild: composite factual+forecast chart, corrected events impact badge, methodology footer.
- Analytics: 4-tab layout (Регионы / Сезонность / События / Сегменты), confidence filter, gap-aware heatmap.
- Map: Yandex Maps + placemarks + balloon popups (replaced ECharts contour).
- Forecast: localized feature names (RU), bumped Y-axis font/width, factual vs forecast validation block.
- Events: extended modal (image / address / time / price / age), corrected impact badges on cards.
- HotelDetail: segment benchmark block (district × size_bucket comparison, empty state at n=0).
- About: dynamic metadata from `/api/analytics/metadata`, methodology block, out-of-scope block.

## Phase 4: Models UML/BPMN (2 tasks)

- UC11, UC12 added (total 12 UCs, 12 diagram pages).
- 5 new domain entities: `BookingSnapshot`, `EventImpactRecord`, `SegmentBenchmark`, `ParserHealthRecord`, `MethodologyRecord`.
- FR3.8 (segment benchmark), FR3.9 (daily proxy-pickup), FR4.7 (refined wording: seasonal_corrected), NFR7 (methodological transparency) added.
- `MethodologyService` + `ParserHealthService` documented in COMPONENT_MODEL.
- Процесс 5 (Methodology Calibration) added to BP_MODEL.
- UC11 sequence diagram added to SEQUENCE_MODEL.

## Phase 5: Verification (this phase)

- **pytest:** 207 tests collected, 0 FAILED, 0 ERROR. Pre-existing asyncpg teardown noise (event loop harness issue) — not regressions.
- **tsc:** `npx tsc --noEmit` — clean, no output.
- **build:** `npm run build` — clean, built in 3.75s.
- **Smoke test (backend on :8000):** 9 endpoints tested — 6 × 200, 3 × 400 (Cyrillic not URL-encoded in bash loop; same endpoints return 200 with proper encoding per pytest logs).
- **UML audit:** all 6 models verified (see matrix below).

## UML Model Audit Matrix

| Model | Before rebuild | After rebuild | Delta |
|-------|---------------|---------------|-------|
| UC | 10 UCs | 12 UCs (UC11, UC12) | +2 |
| DOMAIN | 25 entities | 30 entities (+5 new) | +5 |
| REQ | FR1-FR4.6, NFR1-NFR6 | +FR3.8/3.9, FR4.7 refined, NFR7 | +3 |
| COMPONENT | 16 services | 18 services (+MethodologyService, ParserHealthService) | +2 |
| BP | 4 processes | 5 processes (+Процесс 5) | +1 |
| SEQUENCE | UC1-UC8 | UC1-UC8 + UC11 | +1 |

## Cumulative File Stats

| Area | Count |
|------|-------|
| Backend services | 19 |
| Backend routers | 8 |
| Backend parsers | 17 |
| Backend test files | 33 (207 tests) |
| Frontend pages | 8 |
| Frontend components | 10 |
| Git commits (master→HEAD) | 69 |

## Out-of-scope (intentionally deferred)

- Alembic migrations (используется `create_all` + ALTER scripts).
- True ADR / RevPAR (нет revenue data — только proxy через min_price).
- Comp set с конкретными конкурентами (этически проблемно).
- Real-time pickup curve (нет real booking data stream).
- Channel mix / LOS / GOPPAR / source markets.
- `.drawio` диаграммы (текстовые модели обновлены, графика вне scope).
- Alembic ревизии для новых domain entities (BookingSnapshot, EventImpactRecord, SegmentBenchmark, ParserHealthRecord, MethodologyRecord — таблицы логические, не физические).
