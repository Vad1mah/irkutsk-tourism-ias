"""Парсер отелей из OpenStreetMap через Overpass API.

Альтернатива Xotelo (deprecated, /api/list возвращает HTTP 400; миграция на
RapidAPI стала платной). OSM покрывает Иркутскую область ~1000 туристическими
объектами с tag tourism=hotel|hostel|guest_house|..., которые маппятся 1-в-1
на наш accommodation_type (русские значения, как у 101hotels).
"""
import logging
import aiohttp

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

IRKUTSK_BBOX: tuple[float, float, float, float] = (51.5, 99.5, 58.0, 119.5)

TOURISM_TYPES = [
    "hotel", "hostel", "guest_house", "apartment",
    "motel", "resort", "chalet", "aparthotel",
    "camp_site", "caravan_site", "alpine_hut", "wilderness_hut",
]

OSM_TO_RU_TYPE: dict[str, str] = {
    "hotel": "Отель",
    "hostel": "Хостел",
    "guest_house": "Гостевой дом",
    "apartment": "Апартаменты",
    "motel": "Мотель",
    "resort": "Курорт",
    "chalet": "Шале",
    "aparthotel": "Апарт-отель",
    "camp_site": "Кемпинг",
    "caravan_site": "Кемпинг",
    "alpine_hut": "База отдыха",
    "wilderness_hut": "База отдыха",
}


def _build_query(bbox: tuple[float, float, float, float]) -> str:
    """Overpass QL для всех туристических объектов в bbox."""
    types_re = "|".join(TOURISM_TYPES)
    south, west, north, east = bbox
    return (
        "[out:json][timeout:60];\n"
        "(\n"
        f'  node["tourism"~"^({types_re})$"]({south},{west},{north},{east});\n'
        f'  way["tourism"~"^({types_re})$"]({south},{west},{north},{east});\n'
        ");\n"
        "out center;"
    )


def _normalize(elem: dict) -> dict | None:
    """OSM element → формат, совместимый с cross_reference (lat/lon/accommodation_type)."""
    tags = elem.get("tags", {}) or {}
    tourism = tags.get("tourism")
    if tourism not in TOURISM_TYPES:
        return None

    if elem.get("type") == "node":
        lat = elem.get("lat")
        lon = elem.get("lon")
    else:
        center = elem.get("center", {}) or {}
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    name = tags.get("name") or tags.get("name:ru") or tags.get("name:en") or ""
    accommodation_type = OSM_TO_RU_TYPE.get(
        tourism, tourism.title() if tourism else None
    )

    return {
        "hotel_key": f"osm_{elem.get('id')}",
        "name": name,
        "lat": float(lat),
        "lon": float(lon),
        "accommodation_type": accommodation_type,
        "tourism_raw": tourism,
        "city": tags.get("addr:city"),
        "source": "osm",
    }


async def fetch_hotels_osm(
    bbox: tuple[float, float, float, float] = IRKUTSK_BBOX,
    timeout: int = 90,
) -> list[dict]:
    """Запрос Overpass с автоматическим fallback на резервный сервер.

    Args:
        bbox: (south, west, north, east) в градусах. По умолчанию вся Иркутская обл.
        timeout: общий таймаут запроса в секундах.

    Returns:
        Список нормализованных dict'ов с полями hotel_key, name, lat, lon,
        accommodation_type, tourism_raw, city, source.

    Raises:
        RuntimeError: если все Overpass-серверы недоступны.
    """
    query = _build_query(bbox)
    headers = {"User-Agent": "diplom-tourism-research/1.0"}

    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=query,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as r:
                    if r.status != 200:
                        body = await r.text()
                        logger.warning(
                            "Overpass %s returned HTTP %s: %s",
                            url, r.status, body[:200],
                        )
                        continue
                    data = await r.json()
                    elements = data.get("elements", [])
                    normalized = [_normalize(e) for e in elements]
                    result = [n for n in normalized if n is not None]
                    logger.info(
                        "OSM Overpass [%s]: %d элементов, %d нормализовано",
                        url, len(elements), len(result),
                    )
                    return result
        except Exception as exc:
            last_error = exc
            logger.warning("Overpass %s failed: %s", url, exc)
    raise RuntimeError(f"Все Overpass-серверы недоступны: {last_error}")
