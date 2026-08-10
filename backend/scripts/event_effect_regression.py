"""Средний эффект событий на загрузку — регрессией по всей панели район×день.

Зачем отдельно от `/api/analytics/events-impact`. Оконный baseline
(`window_weeks`) одним параметром управляет и сглаживанием сезонности, и
размером выборки. Измерено на проде 10.08.2026: расширение окна не сужает
интервал (медиана ширины 49.5 при w=3 против 55–67 при w=8..26), но опускает
базу (61.1 → 55.1 на неизменном наборе дней) и тем самым раздувает оценку.
Регрессия убирает этот параметр: сезонность задаётся гармониками от дня года,
день недели и район — собственными столбцами.

Печатает коэффициент в процентных пунктах загрузки, кластерно-робастный по
датам интервал и перестановочный плацебо-тест.

Запуск (из backend/, venv активирован, доступна БД):
    python scripts/event_effect_regression.py
    python scripts/event_effect_regression.py --placebo 5000 --dump-csv panel.csv
    python scripts/event_effect_regression.py --from-csv panel.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.constants import CITY_TO_DISTRICT, DEFAULT_DISTRICT  # noqa: E402
from app.services.methodology_service import methodology_service  # noqa: E402

# Событий в БД заметно меньше, но дефолтный limit=200 в get_events отсекал бы
# хвост выборки по близости к сегодняшнему дню — здесь нужна вся история.
EVENTS_LIMIT = 100_000


def _resolve_district(event: dict) -> str:
    """Район события: явное поле либо совпадение города в location.

    Повторяет `app.routers.analytics._resolve_district`, чтобы выборка
    регрессии совпадала с выборкой действующего эндпоинта impact.
    """
    explicit = event.get("district")
    if explicit:
        return str(explicit)
    location = (event.get("location") or "").lower()
    return next(
        (dist for city, dist in CITY_TO_DISTRICT.items() if city in location),
        DEFAULT_DISTRICT,
    )


def _to_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


async def _load_from_db() -> tuple[list[tuple[str, date, float]], dict[str, set[date]]]:
    """Панель загрузки и множества событийных дней по районам — из БД."""
    from app.services.db_service import db_service

    await db_service.connect()
    try:
        events = await db_service.get_events(limit=EVENTS_LIMIT)

        event_days: dict[str, set[date]] = {}
        for event in events:
            district = _resolve_district(event)
            start = _to_date(event.get("date_start"))
            if not start:
                continue
            end = _to_date(event.get("date_end")) or start
            if end < start:
                end = start
            cursor = start
            while cursor <= end:
                event_days.setdefault(district, set()).add(cursor)
                cursor += timedelta(days=1)

        districts = sorted(event_days)
        panel: list[tuple[str, date, float]] = []
        for district in districts:
            for row in await db_service.get_occupancy_by_district(district):
                day = _to_date(row.get("date"))
                occupancy = row.get("avg_occupancy")
                if day and occupancy is not None:
                    panel.append((district, day, float(occupancy)))
        return panel, event_days
    finally:
        await db_service.close()


def _load_from_csv(path: Path) -> tuple[list[tuple[str, date, float]], dict[str, set[date]]]:
    """Панель из CSV `district,date,occupancy,is_event` (формат --dump-csv)."""
    panel: list[tuple[str, date, float]] = []
    event_days: dict[str, set[date]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            day = datetime.strptime(row["date"], "%Y-%m-%d").date()
            district = row["district"]
            panel.append((district, day, float(row["occupancy"])))
            if row["is_event"] == "1":
                event_days.setdefault(district, set()).add(day)
    return panel, event_days


def _dump_csv(
    path: Path,
    panel: list[tuple[str, date, float]],
    event_days: dict[str, set[date]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["district", "date", "occupancy", "is_event"])
        for district, day, occupancy in sorted(panel, key=lambda r: (r[0], r[1])):
            flag = 1 if day in event_days.get(district, set()) else 0
            writer.writerow([district, day.isoformat(), f"{occupancy:.4f}", flag])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--placebo", type=int, default=2000,
                        help="Число перестановок плацебо-теста (0 — не запускать)")
    parser.add_argument("--min-days", type=int, default=30,
                        help="Минимум наблюдений на район, иначе район отбрасывается")
    parser.add_argument("--min-days-per-cell", type=int, default=4,
                        help="Минимум наблюдений в ячейке «район × месяц»")
    parser.add_argument("--dump-csv", type=Path, default=None,
                        help="Сохранить собранную панель для офлайн-прогонов")
    parser.add_argument("--from-csv", type=Path, default=None,
                        help="Читать панель из CSV вместо БД")
    args = parser.parse_args()

    if args.from_csv:
        panel, event_days = _load_from_csv(args.from_csv)
    else:
        panel, event_days = asyncio.run(_load_from_db())

    if args.dump_csv:
        _dump_csv(args.dump_csv, panel, event_days)
        print(f"Панель сохранена: {args.dump_csv}")

    print(f"Загружено: {len(panel)} наблюдений, районов с событиями {len(event_days)}, "
          f"событийных дней всего {sum(len(v) for v in event_days.values())}")
    if panel:
        days = [row[1] for row in panel]
        print(f"Период: {min(days)} — {max(days)}")

    result = methodology_service.event_effect_regression(
        panel=panel,
        event_days=event_days,
        placebo_rounds=args.placebo,
        min_days_per_district=args.min_days,
        min_days_per_cell=args.min_days_per_cell,
    )
    if result is None:
        print("Оценка невозможна: не хватает данных (пустая панель, нет событий "
              "или все дни событийные).")
        return 1

    verdict = ("отличается от нуля" if result.ci_lower > 0 or result.ci_upper < 0
               else "НЕ отличается от нуля")
    print()
    print(f"Эффект события          {result.tau:+.2f} п.п. загрузки")
    print(f"95% интервал            [{result.ci_lower:+.2f}, {result.ci_upper:+.2f}]  ({verdict})")
    print(f"Кластерная SE           {result.se:.2f}  "
          f"(кластеры — ячейки район×месяц, {result.n_clusters} шт.)")
    print(f"Независимых эпизодов    {result.n_episodes}  "
          f"(серий подряд идущих событийных дней)")
    if result.placebo_p is not None:
        print(f"Плацебо-тест            p = {result.placebo_p:.4f} "
              f"({args.placebo} круговых сдвигов календаря событий на целые недели)")
    print(f"Наблюдений              {result.n_obs} по {result.n_districts} районам, "
          f"из них событийных {result.n_event_days}")
    print(f"Ячеек сравнения         {result.n_cells} (район × месяц)")
    print(f"R2 полной модели        {result.r_squared:.4f}")
    print(f"Пороги отсева           район {result.min_days_per_district} набл., "
          f"ячейка {result.min_days_per_cell} набл.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
