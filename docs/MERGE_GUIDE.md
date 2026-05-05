# Merge Guide — B2B-rebuild ветки → master

## Контекст

После 6 фаз rebuild'а на ветке `feat/b2b-rebuild-phase6` накоплено **75 коммитов** относительно master. Branches формируют последовательную цепочку:

```
master
  └─ feat/b2b-rebuild-phase1 (~50 commits — backend)
       └─ feat/b2b-rebuild-phase2 (~3 commits — AI agent)
            └─ feat/b2b-rebuild-phase3 (~14 commits — frontend)
                 └─ feat/b2b-rebuild-phase4 (~3 commits — UML models)
                      └─ feat/b2b-rebuild-phase5 (~3 commits — verification)
                           └─ feat/b2b-rebuild-phase6 (~5 commits — polish)
```

Все ветки чистые, тесты зелёные (207 backend pytest passed; frontend `tsc --noEmit` clean + `npm run build` ✓), документация и презентация синхронизированы.

## 3 варианта merge

### Вариант 1: Squash merge всех 75 коммитов одним (рекомендуется)

Просто и чисто. История получает один большой коммит «B2B-rebuild Phase 1-6». Для дипломной работы — оптимально.

```bash
git checkout master
git merge --squash feat/b2b-rebuild-phase6
git commit -m "feat: B2B-rebuild — 6 phases of B2B-focused redesign

Phase 1: Backend (30 tasks)
- Event schema +6 fields, dedup constraint, 11 new endpoints
- 7 dead endpoints removed, 5 parsers extended, 2 with AI fallback
- ParserHealthService, MethodologyService

Phase 2: AI Agent (9 tasks)
- 6 new tools (12 total): top_events_impact, booking_pace, compare_districts,
  compare_forecast_models, occupancy_timeseries, price_distribution
- 8 methodology rules in system prompt
- Evergreen quick prompts on Home

Phase 3: Frontend (10 tasks)
- @pbe/react-yandex-maps + 10 typed clients
- Layout: Chat restored
- Home rebuild (composite forecast+factual, methodology footer)
- Analytics: 4 tabs (Регионы/Сезонность/События/Сегменты)
- Map: Yandex Maps + popups
- Forecast: localized features + validation block
- Events: extended modal + corrected impact badges
- HotelDetail: segment benchmark
- About: dynamic metadata + methodology + out-of-scope

Phase 4: UML Models (2 tasks)
- UC11, UC12 added
- 5 new domain entities (BookingSnapshot, EventImpactRecord, SegmentBenchmark, ParserHealthRecord, MethodologyRecord)
- FR3.8/3.9, FR4.7 (refined), NFR7
- 2 new components, BP5, sequence for UC11

Phase 5: Verification (3 tasks)
- 207 tests passing
- UML re-audit (after-rebuild snapshot)
- OTCHET synced + PHASE_REBUILD_SUMMARY

Phase 6: Polish (4 tasks)
- Presentation synced (12 tools, 207 tests, 67 endpoints)
- 3 .drawio diagrams (UC v2, DOMAIN v2, UC11 sequence)
- Persona walkthrough tests (hotelier/admin/researcher)
- This merge guide

Spec: docs/superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md
Summary: docs/PHASE_REBUILD_SUMMARY.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Удалить ветки после merge
git branch -D feat/b2b-rebuild-phase1 feat/b2b-rebuild-phase2 feat/b2b-rebuild-phase3 feat/b2b-rebuild-phase4 feat/b2b-rebuild-phase5 feat/b2b-rebuild-phase6
```

**Pro:** чистая история, один атомарный merge.
**Contra:** теряются мелкие коммиты по фазам (но их видно в git reflog ещё некоторое время).

### Вариант 2: `merge --no-ff` сохраняет историю по фазам

Каждая фаза остаётся видимой в истории. Подходит, если хочется показать научному руководителю детальный прогресс.

