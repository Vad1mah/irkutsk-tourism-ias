# Phase 2: AI Agent Implementation Plan

> **Sub-skill:** `superpowers:subagent-driven-development`. Steps use checkbox tracking.

**Goal:** Расширить LangGraph агент 6 новыми tools, переписать quick-prompts на Home.tsx, добавить методологические правила в system_prompt, прогнать сценарные тесты.

**Architecture:** LangGraph + Mistral Large + tools. Все новые tools вызывают endpoint'ы из Phase 1 D-серии. Stateless, async, доступны через `main_agent.py`.

**Tech Stack:** LangGraph, Mistral, asyncio, FastAPI Annotated, pytest.

**Spec:** [`docs/superpowers/specs/2026-05-04-rebuild-frontend-b2b-design.md`](../specs/2026-05-04-rebuild-frontend-b2b-design.md) §10.

---

## File Structure

### Будет модифицировано
- `backend/app/services/main_agent.py` — добавить 6 tools, обновить системный промпт.
- `backend/app/services/llm_service.py` — синхронизация системного промпта.
- `backend/app/config.py` — методологические константы.
- `frontend/src/pages/Home.tsx` — переписать B2B_QUICK_PROMPTS.

### Будет создано
- `backend/tests/test_agent_new_tools.py` — unit + сценарные тесты для 6 новых tools.

---

## Раздел A: 6 новых tools

### Task A1: tool `get_top_events_by_impact`

**Files:**
- Modify: `backend/app/services/main_agent.py`
- Test: `backend/tests/test_agent_new_tools.py`

- [ ] **Step 1: Test (mock)**

```python
# backend/tests/test_agent_new_tools.py
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_tool_get_top_events_by_impact_returns_formatted_text():
    from app.services.main_agent import get_top_events_by_impact

    mock_response = [
        {"event": "Фестиваль Байкала", "date": "2026-06-01", "district": "Иркутский",
         "delta_pct": 15.2, "baseline_mean": 50.0, "n_samples": 5,
         "confidence": "high", "method": "seasonal_corrected"},
        {"event": "Концерт", "date": "2026-06-05", "district": "Ольхонский",
         "delta_pct": -3.1, "baseline_mean": 45.0, "n_samples": 4,
         "confidence": "medium", "method": "seasonal_corrected"},
    ]
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.json = lambda: mock_response
        mock_get.return_value.status_code = 200
        result = await get_top_events_by_impact.ainvoke({"n": 5, "min_impact": 0})
        assert isinstance(result, str)
        assert "Фестиваль Байкала" in result or "Иркутский" in result
        assert "+15.2%" in result or "15.2" in result
```

- [ ] **Step 2: Implement tool**

In `backend/app/services/main_agent.py` add:

```python
@tool
async def get_top_events_by_impact(
    n: int = 5,
    min_impact: float = 0.0,
    district: str | None = None,
) -> str:
    """Топ-N событий по влиянию на загрузку (corrected impact).

    Используй когда B2B-пользователь спрашивает:
    - Какие события дают пик/провал спроса
    - Топ-N событий с наибольшим положительным/отрицательным impact
    - Influence событий на occupancy

    Args:
        n: Сколько событий вернуть (default 5)
        min_impact: Минимальный modul impact (default 0 — все)
        district: Опциональный фильтр по району
    """
    import httpx
    from app.config import settings

    base_url = f"http://localhost:{settings.api_port}" if hasattr(settings, "api_port") else "http://localhost:8000"
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        response = await client.get(
            "/api/analytics/events-impact",
            params={"method": "seasonal_corrected"},
        )
        if response.status_code != 200:
            return f"Не удалось получить данные о влиянии событий (status {response.status_code})."
        data = response.json()

    if district:
        data = [d for d in data if d.get("district") == district]
    filtered = [d for d in data if d.get("delta_pct") is not None and abs(d["delta_pct"]) >= min_impact]
    filtered.sort(key=lambda x: abs(x.get("delta_pct") or 0), reverse=True)
    top = filtered[:n]
    if not top:
        return "Событий с измеримым влиянием на загрузку не найдено."

    lines = [f"Топ-{len(top)} событий по влиянию на загрузку:"]
    for i, e in enumerate(top, 1):
        sign = "+" if e["delta_pct"] > 0 else ""
        lines.append(
            f"{i}. [{e['date']}] {e['event']} ({e.get('district', 'н/д')}): "
            f"{sign}{e['delta_pct']:.1f}% "
            f"(baseline {e.get('baseline_mean', 0):.1f}%, "
            f"n={e.get('n_samples', 0)}, доверие: {e.get('confidence', 'low')})"
        )
    return "\n".join(lines)
```

Register in `_register_tools` или `tools` list (зависит от того, как реализована регистрация в текущем `main_agent.py`).

- [ ] **Step 3: Run test + commit**

```bash
cd backend && ./venv/Scripts/python.exe -m pytest tests/test_agent_new_tools.py::test_tool_get_top_events_by_impact_returns_formatted_text -v
git add backend/app/services/main_agent.py backend/tests/test_agent_new_tools.py
git commit -m "feat(agent): tool get_top_events_by_impact (uses /events-impact?method=seasonal_corrected)"
```

---

### Task A2: tool `get_booking_pace`

Аналогично A1. Calls `/api/analytics/booking-pace`. Возвращает summary trend + last 14 day-deltas в текстовом формате.

