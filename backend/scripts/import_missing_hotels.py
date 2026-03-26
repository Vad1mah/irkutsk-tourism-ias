"""Создаёт stub-записи для отелей, которые есть в CSV статистики, но отсутствуют в справочнике."""
import asyncio
import csv
import glob
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Base, Hotel, HotelStatistic
from app.db.session import async_session, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CSV_DIR = Path(__file__).resolve().parent.parent.parent / "101hotel_parser"
STATS_DIR = CSV_DIR / "tables" / "hotels_statistics"
HOTELS_CSV = CSV_DIR / "databases" / "af_all_2024.csv"
CITY_DISTRICTS_JSON = CSV_DIR / "databases" / "city_districts.json"

BATCH_SIZE = 100


def _collect_all_hotel_ids_from_stats() -> set[str]:
    """Собирает все уникальные hotel_id из CSV статистики."""
    pattern = str(STATS_DIR / "hotels_statistic_*.csv")
    files = sorted(glob.glob(pattern))
    all_ids: set[str] = set()
    for filepath in files:
        for enc in ("utf-8", "cp1251", "latin-1"):
            try:
                with open(filepath, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        hid = row.get("id", "").strip()
                        if hid:
                            all_ids.add(hid)
                break
            except UnicodeDecodeError:
                continue
    return all_ids


def _load_hotel_names_from_csv() -> dict[str, dict]:
    """Загружает имена и города из af_all_2024.csv для всех отелей."""
    result: dict[str, dict] = {}
    if not HOTELS_CSV.exists():
        return result
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            with open(HOTELS_CSV, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hid = row.get("id", "").strip()
                    if hid:
                        result[hid] = {
                            "name": row.get("name", "").strip() or row.get("full_name", "").strip() or hid,
                            "city": row.get("city", "").strip(),
                            "district": row.get("district", "").strip() or None,
                            "lat": _float(row.get("lat")),
                            "lon": _float(row.get("lon")),
                            "rating": _float(row.get("rating")),
                            "min_price": _int(row.get("min_price")),
                        }
            break
        except UnicodeDecodeError:
            continue
    return result


def _float(v: str | None) -> float | None:
    if not v or v.strip() == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _int(v: str | None) -> int | None:
    f = _float(v)
    return int(f) if f is not None else None


async def main() -> None:
    logger.info("=== Поиск и создание недостающих отелей ===")

    all_stat_ids = _collect_all_hotel_ids_from_stats()
    logger.info(f"Уникальных hotel_id в CSV статистики: {len(all_stat_ids)}")

    csv_hotels = _load_hotel_names_from_csv()
    logger.info(f"Отелей в справочнике af_all_2024.csv: {len(csv_hotels)}")

    async with async_session() as s:
        existing = set(
            row[0] for row in
            (await s.execute(select(Hotel.id))).all()
        )
    logger.info(f"Отелей уже в БД: {len(existing)}")

    missing_ids = all_stat_ids - existing
    logger.info(f"Отелей в статистике, но НЕ в БД: {len(missing_ids)}")

    if not missing_ids:
        logger.info("Нет пропущенных отелей — импорт не нужен")
        await engine.dispose()
        return

    stubs: list[dict] = []
    for hid in missing_ids:
        info = csv_hotels.get(hid, {})
        stubs.append({
            "id": hid,
            "name": info.get("name") or hid.replace("_101hotels", ""),
            "city": info.get("city") or "Неизвестно",
            "district": info.get("district"),
            "lat": info.get("lat"),
            "lon": info.get("lon"),
            "rating": info.get("rating"),
            "min_price": info.get("min_price"),
        })

    total = 0
    for i in range(0, len(stubs), BATCH_SIZE):
        batch = stubs[i:i + BATCH_SIZE]
        async with async_session() as s:
            stmt = pg_insert(Hotel).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
            await s.execute(stmt)
            await s.commit()
            total += len(batch)

    logger.info(f"Создано stub-записей отелей: {total}")

    logger.info("=== Повторный импорт статистики ===")
    from scripts.import_csv_to_pg import _read_all_statistics, _upsert_statistics

    stats = _read_all_statistics()
    if stats:
        count = await _upsert_statistics(stats)
        logger.info(f"Импортировано записей статистики: {count}")

    async with async_session() as s:
        h_count = (await s.execute(select(func.count()).select_from(Hotel))).scalar()
        s_count = (await s.execute(select(func.count()).select_from(HotelStatistic))).scalar()
        min_date = (await s.execute(select(func.min(HotelStatistic.date)))).scalar()
        max_date = (await s.execute(select(func.max(HotelStatistic.date)))).scalar()

    logger.info("=== Итоги ===")
    logger.info(f"Отелей в БД: {h_count}")
    logger.info(f"Записей статистики: {s_count}")
    logger.info(f"Диапазон дат: {min_date} — {max_date}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
