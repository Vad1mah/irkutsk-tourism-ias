"""Парсер отелей с 101hotels.com.

Поддерживает два режима:
- Региональный (по умолчанию): na_baikale + irkutskaya_oblast — 200+ отелей
- По городам (fallback): запросы по отдельным slug-ам городов
"""
import aiohttp
import logging
from datetime import date, timedelta

from app.constants import (
    CITY_DISTRICTS_EN,
    CITY_SLUG_TO_NAME,
    CITY_TO_DISTRICT,
    REGION_SLUGS,
)
from app.services.data_service import data_service

logger = logging.getLogger(__name__)

BASE_URL = "https://ssg.101hotels.com/hotel/available"
MAX_PAGES = 50


async def _save_hotels(hotels: list[dict]) -> int:
    """Сохранить отели через data_service."""
    if not hotels or not data_service.is_connected:
        return 0
    return await data_service.save_hotels(hotels)


async def _save_statistics(statistics: list[dict]) -> int:
    """Сохранить статистику через data_service."""
    if not statistics or not data_service.is_connected:
        return 0
    return await data_service.save_statistics(statistics)


def _resolve_district(city_slug: str) -> str:
    """Определить район по slug города. Fallback = 'Неизвестный'."""
    city_name = CITY_SLUG_TO_NAME.get(city_slug)
    if not city_name:
        return "Неизвестный"
    district = CITY_TO_DISTRICT.get(city_name.lower())
    return district if district else "Неизвестный"


def _extract_image_url(raw: dict) -> str | None:
    """Извлекает первое изображение из response 101hotels API.

    Поддерживает формат photos: list[dict{url}] или list[str].
    """
    photos = raw.get("photos")
    if not isinstance(photos, list) or not photos:
        return None
    first = photos[0]
    if isinstance(first, dict):
        url = first.get("url")
        return url if isinstance(url, str) and url else None
    if isinstance(first, str) and first:
        return first
    return None


def _extract_hotel_data(hotel: dict, city_slug: str) -> dict:
    """Извлечь данные об отеле из API ответа."""
    coords = hotel.get("coords", [])
    slug = hotel.get("city_url", city_slug)
    city_name = hotel.get("city_name") or CITY_SLUG_TO_NAME.get(slug, slug)

    return {
        "id": f"{hotel.get('id', '')}_101hotels",
        "name": hotel.get("name", ""),
        "city": city_name,
        "district": _resolve_district(slug),
        "lat": coords[1] if len(coords) > 1 else None,
        "lon": coords[0] if len(coords) > 0 else None,
        "rating": hotel.get("rating"),
        "min_price": hotel.get("min_price"),
        "image_url": _extract_image_url(hotel),
    }


def _extract_statistic_data(hotel: dict, extract_date: date) -> dict:
    """Извлечь статистику отеля."""
    rooms = hotel.get("rooms", [])
    rooms_num = hotel.get("rooms_num", 0)

    free_rooms_amount = sum(
        room.get("free", 0) if room.get("single_bed", 0) == 0 else 1
        for room in rooms
    )
    if rooms_num > 0:
        free_rooms_amount = min(free_rooms_amount, rooms_num)

    available_rooms_percent = (
        (free_rooms_amount * 100 / rooms_num) if rooms_num > 0 else 0.0
    )

    total_capacity = sum(
        room.get("capacity", 1) for room in rooms
    ) if rooms else rooms_num
    max_capacity = max(total_capacity, rooms_num)

    return {
        "id": f"{hotel.get('id', '')}_101hotels",
        "rooms_num": rooms_num,
        "free_rooms_amount": free_rooms_amount,
        "available_rooms_percent": available_rooms_percent,
        "max_capacity": max_capacity,
        "date": extract_date,
        "min_price": hotel.get("min_price"),
    }


async def _fetch_page(
    session: aiohttp.ClientSession,
    url: str,
    label: str,
    page: int,
) -> tuple[list[dict], int]:
    """Получить страницу результатов."""
    try:
        async with session.get(url) as response:
            if response.status != 200:
                logger.warning(f"HTTP {response.status} для {label}, стр. {page}")
                return [], 0

            data = await response.json()
            resp = data.get("response", {})
            return resp.get("hotels", []), resp.get("total", 0)
    except Exception as e:
        logger.error(f"Ошибка запроса {label}, стр. {page}: {e}")
        return [], 0


def _build_url(
    path: str,
    start_date: str,
    end_date: str,
    page: int,
) -> str:
    return (
        f"{BASE_URL}/{path}"
        f"?sort_direction=desc&in={start_date}&out={end_date}"
        f"&adults=1&page={page}&scenario=desktop"
    )


