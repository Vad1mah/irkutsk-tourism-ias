"""Comprehensive stress-test AI-агента: 20 запросов через все entry-points.

Покрывает все 14 distinct UI-prompts (Chat, Home, Sparkles на Map/Forecast/Events) +
6 edge-cases (parallel tools, gap-period, negative district, default district,
multi-step, English fallback). Дополнительно — отдельный тест /api/forecast/explain.

Запуск:
    cd backend
    PYTHONIOENCODING=utf-8 python tests/agent_stress_test.py [--base-url http://localhost:8000]

Output:
- stdout: live progress + summary table
- JSON: backend/tests/results/agent_stress_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ERROR_MARKERS = (
    "извините, произошла ошибка",
    "ai-сервис сейчас перегружен",
    "ai временно недоступен",
    "произошла ошибка при обработке",
    "попробуйте позже",
)

CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


@dataclass
class TestQuery:
    id: int
    group: str
    prompt: str
    expect_tools: tuple[str, ...] = ()
    must_contain: tuple[str, ...] = ()
    note: str = ""


@dataclass
class Result:
    id: int
    group: str
    prompt: str
    status: str
    http_code: int
    duration_s: float
    answer_len: int
    answer_preview: str
    tools_used: list[str]
    tools_match: bool
    must_contain_match: bool
    is_russian: bool
    error_marker_hit: str | None
    score: int
    hard_fail: bool
    notes: list[str] = field(default_factory=list)


TEST_QUERIES: list[TestQuery] = [
    # === Chat.tsx QUICK_QUESTIONS (6) ===
    TestQuery(1, "chat",
              "Рассчитай RevPAR на майские праздники по Иркутскому району и сравни с прошлой неделей",
              expect_tools=("get_revenue_metrics",),
              must_contain=("RevPAR",)),
    TestQuery(2, "chat",
              "Какие ближайшие события сильнее всего поднимают спрос на размещение? Топ-5 с расчётом влияния",
              expect_tools=("get_event_effect", "search_events"),
              must_contain=("событ",)),
    TestQuery(3, "chat",
              "Сравни средний тариф и загрузку по всем районам региона за последние 30 дней. Где RevPAR максимальный?",
              expect_tools=("compare_districts", "get_revenue_metrics"),
              must_contain=("район", "RevPAR")),
    TestQuery(4, "chat",
              "Покажи динамику бронирований за последние 14 дней по Ольхонскому району. Тренд ускоряется или замедляется?",
              expect_tools=("get_booking_pace",),
              must_contain=("Ольхонск",)),
    TestQuery(5, "chat",
              "Как погода повлияла на загрузку Иркутского района за последний месяц?",
              expect_tools=("get_weather", "get_occupancy_timeseries"),
              must_contain=("погод",)),
    TestQuery(6, "chat",
              "Дай прогноз загрузки и факторов спроса по Слюдянскому району на 14 дней",
              expect_tools=("forecast_occupancy",),
              must_contain=("Слюдянск", "прогноз")),

    # === Home.tsx B2B_QUICK_PROMPTS (4) ===
    TestQuery(7, "home",
              "Какой район показал лучший RevPAR за последние 30 дней?",
              expect_tools=("get_revenue_metrics", "compare_districts"),
              must_contain=("RevPAR", "район")),
    TestQuery(8, "home",
              "Топ-5 событий с наибольшим положительным влиянием на спрос",
              expect_tools=("get_event_effect",),
              must_contain=("событ",)),
    TestQuery(9, "home",
              "Сравни два самых загруженных района по RMS-метрикам",
              expect_tools=("compare_districts", "get_revenue_metrics"),
              must_contain=("район",)),
    TestQuery(10, "home",
              "Темп бронирований за последние 14 дней — ускоряется или замедляется?",
              expect_tools=("get_booking_pace",),
              must_contain=("брониров",)),

    # === Sparkles-кнопки (3) ===
    TestQuery(11, "map",
              "Сравни заполняемость отелей по районам Прибайкалья",
              expect_tools=("compare_districts", "get_revenue_metrics", "search_hotels"),
              must_contain=("район",)),
    TestQuery(12, "forecast",
              "Объясни прогноз заполняемости для Иркутский района на 14 дней",
              expect_tools=("forecast_occupancy",),
              must_contain=("Иркутск", "14")),
    TestQuery(13, "events",
              "Какие события повлияют на заполняемость отелей в мае?",
              expect_tools=("search_events", "get_event_effect"),
              must_contain=("событ", "мае")),

    # === Edge-cases (6) ===
    TestQuery(15, "edge",
              "Сравни RevPAR Иркутского, Ольхонского и Слюдянского районов за 5, 7 и 14 дней одновременно",
              expect_tools=("get_revenue_metrics", "compare_districts"),
              must_contain=("район",),
              note="parallel-tools provocation: проверка дедупа tool_call_id"),
    TestQuery(16, "edge",
              "Дай статистику по району Краснодарский за 30 дней",
              expect_tools=(),
              must_contain=("Иркутск",),
              note="negative: Краснодарский не в Иркутской области — должен корректно сказать"),
    TestQuery(17, "edge",
              "Что было с загрузкой в августе 2025 года в Иркутском районе?",
              expect_tools=("get_occupancy_timeseries", "get_revenue_metrics"),
              must_contain=("данн",),
              note="gap-период (123-day offline) — должен честно отметить"),
    TestQuery(18, "edge",
              "Какая сейчас загрузка?",
              expect_tools=("get_revenue_metrics", "get_statistics"),
              must_contain=("загруз",),
              note="без района — должен использовать default Иркутский"),
    TestQuery(19, "edge",
              "Сначала покажи топ-3 районов по загрузке, затем топ-3 событий за май, и в конце прогноз для самого загруженного района на 7 дней",
              expect_tools=("compare_districts", "search_events", "forecast_occupancy"),
              must_contain=("район", "событ", "прогноз"),
              note="multi-step: должен использовать 3+ tools последовательно"),
    TestQuery(20, "edge",
              "What is the current occupancy in Olkhonsky district?",
              expect_tools=("get_revenue_metrics", "get_occupancy_timeseries"),
              must_contain=(),
              note="EN-запрос: должен ответить на русском (по системе)"),
]


def post_json(url: str, payload: dict, timeout: float = 180.0) -> tuple[int, dict | None, float]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return r.status, data, time.time() - t0
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = None
        return e.code, err_body, time.time() - t0
    except Exception as exc:
        return 0, {"error": str(exc)}, time.time() - t0


def get_json(url: str, timeout: float = 60.0) -> tuple[int, dict | None, float]:
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return r.status, data, time.time() - t0
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = None
        return e.code, err_body, time.time() - t0
    except Exception as exc:
        return 0, {"error": str(exc)}, time.time() - t0


def score_response(q: TestQuery, http_code: int, body: dict | None, duration_s: float) -> Result:
    answer = ""
    tools_used: list[str] = []
    error_marker_hit: str | None = None
    notes: list[str] = []
    score = 0
    hard_fail = False

    if http_code != 200 or body is None:
        hard_fail = True
        notes.append(f"HTTP {http_code} or empty body")
        return Result(
            id=q.id, group=q.group, prompt=q.prompt, status="HTTP_ERROR",
            http_code=http_code, duration_s=duration_s, answer_len=0,
            answer_preview="", tools_used=[], tools_match=False,
            must_contain_match=False, is_russian=False,
            error_marker_hit=None, score=0, hard_fail=True, notes=notes,
        )

    answer = (body.get("answer") or "").strip()
    tools_used = list(body.get("sources") or [])

    answer_lower = answer.lower()
    for marker in ERROR_MARKERS:
        if marker in answer_lower:
            error_marker_hit = marker
            hard_fail = True
            notes.append(f"error marker: {marker!r}")
            break

    if len(answer) < 30 and not error_marker_hit:
        hard_fail = True
        notes.append(f"answer too short ({len(answer)} chars)")

    if not hard_fail:
        score += 2  # HTTP 200 + non-empty + no error marker

    tools_match = bool(q.expect_tools) and any(t in tools_used for t in q.expect_tools)
    if not q.expect_tools:
        tools_match = True
    if tools_match:
        score += 1
    else:
        notes.append(f"expected tools {q.expect_tools}, got {tools_used}")

    must_contain_match = True
    if q.must_contain:
        for sub in q.must_contain:
            if sub.lower() not in answer_lower:
                must_contain_match = False
                notes.append(f"missing substring {sub!r}")
                break
    if must_contain_match:
        score += 1

    cyr_count = len(CYRILLIC_RE.findall(answer))
    is_russian = (cyr_count / max(len(answer), 1)) > 0.30 if answer else False
    if is_russian:
        score += 1
    else:
        notes.append(f"low cyrillic ratio ({cyr_count}/{len(answer)})")

    if duration_s > 60:
        notes.append(f"slow response {duration_s:.1f}s")
        score = max(0, score - 1)

    status = "OK" if not hard_fail else "FAIL"
    if not hard_fail and score < 4:
        status = "PARTIAL"

    return Result(
        id=q.id, group=q.group, prompt=q.prompt[:80], status=status,
        http_code=http_code, duration_s=round(duration_s, 1),
        answer_len=len(answer), answer_preview=answer[:200].replace("\n", " "),
        tools_used=tools_used, tools_match=tools_match,
        must_contain_match=must_contain_match, is_russian=is_russian,
        error_marker_hit=error_marker_hit, score=score,
        hard_fail=hard_fail, notes=notes,
    )


def run_with_retry(q: TestQuery, base_url: str, max_retries: int = 2) -> Result:
    url = f"{base_url}/api/query"
    backoff_seq = [15, 30, 60]
    code, body, dur = 0, None, 0.0
    for attempt in range(max_retries + 1):
        code, body, dur = post_json(url, {"text": q.prompt}, timeout=180)
        if code == 429 and attempt < max_retries:
            wait = backoff_seq[min(attempt, len(backoff_seq) - 1)]
            print(f"  [#{q.id}] HTTP 429 — waiting {wait}s before retry {attempt+1}/{max_retries}")
            time.sleep(wait)
            continue
        break
    return score_response(q, code, body, dur)


def run_forecast_explain_test(base_url: str) -> dict:
    url = f"{base_url}/api/forecast/explain?district={urllib.parse.quote('Иркутский')}&days_ahead=14"
    code, body, dur = get_json(url, timeout=90)
    result = {
        "test": "forecast/explain",
        "http_code": code,
        "duration_s": round(dur, 1),
        "source": (body or {}).get("source"),
        "best_model": (body or {}).get("best_model"),
        "explanation_len": len((body or {}).get("explanation") or ""),
        "factors_count": len((body or {}).get("factors") or []),
        "ok": code == 200 and (body or {}).get("source") in ("llm", "llm_empty")
              and len((body or {}).get("explanation") or "") > 30,
    }
    return result


def fmt_summary(results: list[Result], explain_result: dict) -> str:
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("AGENT STRESS TEST — РЕЗУЛЬТАТЫ")
    lines.append("=" * 80)
    lines.append(f"{'#':>3} {'GRP':<8} {'STAT':<8} {'CODE':<5} {'DUR':<6} {'SCR':<3} TOOLS")
    lines.append("-" * 80)
    for r in results:
        tools = ",".join(r.tools_used)[:30]
        lines.append(
            f"{r.id:>3} {r.group:<8} {r.status:<8} {r.http_code:<5} "
            f"{r.duration_s:<6} {r.score}/5 {tools}"
        )
    lines.append("-" * 80)

    hard_fails = sum(1 for r in results if r.hard_fail)
    avg_score = sum(r.score for r in results) / len(results) if results else 0
    avg_duration = sum(r.duration_s for r in results) / len(results) if results else 0
    all_tools_seen = sorted({t for r in results for t in r.tools_used})

    lines.append(f"  Total queries:    {len(results)}")
    lines.append(f"  Hard fails:       {hard_fails}")
    lines.append(f"  Avg score:        {avg_score:.2f}/5")
    lines.append(f"  Avg duration:     {avg_duration:.1f}s")
    lines.append(f"  Tools seen ({len(all_tools_seen)}): {', '.join(all_tools_seen)}")
    lines.append("")
    lines.append(f"  /forecast/explain: HTTP {explain_result['http_code']}, "
                 f"source={explain_result['source']}, "
                 f"best_model={explain_result['best_model']}, "
                 f"explanation_len={explain_result['explanation_len']}, "
                 f"ok={explain_result['ok']}")
    lines.append("=" * 80)

    if hard_fails > 0:
        lines.append("\nHARD FAIL DETAILS:")
        for r in results:
            if r.hard_fail:
                lines.append(f"  #{r.id} ({r.group}): {r.notes}")
                lines.append(f"     prompt: {r.prompt}")
                lines.append(f"     answer: {r.answer_preview!r}")

    partial = [r for r in results if r.status == "PARTIAL"]
    if partial:
        lines.append("\nPARTIAL (score < 4):")
        for r in partial:
            lines.append(f"  #{r.id} ({r.group}) score={r.score}: {r.notes}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--pause", type=float, default=8.0,
                        help="Пауза между запросами (сек). Дефолт 8с — под rate-limit 10/min.")
    parser.add_argument("--ids", type=str, default=None,
                        help="Фильтр: только эти ID запросов через запятую (debug)")
    args = parser.parse_args()

    queries = TEST_QUERIES
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        queries = [q for q in queries if q.id in wanted]

    print(f"Stress-test: {len(queries)} запросов на {args.base_url}, пауза {args.pause}с")
    print(f"Старт: {datetime.now().isoformat()}\n")

    health_code, health_body, _ = get_json(f"{args.base_url}/health", timeout=10)
    if health_code != 200:
        print(f"FATAL: backend health check failed (HTTP {health_code}): {health_body}")
        sys.exit(2)
    print(f"Health OK: {health_body}\n")

    results: list[Result] = []
    for i, q in enumerate(queries):
        print(f"[#{q.id:>2}/{q.group:<8}] {q.prompt[:70]}...")
        result = run_with_retry(q, args.base_url)
        results.append(result)
        marker = "OK" if result.status == "OK" else result.status
        print(f"           → {marker} | {result.duration_s}s | score {result.score}/5 | "
              f"tools={result.tools_used}")
        if result.notes:
            print(f"           notes: {'; '.join(result.notes[:3])}")
        if i < len(queries) - 1:
            time.sleep(args.pause)

    print("\nForecast/Explain probe...")
    explain_result = run_forecast_explain_test(args.base_url)
    print(f"  → HTTP {explain_result['http_code']}, "
          f"source={explain_result['source']}, "
          f"explanation_len={explain_result['explanation_len']}")

    summary = fmt_summary(results, explain_result)
    print(summary)

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"agent_stress_{ts}.json"
    out_path.write_text(json.dumps({
        "timestamp": ts,
        "base_url": args.base_url,
        "queries": [asdict(r) for r in results],
        "forecast_explain": explain_result,
        "summary": {
            "total": len(results),
            "hard_fails": sum(1 for r in results if r.hard_fail),
            "avg_score": round(sum(r.score for r in results) / len(results), 2) if results else 0,
            "avg_duration_s": round(sum(r.duration_s for r in results) / len(results), 2) if results else 0,
            "tools_seen": sorted({t for r in results for t in r.tools_used}),
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON: {out_path}")


if __name__ == "__main__":
    main()
