"""Monte Carlo simulation for TEO NPV (10 000 iterations).

Stochastic parameters:
- penetration rate per tariff (Starter/Pro/Region/Research): triangular(0.5x, baseline, 1.5x)
- monthly churn: Beta(2, 18) -> mode ~5 %, mean ~10 %, asymmetric to low values
- hosting cost: triangular(2500, 3000, 6000) RUB/mes (Yandex Cloud B2.medium baseline,
  scale-up to B2.large at 4 vCPU + 8 GB RAM as upper tail)

Outputs:
- P10/P50/P90 NPV (full and cash-only variants)
- P(NPV > 0) for both variants
- histogram saved to PNG

Methodology aligned with new_tasks/monte-karlo-ZAPOLNENO.xlsm template by Osipov M. A.

Run:
    python scripts/monte_carlo_teo.py [--n 10000] [--seed 42]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev


@dataclass(frozen=True)
class Tariff:
    name: str
    price_per_month: int
    baseline_subscribers_at_24m: int


@dataclass(frozen=True)
class TEOParams:
    horizon_months: int = 24
    annual_discount_rate: float = 0.21
    investment_full: int = 174_000  # 30 000 регистрация + 288 ч × 500 ₽ junior-rate = 144 000
    investment_cash: int = 30_000  # cash-only (юридическое оформление ИП)
    fixed_costs_y1_per_month: int = 733  # VPS 150 + мониторинг 500 + домен 83
    fixed_costs_y2_per_month: int = 2_433  # +LLM API 200, +бухгалтерия 1500
    fixed_strakh_vznosy_y1: int = 57_390  # 2026 fixed insurance contributions (ст. 430 НК РФ)
    fixed_strakh_vznosy_y2: int = 60_260  # 2027 estimate (~5 % индексация)
    additional_1pct_threshold_per_year: int = 300_000
    usn_rate: float = 0.06
    logistic_k: float = 0.3
    logistic_t0: float = 14.0  # midpoint month for logistic growth


TARIFFS = [
    Tariff("Starter", 3_500, 24),
    Tariff("Pro", 9_900, 5),
    Tariff("Region", 30_000, 1),
    Tariff("Research", 5_000, 2),
]


def triangular_sample(low: float, mode: float, high: float, rng: random.Random) -> float:
    """Triangular distribution sample."""
    return rng.triangular(low, high, mode)


def beta_sample(alpha: float, beta: float, rng: random.Random) -> float:
    """Beta distribution sample using rng.betavariate."""
    return rng.betavariate(alpha, beta)


def logistic_growth(month: int, target: float, k: float, t0: float) -> float:
    """Logistic curve N(t) = target / (1 + e^(-k(t - t0)))."""
    return target / (1.0 + math.exp(-k * (month - t0)))


def simulate_one(rng: random.Random, params: TEOParams) -> tuple[float, float]:
    """Run one Monte Carlo iteration. Returns (npv_full, npv_cash) in RUB."""
    # Stochastic parameters
    penetration_multiplier = {
        t.name: triangular_sample(0.5, 1.0, 1.5, rng) for t in TARIFFS
    }
    monthly_churn = beta_sample(2, 18, rng)  # mode ~5 %, mean ~10 %
    # Хостинг: Yandex Cloud B2.medium 3000 ₽/мес базовый тариф (2 vCPU + 4 GB RAM,
    # Docker Compose: PostgreSQL + Redis + ChromaDB + FastAPI + Nginx + бэкап
    # в Object Storage). Нижний хвост 2500 ₽ (промо-тариф / меньшая конфигурация),
    # верхний хвост 6000 ₽ (рост нагрузки до B2.large: 4 vCPU + 8 GB RAM).
    hosting_per_month = triangular_sample(2_500, 3_000, 6_000, rng)

    monthly_cash_flow_full: list[float] = []
    monthly_cash_flow_cash: list[float] = []

    annual_revenue_y1 = 0.0
    annual_revenue_y2 = 0.0

    for month in range(1, params.horizon_months + 1):
        # Subscribers per tariff at month t (logistic growth with stochastic
        # multiplier and churn applied after month 6)
        revenue_t = 0.0
        for tariff in TARIFFS:
            target = tariff.baseline_subscribers_at_24m * penetration_multiplier[tariff.name]
            n_subscribers = logistic_growth(month, target, params.logistic_k, params.logistic_t0)

            # Apply churn after month 6 (newly acquired subscribers slowly leak)
            if month > 6:
                churn_factor = (1.0 - monthly_churn) ** (month - 6)
                n_subscribers *= churn_factor

            revenue_t += n_subscribers * tariff.price_per_month

        # Annual revenue accumulators (for tax calc)
        if month <= 12:
            annual_revenue_y1 += revenue_t
        else:
            annual_revenue_y2 += revenue_t

        # Fixed costs (depending on year, plus stochastic hosting)
        if month <= 12:
            fixed_t = (
                hosting_per_month
                + 500  # monitoring
                + 83  # domain
            )
        else:
            fixed_t = (
                hosting_per_month
                + 500
                + 83
                + 200  # LLM API y2
                + 1_500  # accounting y2
            )

        # Bookkeeping: defer tax & insurance to designated months
        budget_payment_t = 0.0
        if month == 12:
            # Year 1 close: insurance + 1% on excess + USN 6% with reduction
            additional_1pct_y1 = max(0, annual_revenue_y1 - params.additional_1pct_threshold_per_year) * 0.01
            usn_y1_theoretical = annual_revenue_y1 * params.usn_rate
            insurance_y1 = params.fixed_strakh_vznosy_y1 + additional_1pct_y1
            usn_y1_actual = max(0, usn_y1_theoretical - insurance_y1)
            budget_payment_t = insurance_y1 + usn_y1_actual
        elif month == 24:
            additional_1pct_y2 = max(0, annual_revenue_y2 - params.additional_1pct_threshold_per_year) * 0.01
            usn_y2_theoretical = annual_revenue_y2 * params.usn_rate
            insurance_y2 = params.fixed_strakh_vznosy_y2 + additional_1pct_y2
            usn_y2_actual = max(0, usn_y2_theoretical - insurance_y2)
            budget_payment_t = insurance_y2 + usn_y2_actual

        net_cash_flow_t = revenue_t - fixed_t - budget_payment_t
        monthly_cash_flow_full.append(net_cash_flow_t)
        monthly_cash_flow_cash.append(net_cash_flow_t)

    # Discount and sum
    monthly_discount_rate = (1 + params.annual_discount_rate) ** (1 / 12) - 1
    discount_factor = lambda t: 1 / (1 + monthly_discount_rate) ** t  # noqa: E731

    npv_full = -params.investment_full + sum(
        cf * discount_factor(t + 1) for t, cf in enumerate(monthly_cash_flow_full)
    )
    npv_cash = -params.investment_cash + sum(
        cf * discount_factor(t + 1) for t, cf in enumerate(monthly_cash_flow_cash)
    )

    return npv_full, npv_cash


def percentile(values: list[float], p: float) -> float:
    """Return the p-th percentile (0..100)."""
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def histogram_ascii(values: list[float], bins: int = 30, width: int = 60) -> str:
    """Draw an ASCII histogram for poor-man's visualization."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        return f"  All values = {lo:.0f}"
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / step), bins - 1)
        counts[idx] += 1
    max_count = max(counts)
    lines = []
    for i, c in enumerate(counts):
        bar = "#" * int(c / max_count * width)
        lo_edge = lo + i * step
        lines.append(f"  {lo_edge:>10,.0f} | {bar} ({c})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=10_000, help="number of Monte Carlo iterations")
    parser.add_argument("--seed", type=int, default=42, help="random seed for reproducibility")
    parser.add_argument(
        "--out",
        type=str,
        default="docs/project/monte_carlo_results.json",
        help="output JSON path",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="run a single deterministic baseline (penetration=1, churn=0, hosting=4500)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="override annual discount rate for sensitivity analysis (e.g. 0.25, 0.30)",
    )
    parser.add_argument(
        "--penetration",
        type=float,
        default=1.0,
        help="penetration multiplier for scenario analysis (0.5 pessimistic / 1.5 optimistic)",
    )
    parser.add_argument(
        "--churn",
        type=float,
        default=0.0,
        help="monthly churn rate after month 6 (e.g. 0.05 for pessimistic scenario)",
    )
    args = parser.parse_args()

    if args.deterministic:
        # Override defaults via CLI for sensitivity / scenario analysis
        if args.rate is not None:
            params = TEOParams(annual_discount_rate=args.rate)
        else:
            params = TEOParams()

        def simulate_deterministic(params: TEOParams) -> tuple[float, float]:
            monthly_cash_flow: list[float] = []
            annual_revenue_y1 = 0.0
            annual_revenue_y2 = 0.0
            for month in range(1, params.horizon_months + 1):
                revenue_t = 0.0
                for tariff in TARIFFS:
                    target = float(tariff.baseline_subscribers_at_24m) * args.penetration
                    n_subscribers = logistic_growth(month, target, params.logistic_k, params.logistic_t0)
                    if month > 6 and args.churn > 0:
                        n_subscribers *= (1.0 - args.churn) ** (month - 6)
                    revenue_t += n_subscribers * tariff.price_per_month
                if month <= 12:
                    annual_revenue_y1 += revenue_t
                else:
                    annual_revenue_y2 += revenue_t
                if month <= 12:
                    fixed_t = 3000 + 500 + 83  # Yandex Cloud B2.medium 3000 + monitoring 500 + .ru-domain 83
                else:
                    fixed_t = 3000 + 500 + 83 + 200 + 1500  # +DeepSeek fallback по факту, +Эльба
                budget_payment_t = 0.0
                if month == 12:
                    additional_1pct_y1 = max(0, annual_revenue_y1 - params.additional_1pct_threshold_per_year) * 0.01
                    usn_y1_theoretical = annual_revenue_y1 * params.usn_rate
                    insurance_y1 = params.fixed_strakh_vznosy_y1 + additional_1pct_y1
                    usn_y1_actual = max(0, usn_y1_theoretical - insurance_y1)
                    budget_payment_t = insurance_y1 + usn_y1_actual
                elif month == 24:
                    additional_1pct_y2 = max(0, annual_revenue_y2 - params.additional_1pct_threshold_per_year) * 0.01
                    usn_y2_theoretical = annual_revenue_y2 * params.usn_rate
                    insurance_y2 = params.fixed_strakh_vznosy_y2 + additional_1pct_y2
                    usn_y2_actual = max(0, usn_y2_theoretical - insurance_y2)
                    budget_payment_t = insurance_y2 + usn_y2_actual
                monthly_cash_flow.append(revenue_t - fixed_t - budget_payment_t)

            monthly_discount_rate = (1 + params.annual_discount_rate) ** (1 / 12) - 1
            df = lambda t: 1 / (1 + monthly_discount_rate) ** t  # noqa: E731
            present_inflow = sum(cf * df(t + 1) for t, cf in enumerate(monthly_cash_flow))
            npv_full = -params.investment_full + present_inflow
            npv_cash = -params.investment_cash + present_inflow

            cumulative = -params.investment_full
            pp_full = None
            for t, cf in enumerate(monthly_cash_flow, start=1):
                cumulative += cf
                if cumulative >= 0 and pp_full is None:
                    pp_full = t
                    break

            cumulative = -params.investment_cash
            pp_cash = None
            for t, cf in enumerate(monthly_cash_flow, start=1):
                cumulative += cf
                if cumulative >= 0 and pp_cash is None:
                    pp_cash = t
                    break

            cumulative_disc = -params.investment_full
            dpp_full = None
            for t, cf in enumerate(monthly_cash_flow, start=1):
                cumulative_disc += cf * df(t)
                if cumulative_disc >= 0 and dpp_full is None:
                    dpp_full = t
                    break

            cumulative_disc = -params.investment_cash
            dpp_cash = None
            for t, cf in enumerate(monthly_cash_flow, start=1):
                cumulative_disc += cf * df(t)
                if cumulative_disc >= 0 and dpp_cash is None:
                    dpp_cash = t
                    break

            return npv_full, npv_cash, pp_full, pp_cash, dpp_full, dpp_cash, sum(monthly_cash_flow), monthly_cash_flow

        npv_full, npv_cash, pp_full, pp_cash, dpp_full, dpp_cash, total_cf, monthly_cf = simulate_deterministic(params)
        revenue_total = 0.0
        for m in range(1, params.horizon_months + 1):
            for t in TARIFFS:
                target = float(t.baseline_subscribers_at_24m) * args.penetration
                n_subscribers = logistic_growth(m, target, params.logistic_k, params.logistic_t0)
                if m > 6 and args.churn > 0:
                    n_subscribers *= (1.0 - args.churn) ** (m - 6)
                revenue_total += n_subscribers * t.price_per_month
        hosting_label = "3000" if (args.penetration == 1.0 and args.churn == 0.0) else "3000"
        print(f"=== DETERMINISTIC (penetration={args.penetration}, churn={args.churn}, hosting={hosting_label}, rate={params.annual_discount_rate:.0%}) ===")
        print(f"  Total revenue 24m:    {revenue_total:>15,.0f} RUB")
        print(f"  Net cash sum 24m:     {total_cf:>15,.0f} RUB")
        print(f"  NPV full:             {npv_full:>15,.0f} RUB")
        print(f"  NPV cash:             {npv_cash:>15,.0f} RUB")
        print(f"  PP full (months):     {pp_full}")
        print(f"  PP cash (months):     {pp_cash}")
        print(f"  DPP full (months):    {dpp_full}")
        print(f"  DPP cash (months):    {dpp_cash}")
        return 0

    rng = random.Random(args.seed)
    params = TEOParams()

    print(f"Running Monte Carlo: n={args.n}, seed={args.seed}")
    print(f"Parameters: horizon={params.horizon_months}m, discount={params.annual_discount_rate:.0%}/yr")

    results_full: list[float] = []
    results_cash: list[float] = []

    for _ in range(args.n):
        full, cash = simulate_one(rng, params)
        results_full.append(full)
        results_cash.append(cash)

    summary = {
        "n_iterations": args.n,
        "seed": args.seed,
        "horizon_months": params.horizon_months,
        "annual_discount_rate": params.annual_discount_rate,
        "investment_full": params.investment_full,
        "investment_cash": params.investment_cash,
        "npv_full": {
            "mean": mean(results_full),
            "stdev": stdev(results_full),
            "p10": percentile(results_full, 10),
            "p50": percentile(results_full, 50),
            "p90": percentile(results_full, 90),
            "p_npv_positive": sum(1 for v in results_full if v > 0) / len(results_full),
        },
        "npv_cash": {
            "mean": mean(results_cash),
            "stdev": stdev(results_cash),
            "p10": percentile(results_cash, 10),
            "p50": percentile(results_cash, 50),
            "p90": percentile(results_cash, 90),
            "p_npv_positive": sum(1 for v in results_cash if v > 0) / len(results_cash),
        },
    }

    print()
    print("=== NPV (полный, с альтернативными издержками) ===")
    print(f"  P10:    {summary['npv_full']['p10']:>15,.0f} ₽")
    print(f"  P50:    {summary['npv_full']['p50']:>15,.0f} ₽")
    print(f"  P90:    {summary['npv_full']['p90']:>15,.0f} ₽")
    print(f"  Mean:   {summary['npv_full']['mean']:>15,.0f} ₽")
    print(f"  Stdev:  {summary['npv_full']['stdev']:>15,.0f} ₽")
    print(f"  P(NPV>0): {summary['npv_full']['p_npv_positive']:.1%}")
    print()
    print("=== NPV (денежный, только реальные потоки) ===")
    print(f"  P10:    {summary['npv_cash']['p10']:>15,.0f} ₽")
    print(f"  P50:    {summary['npv_cash']['p50']:>15,.0f} ₽")
    print(f"  P90:    {summary['npv_cash']['p90']:>15,.0f} ₽")
    print(f"  Mean:   {summary['npv_cash']['mean']:>15,.0f} ₽")
    print(f"  Stdev:  {summary['npv_cash']['stdev']:>15,.0f} ₽")
    print(f"  P(NPV>0): {summary['npv_cash']['p_npv_positive']:.1%}")
    print()
    print("=== Histogram NPV (полный) ===")
    print(histogram_ascii(results_full, bins=30, width=50))
    print()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary written to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