async def _fetch_all_pages(
    session: aiohttp.ClientSession,
    path: str,
    label: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Загрузить все страницы для указанного path."""
    collected: list[dict] = []
    page = 1
    total = 1

    while len(collected) < total:
        url = _build_url(path, start_date, end_date, page)
        hotels, total = await _fetch_page(session, url, label, page)

        if total == 0:
            break
        if not hotels:
            break
        if page > MAX_PAGES:
            logger.warning(f"{label}: достигнут лимит {MAX_PAGES} страниц")
            break

        collected.extend(hotels)
        logger.info(f"{label}: стр. {page}, получено {len(collected)}/{total}")
        page += 1

    return collected


async def fetch_hotels_by_region(
    regions: list[str] | None = None,
    days_ahead: int = 1,
) -> tuple[list[dict], list[dict]]:
    """Получить отели по регионам с дедупликацией.

    Args:
        regions: Slug-и регионов (по умолчанию REGION_SLUGS)
        days_ahead: Дней вперёд для проверки доступности
    """
    if regions is None:
        regions = REGION_SLUGS

    today = date.today()
    next_day = today + timedelta(days=days_ahead)
    start_date = today.strftime("%d.%m.%Y")
    end_date = next_day.strftime("%d.%m.%Y")

    seen_ids: set[int] = set()
    all_hotels: list[dict] = []
    all_statistics: list[dict] = []

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"},
    ) as session:
        for region in regions:
            path = f"region/russia/{region}"
            raw = await _fetch_all_pages(
                session, path, region, start_date, end_date
            )

            new_count = 0
            for hotel in raw:
                hotel_id = hotel.get("id")
                if hotel_id in seen_ids:
                    continue
                seen_ids.add(hotel_id)

                city_slug = hotel.get("city_url", "")
                all_hotels.append(_extract_hotel_data(hotel, city_slug))
                all_statistics.append(_extract_statistic_data(hotel, today))
                new_count += 1

            logger.info(
                f"Регион {region}: {len(raw)} всего, {new_count} новых "
                f"(дубликатов: {len(raw) - new_count})"
            )

    logger.info(f"Итого: {len(all_hotels)} отелей, {len(all_statistics)} статистик")
    return all_hotels, all_statistics


async def fetch_hotels_by_cities(
    cities: list[str] | None = None,
    days_ahead: int = 1,
) -> tuple[list[dict], list[dict]]:
    """Получить отели по городам (fallback-режим)."""
    if cities is None:
        cities = list(CITY_DISTRICTS_EN.keys())

    today = date.today()
    next_day = today + timedelta(days=days_ahead)
    start_date = today.strftime("%d.%m.%Y")
    end_date = next_day.strftime("%d.%m.%Y")

    all_hotels: list[dict] = []
    all_statistics: list[dict] = []

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"},
    ) as session:
        for city in cities:
            path = f"city/russia/{city}"
            raw = await _fetch_all_pages(
                session, path, city, start_date, end_date
            )

            for hotel in raw:
                all_hotels.append(_extract_hotel_data(hotel, city))
                all_statistics.append(_extract_statistic_data(hotel, today))

    logger.info(f"Итого (по городам): {len(all_hotels)} отелей")
    return all_hotels, all_statistics


async def parse_and_save_hotels(
    cities: list[str] | None = None,
    days_ahead: int = 1,
    use_regions: bool = True,
) -> dict:
    """Парсинг и сохранение данных об отелях.

    Args:
        cities: Список городов (только для city-режима)
        days_ahead: Количество дней вперёд
        use_regions: True — региональный режим (200+ отелей), False — по городам
    """
    if use_regions and cities is None:
        logger.info(f"Региональный парсинг: {REGION_SLUGS}")
        hotels, statistics = await fetch_hotels_by_region(
            days_ahead=days_ahead,
        )
    else:
        if cities is None:
            cities = list(CITY_DISTRICTS_EN.keys())
        logger.info(f"Парсинг по городам: {cities}")
        hotels, statistics = await fetch_hotels_by_cities(cities, days_ahead)

    hotels_saved = await _save_hotels(hotels)
    stats_saved = await _save_statistics(statistics)

    logger.info(f"Сохранено: {hotels_saved} отелей, {stats_saved} статистик")

    return {
        "hotels_count": len(hotels),
        "hotels_saved": hotels_saved,
        "statistics_count": len(statistics),
        "statistics_saved": stats_saved,
        "mode": "region" if (use_regions and cities is None) else "city",
    }
