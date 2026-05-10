"""CLI для заполнения accommodation_type у hotels с NULL через cross-ref OpenStreetMap.

Альтернатива Xotelo (deprecated). OSM Overpass API покрывает ~1000 объектов
Иркутской области с тегом tourism=*, которые мэппятся на русские типы
(см. OSM_TO_RU_TYPE в app.parsers.hotels_osm).

Usage:
    python scripts/fill_hotel_types_from_osm.py --dry-run --limit 100
    python scripts/fill_hotel_types_from_osm.py --max-distance-km 0.5
    python scripts/fill_hotel_types_from_osm.py
"""
import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db.session import async_session  # noqa: E402
from app.parsers.hotels_osm import fetch_hotels_osm  # noqa: E402
from app.parsers.hotels_xotelo import cross_reference  # noqa: E402
from app.services.data_service import data_service  # noqa: E402

logger = logging.getLogger(__name__)


async def _fetch_null_hotels(limit: int | None) -> list[dict]:
    """Hotels с accommodation_type IS NULL и непустыми координатами."""
    q = (
        "SELECT id, lat, lon, name, city FROM hotels "
        "WHERE accommodation_type IS NULL "
        "AND lat IS NOT NULL AND lon IS NOT NULL"
    )
    params: dict = {}
    if limit:
        q += " LIMIT :lim"
        params["lim"] = limit
    async with async_session() as s:
        rows = (await s.execute(text(q), params)).all()
    return [
        {
            "id": r[0],
            "lat": float(r[1]),
            "lon": float(r[2]),
            "name": r[3],
            "city": r[4],
        }
        for r in rows
    ]


async def main(limit: int | None, dry_run: bool, max_distance_km: float) -> int:
    await data_service.connect()

    null_hotels = await _fetch_null_hotels(limit)
    logger.info("NULL hotels с координатами: %d", len(null_hotels))
    if not null_hotels:
        logger.info("Нечего заполнять — выход")
        return 0

    logger.info("Загружаем OSM (Overpass API)...")
    try:
        osm_hotels = await fetch_hotels_osm()
    except RuntimeError as e:
        logger.error("OSM недоступен: %s", e)
        return 1
    logger.info("OSM вернул: %d объектов", len(osm_hotels))
    if not osm_hotels:
        logger.error("OSM не вернул отелей — выход")
        return 1

    matches = cross_reference(null_hotels, osm_hotels, max_distance_km=max_distance_km)
    pct = (100.0 * len(matches) / len(null_hotels)) if null_hotels else 0.0
    logger.info("Matched: %d / %d (%.1f%%)", len(matches), len(null_hotels), pct)

    updates: list[tuple[str, str, float, str]] = []
    skipped_no_type = 0
    for m in matches:
        local = m["hotel_101"]
        osm = m["xotelo"]
        dist = m["distance_km"]
        type_ru = osm.get("accommodation_type")
        if not type_ru:
            skipped_no_type += 1
            continue
        updates.append((local["id"], type_ru, dist, osm.get("tourism_raw") or ""))

    type_counts = Counter(u[1] for u in updates)
    logger.info("Распределение типов: %s", dict(type_counts))
    if skipped_no_type:
        logger.info("Skipped (OSM без accommodation_type): %d", skipped_no_type)

    if dry_run:
        logger.info("DRY-RUN — БД не изменяется. Превью первых 30:")
        for hotel_id, t, dist, raw in updates[:30]:
            print(f"  {hotel_id:32} -> {t:20} [tourism={raw!r}, dist={dist:.3f} км]")
        if len(updates) > 30:
            print(f"  ... ещё {len(updates) - 30}")
        print(f"TOTAL would-be updates: {len(updates)}")
        return 0

    saved = 0
    failed = 0
    for hotel_id, t, _dist, _raw in updates:
        try:
            ok = await data_service.update_hotel_metadata(
                hotel_id=hotel_id,
                accommodation_type=t,
            )
            if ok:
                saved += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.warning("update_hotel_metadata(%s) failed: %s", hotel_id, e)
    logger.info("DB updated: %d hotels (failed=%d)", saved, failed)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(
        description=(
            "Заполнить hotels.accommodation_type у NULL-записей "
            "через cross-ref с OpenStreetMap (Overpass API)."
        )
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ограничить число NULL-hotels (для пилота)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать решения, не апдейтить БД",
    )
    p.add_argument(
        "--max-distance-km",
        type=float,
        default=0.5,
        help="Tolerance Хаверсина в км (default 0.5)",
    )
    args = p.parse_args()
    sys.exit(asyncio.run(main(args.limit, args.dry_run, args.max_distance_km)))