```bash
git checkout master

# Merge phase by phase, в каждой merge --no-ff создаст merge-commit с описанием фазы
git merge --no-ff feat/b2b-rebuild-phase1 -m "merge: Phase 1 — Backend (schema, dedup, 11 new endpoints, 6 bugfixes, parsers)"
git merge --no-ff feat/b2b-rebuild-phase2 -m "merge: Phase 2 — AI Agent (12 tools, methodology, evergreen prompts)"
git merge --no-ff feat/b2b-rebuild-phase3 -m "merge: Phase 3 — Frontend rebuild (Yandex Maps, 4-tab Analytics, gap-aware UI)"
git merge --no-ff feat/b2b-rebuild-phase4 -m "merge: Phase 4 — UML Models (UC11/UC12, 5 entities, FR3.8/3.9, services, BP5)"
git merge --no-ff feat/b2b-rebuild-phase5 -m "merge: Phase 5 — Verification (207 tests, OTCHET sync, summary)"
git merge --no-ff feat/b2b-rebuild-phase6 -m "merge: Phase 6 — Polish (presentation sync, drawio gen, persona tests, merge guide)"

git branch -D feat/b2b-rebuild-phase1 feat/b2b-rebuild-phase2 feat/b2b-rebuild-phase3 feat/b2b-rebuild-phase4 feat/b2b-rebuild-phase5 feat/b2b-rebuild-phase6
```

**Pro:** видна структура работы, каждая фаза — отдельный merge-commit.
**Contra:** многословная история (75 + 6 merge-commits = 81 entry).

### Вариант 3: Простой fast-forward

Самый минималистичный — `master` просто перематывается на текущий HEAD ветки.

```bash
git checkout master
git merge feat/b2b-rebuild-phase6  # fast-forward (без создания merge-commit)

git branch -D feat/b2b-rebuild-phase1 feat/b2b-rebuild-phase2 feat/b2b-rebuild-phase3 feat/b2b-rebuild-phase4 feat/b2b-rebuild-phase5
git branch -D feat/b2b-rebuild-phase6
```

**Pro:** все 75 коммитов сохраняются в master в исходном виде.
**Contra:** master становится «наполненным мелкими коммитами», что для ВКР-репозитория обычно нежелательно.

## Рекомендация для дипломной работы

**Вариант 1 (squash) — самый чистый.** Даёт один атомарный коммит, легко показать руководителю/комиссии («B2B-rebuild сделан в одном relevant change»). История по фазам всё равно фиксирована в:

- `docs/superpowers/plans/2026-05-04-rebuild-phase{1..6}-*.md` — планы.
- `docs/PHASE_REBUILD_SUMMARY.md` — кумулятивный отчёт.
- `docs/SESSION_HANDOFF.md` — top-of-file блок с фазами.

## После merge — финальные шаги

1. **Тесты:**
   ```bash
   cd backend && ./venv/Scripts/python.exe -m pytest -q
   cd frontend && npm run build
   ```
   Должны быть зелёными.

2. **Tag для защиты:**
   ```bash
   git tag -a v1.0-b2b -m "B2B-rebuild release for thesis defense"
   ```

3. **Push (когда готов):**
   ```bash
   git push origin master
   git push origin v1.0-b2b
   ```

4. **`.drawio` рендер:** открыть три новых диаграммы в draw.io desktop, экспортировать в PNG, вставить в ВКР отчёт:
   - `models/UC/use_case_b2b_v2.drawio` → `docs/vkr/figures/figure_uc_v2.png`
   - `models/DOMAIN/domain_b2b_v2.drawio` → `docs/vkr/figures/figure_domain_v2.png`
   - `models/SEQUENCE/uc11_sequence.drawio` → `docs/vkr/figures/figure_uc11_seq.png`

5. **Production Yandex Maps key:** ограничить domain referer в личном кабинете Yandex Cloud (https://developer.tech.yandex.ru/) — текущий `a8c0e3f6...` подходит для dev/защиты, но для prod рекомендуется bind to known domains.

## Что НЕ нужно делать

- ❌ `git push --force` на master — никогда.
- ❌ `git rebase -i` на уже зашаренных коммитах.
- ❌ Удалять ветки до подтверждения merge'а в master.
- ❌ Менять коммиты на ветках после merge'а (использовать новый коммит, если нужно).
