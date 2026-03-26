"""Парсер метаданных отелей через Xotelo API (TripAdvisor).

Бесплатный API без авторизации.
Покрытие: Иркутская область — 1262 объекта.
Данные: название, координаты, рейтинг TripAdvisor, тип, фото, отзывы.
Цены: недоступны для РФ (OTA ограничения).
"""
import aiohttp
import asyncio
import logging
from math import radians, cos, sin, asin, sqrt

from app.constants import TRIPADVISOR_LOCATIONS, TRIPADVISOR_REGION_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://data.xotelo.com/api"
PAGE_SIZE = 100
REQUEST_DELAY = 1.5


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в км (формула Хаверсина)."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def _extract_hotel(raw: dict, location_name: str) -> dict:
    """Преобразовать данные Xotelo в формат проекта."""
    geo = raw.get("geo") or {}
    review = raw.get("review_summary") or {}

    return {
        "hotel_key": raw.get("key", ""),
        "name": raw.get("name", ""),
        "accommodation_type": raw.get("accommodation_type", ""),
        "location": location_name,
        "lat": geo.get("latitude", 0.0),
        "lon": geo.get("longitude", 0.0),
        "tripadvisor_rating": review.get("rating"),
        "tripadvisor_reviews": review.get("count", 0),
        "mentions": raw.get("mentions", []),
        "labels": raw.get("merchandising_labels", []),
        "image_url": raw.get("image", ""),
        "tripadvisor_url": raw.get("url", ""),
        "source": "xotelo",
    }


async def _fetch_page(
    session: aiohttp.ClientSession,
    location_key: str,
    offset: int,
    sort: str = "best_value",
) -> tuple[list[dict], int]:
    """Получить страницу списка отелей."""
    url = (
        f"{BASE_URL}/list"
        f"?location_key={location_key}"
        f"&offset={offset}&limit={PAGE_SIZE}&sort={sort}"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning(f"Xotelo HTTP {resp.status} (offset={offset})")
                return [], 0
            data = await resp.json()
            if data.get("error"):
                logger.error(f"Xotelo API error: {data['error']}")
                return [], 0
            result = data.get("result", {})
            return result.get("list", []), result.get("total_count", 0)
    except asyncio.TimeoutError:
        logger.warning(f"Xotelo timeout (offset={offset})")
        return [], 0
    except Exception as e:
        logger.error(f"Xotelo request error: {e}")
        return [], 0


async def fetch_hotels_xotelo(
    location_key: str | None = None,
    max_hotels: int | None = None,
) -> list[dict]:
    """Получить все отели для указанной локации.

    Args:
        location_key: TripAdvisor location key (по умолчанию вся область)
        max_hotels: Максимум отелей (None — все)
    """
    if location_key is None:
        location_key = TRIPADVISOR_REGION_KEY

    location_name = TRIPADVISOR_LOCATIONS.get(location_key, location_key)
    hotels: list[dict] = []
    offset = 0
    total = 1

    async with aiohttp.ClientSession() as session:
        while offset < total:
            page_hotels, total = await _fetch_page(session, location_key, offset)
            if not page_hotels:
                break

            for raw in page_hotels:
                hotels.append(_extract_hotel(raw, location_name))

            logger.info(
                f"Xotelo [{location_name}]: {len(hotels)}/{total} "
                f"(offset={offset})"
            )

            offset += PAGE_SIZE
            if max_hotels and len(hotels) >= max_hotels:
                hotels = hotels[:max_hotels]
                break

            await asyncio.sleep(REQUEST_DELAY)

    logger.info(f"Xotelo итого: {len(hotels)} отелей из {location_name}")
    return hotels


def cross_reference(
    hotels_101: list[dict],
    hotels_xotelo: list[dict],
    max_distance_km: float = 0.3,
) -> list[dict]:
    """Сопоставить отели 101Hotels с Xotelo по координатам.

    Args:
        hotels_101: Отели из 101Hotels (поля: name, lat, lon)
        hotels_xotelo: Отели из Xotelo (поля: name, lat, lon)
        max_distance_km: Максимальная дистанция для матча (км)

    Returns:
        Список matched-пар: {hotel_101: ..., xotelo: ..., distance_km: ...}
    """
    matched: list[dict] = []
    used_xotelo: set[str] = set()

    for h101 in hotels_101:
        lat1, lon1 = h101.get("lat", 0), h101.get("lon", 0)
        if not lat1 or not lon1:
            continue

        best_match = None
        best_dist = max_distance_km

        for xh in hotels_xotelo:
            key = xh.get("hotel_key", "")
            if key in used_xotelo:
                continue

            lat2, lon2 = xh.get("lat", 0), xh.get("lon", 0)
            if not lat2 or not lon2:
                continue

            dist = _haversine(lat1, lon1, lat2, lon2)
            if dist < best_dist:
                best_dist = dist
                best_match = xh

        if best_match:
            used_xotelo.add(best_match["hotel_key"])
            matched.append({
                "hotel_101": h101,
                "xotelo": best_match,
                "distance_km": round(best_dist, 3),
            })

    logger.info(
        f"Cross-reference: {len(matched)}/{len(hotels_101)} "
        f"совпадений (порог {max_distance_km} км)"
    )
    return matched


async def parse_and_save_xotelo(
    location_key: str | None = None,
    save_to_db: bool = True,
) -> dict:
    """Полный цикл: загрузка → cross-reference → сохранение.

    Returns:
        Статистика: hotels_fetched, matched, unmatched, saved
    """
    from app.services.data_service import data_service

    hotels = await fetch_hotels_xotelo(location_key)

    result = {
        "hotels_fetched": len(hotels),
        "location": TRIPADVISOR_LOCATIONS.get(
            location_key or TRIPADVISOR_REGION_KEY, "unknown"
        ),
        "matched": 0,
        "saved": 0,
    }

    if not save_to_db or not data_service.is_connected:
        return result

    db_hotels, _ = await data_service.get_hotels(limit=1000)
    hotels_101 = [
        {"id": h.id, "name": h.name, "lat": h.lat, "lon": h.lon}
        for h in db_hotels
    ]

    matches = cross_reference(hotels_101, hotels)
    result["matched"] = len(matches)

    saved = 0
    for m in matches:
        h101_id = m["hotel_101"]["id"]
        xh = m["xotelo"]
        try:
            await data_service.update_hotel_metadata(
                hotel_id=h101_id,
                tripadvisor_rating=xh.get("tripadvisor_rating"),
                tripadvisor_reviews=xh.get("tripadvisor_reviews"),
                tripadvisor_url=xh.get("tripadvisor_url"),
                image_url=xh.get("image_url"),
                accommodation_type=xh.get("accommodation_type"),
            )
            saved += 1
        except Exception as e:
            logger.debug(f"Skip metadata update for {h101_id}: {e}")

    result["saved"] = saved
    logger.info(
        f"Xotelo: {len(hotels)} получено, {len(matches)} совпадений, "
        f"{saved} обновлено"
    )
    return result