```python
@tool
async def get_booking_pace(district: str = "Иркутский", days_ahead: int = 14) -> str:
    """Динамика бронирований (proxy-pickup) за будущие дни."""
    # ... вызов /booking-pace, форматирование summary + сводки тренда
```

- [ ] Step 1-3 как A1.

---

### Task A3: tool `compare_districts`

Calls `/api/analytics/compare-districts?districts=A,B`. Возвращает таблицу side-by-side.

```python
@tool
async def compare_districts(districts: list[str], days: int = 30) -> str:
    """Сравнение RMS-метрик нескольких районов."""
```

---

### Task A4: tool `compare_forecast_models`

Calls `/api/forecast/compare-all` (existing). Возвращает RMSE/MAE/R² Prophet/NeuralProphet/XGBoost.

```python
@tool
async def compare_forecast_models(district: str = "Иркутский", days: int = 14) -> str:
    """Сравнить прогноз-модели по точности (RMSE, MAE, R²)."""
```

---

### Task A5: tool `get_occupancy_timeseries`

Calls `/api/analytics/occupancy-timeseries`. Возвращает summary min/max/avg + последние 7 дней.

---

### Task A6: tool `get_price_distribution`

Calls `/api/analytics/price-distribution`. Возвращает p10/p25/p50/p75/p90.

---

## Раздел B: System prompt + методология

### Task B1: Расширить системный промпт

**Files:**
- Modify: `backend/app/services/main_agent.py` (`agent_system_prompt`)
- Modify: `backend/app/services/llm_service.py` (если есть копия промпта там)

- [ ] **Step 1: Add methodological rules to prompt**

В существующий `agent_system_prompt`, после секции «Tools — обязательно использовать», добавить:

```
ФОРМАТ ОТВЕТА (обязателен):
1. Всегда указывай район или географический скоп ответа.
2. Всегда указывай период данных, на которые опирается ответ.
3. Всегда указывай метод/методологию метрики (например, "seasonal_corrected" для impact).
4. Всегда указывай базу для сравнения (с прошлой неделей, с регионом, с baseline).
5. При нехватке данных — явно говори, чего не хватает, не выдумывай.
6. Не сравнивай отель с конкретными конкурентами — у нас нет данных; используй сегментный benchmark.
7. RevPAR и ADR — это прокси (рассчитываются из min_price), а не реальные values; помечай это.
8. Gap данных июль-сентябрь 2025 — известен; не интерполируй молча, явно отмечай.
```

- [ ] **Step 2: Test that prompt contains key phrases**

```python
def test_system_prompt_has_methodology_rules():
    from app.services.main_agent import AGENT_SYSTEM_PROMPT  # или как называется
    assert "район" in AGENT_SYSTEM_PROMPT.lower()
    assert "период" in AGENT_SYSTEM_PROMPT.lower()
    assert "прокси" in AGENT_SYSTEM_PROMPT.lower() or "proxy" in AGENT_SYSTEM_PROMPT.lower()
    assert "gap" in AGENT_SYSTEM_PROMPT.lower() or "июль" in AGENT_SYSTEM_PROMPT.lower()
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(agent): methodological rules in system prompt (district, period, method, baseline, proxy disclaimer)"
```

---

## Раздел C: Frontend quick-prompts

### Task C1: Переписать Home.tsx B2B_QUICK_PROMPTS

**Files:**
- Modify: `frontend/src/pages/Home.tsx` строки 18-23

- [ ] **Step 1**: Переписать на «вечнозелёные» формулировки (см. spec §10.4):

```typescript
const B2B_QUICK_PROMPTS = [
  {
    icon: TrendingUp,
    short: 'Лучший район по RevPAR',
    prompt: 'Какой район показал лучший RevPAR за последние 30 дней?',
  },
  {
    icon: Calendar,
    short: 'События с пиком спроса',
    prompt: 'Топ-5 событий с наибольшим положительным влиянием на спрос',
  },
  {
    icon: Building2,
    short: 'Сравни два загруженных района',
    prompt: 'Сравни два самых загруженных района по RMS-метрикам',
  },
  {
    icon: Activity,
    short: 'Темп бронирований 14 дней',
    prompt: 'Темп бронирований за последние 14 дней — ускоряется или замедляется?',
  },
];
```

- [ ] **Step 2: Verify TypeScript build**

```bash
cd frontend && npm run typecheck
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(home): rewrite B2B_QUICK_PROMPTS as evergreen (no date/event-specific)"
```

---

## Раздел D: Финальная верификация Phase 2

### Task D1: Сценарные тесты + smoke

- [ ] **Step 1: Запустить сценарный тест**

Проверить что агент с новыми tools реально может ответить на quick-prompts. Mock LLM not required — лучше скип-тест с реальным backend если он запущен.

- [ ] **Step 2: Update SESSION_HANDOFF**

Добавить блок про Phase 2 завершение.

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: SESSION_HANDOFF — Phase 2 (AI agent) complete"
```

---

## Self-review checklist

- [ ] 6 новых tools зарегистрированы в `main_agent.py`
- [ ] System prompt расширен 8 методологическими правилами
- [ ] Quick-prompts на Home.tsx переписаны как evergreen
- [ ] Сценарный тест: каждый prompt из Home.tsx может быть выполнен через соответствующие tools
- [ ] No regressions в существующих 22 тестах агента

---

## Execution

`subagent-driven-development` — fresh subagent per task + 2-stage review (spec + code quality) + final code-reviewer for entire phase.
