"""Dozabor missed 101hotels statistics days from working YDB table into PostgreSQL.

Когда нужен:
    Backend (uvicorn) долго не работал, APScheduler не дёргал новый парсер 101hotels,
    но старый внешний парсер (101hotel_parser/main.py) продолжает писать в YDB.
    Этот скрипт догоняет PostgreSQL по датам, берёт данные напрямую из YDB.

Источник данных:
    YDB-таблица hotels_statistics в директории hotels_statistics/ внутри базы из YDB_DATABASE.
    Схема (по 101hotel_parser/main.py): id, rooms_num, free_rooms_amount,
    available_rooms_percent, max_capacity, date, min_price.

Целевая таблица:
    PostgreSQL hotel_statistics (см. app.db.models.HotelStatistic). PK: (id, date).
    Внешний ключ id -> hotels.id (записи без существующего отеля пропускаются).

Использование:
    cd backend
    venv/Scripts/python.exe scripts/import_from_ydb_101hotels.py [--days 14] [--dry-run]

Параметры:
    --days N           Сколько дней назад от сегодня (default: автоматически от MAX(date) в PG).
    --from YYYY-MM-DD  Явная нижняя граница периода (перекрывает --days).
    --to YYYY-MM-DD    Явная верхняя граница периода (default: сегодня).
    --dry-run          Не вставлять в PG, только посчитать и залогировать.

Источник credentials:
    YDB_AUTH_KEY_PATH из backend/.env (по умолчанию ./authorized_key.json).
    Если файл по этому пути не найден — fallback на ../101hotel_parser/authorized_key.json.

Идемпотентность:
    Используется ON CONFLICT (id, date) DO UPDATE — повторный запуск безопасен.
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

import ydb
import ydb.iam

from app.db.models import Hotel, HotelStatistic
from app.db.session import async_session, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ydb_import")

BATCH_SIZE = 200
YDB_TABLE_DIR = "hotels_statistics"
YDB_TABLE_NAME = "hotels_statistics"


def _resolve_auth_key_path() -> Path:
    """Найти authorized_key.json: сначала из .env, fallback на 101hotel_parser/."""
    env_path = os.getenv("YDB_AUTH_KEY_PATH", "./authorized_key.json")
    cwd = Path.cwd()
    candidate = (cwd / env_path).resolve() if not Path(env_path).is_absolute() else Path(env_path)
    if candidate.exists():
        return candidate

    fallback = (Path(__file__).resolve().parent.parent.parent / "101hotel_parser" / "authorized_key.json")
    if fallback.exists():
        logger.warning(f"YDB_AUTH_KEY_PATH={env_path} не найден ({candidate}), fallback: {fallback}")
        return fallback

    raise FileNotFoundError(f"authorized_key.json не найден ни по {candidate}, ни по {fallback}")


async def _get_pg_state() -> tuple[date | None, set[str]]:
    """Собрать MAX(date) и set hotel_ids из PostgreSQL."""
    async with async_session() as session:
        max_row = await session.scalar(select(func.max(HotelStatistic.date)))
        ids_result = await session.scalars(select(Hotel.id))
        hotel_ids = set(ids_result.all())
    return max_row, hotel_ids


def _build_ydb_driver() -> ydb.Driver:
    endpoint = os.getenv("YDB_ENDPOINT")
    database = os.getenv("YDB_DATABASE")
    if not endpoint or not database:
        raise ValueError("YDB_ENDPOINT и/или YDB_DATABASE не заданы в .env")

    auth_key = _resolve_auth_key_path()
    credentials = ydb.iam.ServiceAccountCredentials.from_file(str(auth_key))
    driver_config = ydb.DriverConfig(endpoint=endpoint, database=database, credentials=credentials)
    return ydb.Driver(driver_config)


def _query_ydb(driver: ydb.Driver, date_from: date, date_to: date) -> list[dict[str, Any]]:
    """Прочитать строки YDB hotels_statistics за период.

    YDB OLTP-транзакция ограничена размером ответа (~50MB),
    поэтому идём по дням — каждый день умещается в один запрос.
    """
    database = os.getenv("YDB_DATABASE", "")
    rows: list[dict[str, Any]] = []
    pool = ydb.SessionPool(driver)
    try:
        cur = date_from
        while cur <= date_to:
            query = f"""
                PRAGMA TablePathPrefix("{database}/{YDB_TABLE_DIR}");
                SELECT id, rooms_num, free_rooms_amount, available_rooms_percent,
                       max_capacity, date, min_price
                FROM {YDB_TABLE_NAME}
                WHERE date = Date("{cur.isoformat()}");
            """

            def _run_query(session):
                return session.transaction().execute(query, commit_tx=True)

            try:
                result_sets = pool.retry_operation_sync(_run_query)
            except ydb.issues.TruncatedResponseError:
                logger.warning(f"YDB TruncatedResponse за {cur}, дата пропущена")
                cur += timedelta(days=1)
                continue

            day_count = 0
            for rs in result_sets:
                for row in rs.rows:
                    rows.append(dict(row))
                    day_count += 1
            logger.info(f"YDB {cur}: {day_count} строк")
            cur += timedelta(days=1)
    finally:
        pool.stop()
    return rows


def _normalize_row(row: dict[str, Any], hotel_ids: set[str]) -> dict[str, Any] | None:
    """Привести запись YDB к виду PostgreSQL hotel_statistics или вернуть None если skip."""
    hotel_id = row.get("id")
    if not hotel_id:
        return None

    if isinstance(hotel_id, bytes):
        hotel_id = hotel_id.decode("utf-8", errors="replace")

    if hotel_id not in hotel_ids:
        return None

    raw_date = row.get("date")
    if raw_date is None:
        return None

    if isinstance(raw_date, datetime):
        d = raw_date.date()
    elif isinstance(raw_date, date):
        d = raw_date
    elif isinstance(raw_date, int):
        d = date(1970, 1, 1) + timedelta(days=raw_date)
    elif isinstance(raw_date, str):
        try:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            return None
    else:
        return None

    pct = row.get("available_rooms_percent")
    if pct is not None:
        try:
            pct = max(0.0, min(100.0, float(pct)))
        except (TypeError, ValueError):
            pct = None

    def _to_int(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return {
        "id": hotel_id,
        "date": d,
        "rooms_num": _to_int(row.get("rooms_num")),
        "free_rooms_amount": _to_int(row.get("free_rooms_amount")),
        "available_rooms_percent": pct,
        "max_capacity": _to_int(row.get("max_capacity")),
        "min_price": _to_int(row.get("min_price")),
    }


async def _upsert_batch(rows: list[dict[str, Any]]) -> int:
    """Batch upsert в PostgreSQL hotel_statistics. Возвращает количество вставленных."""
    if not rows:
        return 0

    stmt = pg_insert(HotelStatistic).values(rows)
    update_cols = {
        "rooms_num": stmt.excluded.rooms_num,
        "free_rooms_amount": stmt.excluded.free_rooms_amount,
        "available_rooms_percent": stmt.excluded.available_rooms_percent,
        "max_capacity": stmt.excluded.max_capacity,
        "min_price": stmt.excluded.min_price,
    }
    stmt = stmt.on_conflict_do_update(index_elements=["id", "date"], set_=update_cols)

    async with async_session() as session:
        await session.execute(stmt)
        await session.commit()
    return len(rows)


def _resolve_period(args: argparse.Namespace, pg_max: date | None) -> tuple[date, date]:
    today = date.today()
    date_to = datetime.strptime(args.to, "%Y-%m-%d").date() if args.to else today

    if args.from_:
        date_from = datetime.strptime(args.from_, "%Y-%m-%d").date()
    elif args.days is not None:
        date_from = today - timedelta(days=int(args.days))
    elif pg_max is not None:
        date_from = pg_max + timedelta(days=1)
    else:
        date_from = today - timedelta(days=14)

    if date_from > date_to:
        raise ValueError(f"date_from {date_from} > date_to {date_to}")
    return date_from, date_to


async def _run(args: argparse.Namespace) -> int:
    load_dotenv()
    try:
        return await _run_impl(args)
    finally:
        await engine.dispose()


async def _run_impl(args: argparse.Namespace) -> int:
    pg_max, hotel_ids = await _get_pg_state()
    logger.info(f"PG state: hotels={len(hotel_ids)}, hotel_statistics MAX(date)={pg_max}")

    date_from, date_to = _resolve_period(args, pg_max)
    logger.info(f"Период импорта: {date_from} -> {date_to}")

    if not hotel_ids:
        logger.error("В PostgreSQL нет ни одного отеля. Сначала импортируйте hotels.")
        return 2

    driver = _build_ydb_driver()
    driver.wait(fail_fast=True, timeout=20)
    logger.info("YDB driver connected")

    try:
        ydb_rows = _query_ydb(driver, date_from, date_to)
    finally:
        driver.stop()

    total_read = len(ydb_rows)
    logger.info(f"YDB вернул {total_read} строк")

    if total_read == 0:
        logger.warning("Нечего импортировать. Проверьте период и YDB-таблицу.")
        return 0

    valid: list[dict[str, Any]] = []
    skipped_no_hotel = 0
    skipped_invalid = 0
    for row in ydb_rows:
        norm = _normalize_row(row, hotel_ids)
        if norm is None:
            raw_id = row.get("id")
            if isinstance(raw_id, bytes):
                raw_id = raw_id.decode("utf-8", errors="replace")
            if raw_id and raw_id not in hotel_ids:
                skipped_no_hotel += 1
            else:
                skipped_invalid += 1
            continue
        valid.append(norm)

    logger.info(
        f"Готово к upsert: {len(valid)}, пропущено без отеля: {skipped_no_hotel}, "
        f"пропущено невалидных: {skipped_invalid}"
    )

    if args.dry_run:
        logger.info("--dry-run: запись в PG не выполняется")
        return 0

    upserted = 0
    for i in range(0, len(valid), BATCH_SIZE):
        chunk = valid[i:i + BATCH_SIZE]
        upserted += await _upsert_batch(chunk)
        logger.info(f"Upserted {upserted}/{len(valid)}")

    new_max = (await _get_pg_state())[0]
    logger.info(f"Готово. Upserted={upserted}, новый MAX(date) в PG={new_max}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Дозабор YDB hotels_statistics в PostgreSQL")
    parser.add_argument("--days", type=int, default=None, help="Сколько дней назад от сегодня")
    parser.add_argument("--from", dest="from_", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--to", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Только посчитать, не вставлять")
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args))
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.exception(f"Импорт упал: {e}")
        return 1
    finally:
        try:
            asyncio.run(engine.dispose())
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
