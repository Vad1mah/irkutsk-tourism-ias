"""Импорт исторических CSV из курсовой (101hotel_parser) в PostgreSQL."""
import asyncio
import csv
import glob
import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Base, Hotel, HotelStatistic
from app.db.session import async_session, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CSV_DIR = Path(__file__).resolve().parent.parent.parent / "101hotel_parser"
HOTELS_CSV = CSV_DIR / "databases" / "af_all_2024.csv"
STATS_DIR = CSV_DIR / "tables" / "hotels_statistics"

BATCH_SIZE = 100


def _parse_float(val: str | None) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val: str | None) -> int | None:
    f = _parse_float(val)
    return int(f) if f is not None else None


def _parse_date_from_filename(filename: str) -> date | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", filename)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _read_hotels_csv() -> list[dict]:
    """Читает справочник отелей из af_all_2024.csv."""
    if not HOTELS_CSV.exists():
        logger.error(f"Файл не найден: {HOTELS_CSV}")
        return []

    hotels = []
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            with open(HOTELS_CSV, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hotel_id = row.get("id", "").strip()
                    if not hotel_id or not row.get("name", "").strip():
                        continue
                    hotels.append({
                        "id": hotel_id,
                        "name": row.get("name", "").strip(),
                        "city": row.get("city", "").strip(),
                        "district": row.get("district", "").strip() or None,
                        "lat": _parse_float(row.get("lat")),
                        "lon": _parse_float(row.get("lon")),
                        "rating": _parse_float(row.get("rating")),
                        "min_price": _parse_int(row.get("min_price")),
                    })
            logger.info(f"Прочитано {len(hotels)} отелей (encoding={enc})")
            break
        except UnicodeDecodeError:
            continue
    return hotels


def _read_all_statistics() -> list[dict]:
    """Читает все CSV со статистикой загрузки."""
    pattern = str(STATS_DIR / "hotels_statistic_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        logger.error(f"CSV файлы не найдены: {pattern}")
        return []

    logger.info(f"Найдено {len(files)} файлов статистики")
    all_stats: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for filepath in files:
        fname = os.path.basename(filepath)
        fallback_date = _parse_date_from_filename(fname)

        for enc in ("utf-8", "cp1251", "latin-1"):
            try:
                with open(filepath, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        hotel_id = row.get("id", "").strip()
                        if not hotel_id:
                            continue

                        date_str = row.get("date", "").strip()
                        try:
                            record_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else fallback_date
                        except ValueError:
                            record_date = fallback_date

                        if not record_date:
                            continue

                        key = (hotel_id, str(record_date))
                        if key in seen:
                            continue
                        seen.add(key)

                        avail = _parse_float(row.get("available_rooms_percent"))
                        if avail is not None:
                            avail = max(0.0, min(100.0, avail))

                        all_stats.append({
                            "id": hotel_id,
                            "date": record_date,
                            "rooms_num": _parse_int(row.get("rooms_num")),
                            "free_rooms_amount": _parse_int(row.get("free_rooms_amount")),
                            "available_rooms_percent": avail,
                            "min_price": _parse_int(row.get("min_price")),
                            "max_capacity": _parse_int(row.get("max_capacity")),
                        })
                break
            except UnicodeDecodeError:
                continue

    logger.info(f"Прочитано {len(all_stats)} уникальных записей статистики")
    return all_stats


async def _upsert_hotels(hotels: list[dict]) -> int:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    total = 0
    for i in range(0, len(hotels), BATCH_SIZE):
        batch = hotels[i : i + BATCH_SIZE]
        async with async_session() as s:
            stmt = pg_insert(Hotel).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": stmt.excluded.name,
                    "city": stmt.excluded.city,
                    "district": stmt.excluded.district,
                    "lat": stmt.excluded.lat,
                    "lon": stmt.excluded.lon,
                    "rating": stmt.excluded.rating,
                    "min_price": stmt.excluded.min_price,
                },
            )
            await s.execute(stmt)
            await s.commit()
            total += len(batch)
    return total


async def _upsert_statistics(stats: list[dict]) -> int:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    total = 0
    skipped = 0
    for i in range(0, len(stats), BATCH_SIZE):
        batch = stats[i : i + BATCH_SIZE]
        async with async_session() as s:
            try:
                stmt = pg_insert(HotelStatistic).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id", "date"],
                    set_={
                        "rooms_num": stmt.excluded.rooms_num,
                        "free_rooms_amount": stmt.excluded.free_rooms_amount,
                        "available_rooms_percent": stmt.excluded.available_rooms_percent,
                        "min_price": stmt.excluded.min_price,
                        "max_capacity": stmt.excluded.max_capacity,
                    },
                )
                await s.execute(stmt)
                await s.commit()
                total += len(batch)
            except Exception as e:
                await s.rollback()
                skipped += len(batch)
                logger.warning(f"Пропущен батч ({len(batch)} записей): {str(e)[:200]}")

    if skipped:
        logger.warning(f"Пропущено {skipped} записей из-за ошибок constraint")
    return total


async def main() -> None:
    logger.info("=== Импорт CSV из курсовой в PostgreSQL ===")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы созданы/проверены")

    hotels = _read_hotels_csv()
    if hotels:
        count = await _upsert_hotels(hotels)
        logger.info(f"Импортировано отелей: {count}")
    else:
        logger.warning("Нет данных отелей для импорта")

    stats = _read_all_statistics()
    if stats:
        count = await _upsert_statistics(stats)
        logger.info(f"Импортировано записей статистики: {count}")
    else:
        logger.warning("Нет данных статистики для импорта")

    from sqlalchemy import func, select
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
