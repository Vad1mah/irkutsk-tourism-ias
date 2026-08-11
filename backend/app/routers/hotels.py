from fastapi import APIRouter, Query, HTTPException
from datetime import date
from pydantic import ValidationError
import logging

from app.models.schemas import (
    Hotel,
    HotelStatistics,
    HotelSegmentBenchmarkHotel,
    HotelSegmentBenchmarkResponse,
    HotelSegmentBenchmarkSegment,
    HotelSegmentMetrics,
    SegmentAvgMetrics,
)
from app.dependencies import DataServiceDep, CacheServiceDep
from app.constants import SEGMENT_WINDOW_DAYS, VALID_DISTRICTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hotels", tags=["hotels"])


@router.get("")
async def get_hotels(
    data_svc: DataServiceDep,
    cache_svc: CacheServiceDep,
    city: str | None = Query(None, description="Фильтр по городу"),
    district: str | None = Query(None, description="Фильтр по району"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Получить список отелей с пагинацией."""
    if district and district not in VALID_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    cache_key = cache_svc.cache_key("hotels", city, district, limit, offset)
    cached = await cache_svc.get(cache_key)
    if cached:
        return cached

    hotels, total = await data_svc.get_hotels(city=city, district=district, limit=limit, offset=offset)
    response = {
        "items": [h.model_dump() for h in hotels],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }
    await cache_svc.set(cache_key, response, ttl=300)
    return response



@router.get("/{hotel_id}", response_model=Hotel)
async def get_hotel(hotel_id: str, data_svc: DataServiceDep):
    """Получить один отель по ID."""
    hotel = await data_svc.get_hotel_by_id(hotel_id)
    if not hotel:
        raise HTTPException(404, "Отель не найден")
    return hotel


@router.get("/{hotel_id}/statistics", response_model=list[HotelStatistics])
async def get_hotel_statistics(
    hotel_id: str,
    data_svc: DataServiceDep,
    cache_svc: CacheServiceDep,
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата конца (YYYY-MM-DD)"),
):
    """Получить статистику загруженности отеля (с кэшированием)."""
    try:
        date_from_parsed = date.fromisoformat(date_from) if date_from else None
        date_to_parsed = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        raise HTTPException(400, "Неверный формат даты. Ожидается YYYY-MM-DD")

    cache_key = cache_svc.cache_key("hotel_stats", hotel_id, date_from, date_to)
    cached = await cache_svc.get(cache_key)
    if cached:
        return [HotelStatistics(**s) for s in cached]

    stats = await data_svc.get_hotel_statistics(
        hotel_id=hotel_id,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
    )
    await cache_svc.set(cache_key, [s.model_dump() for s in stats], ttl=600)
    return stats


@router.get("/{hotel_id}/segment-benchmark", response_model=HotelSegmentBenchmarkResponse)
async def hotel_segment_benchmark(
    hotel_id: str,
    data_svc: DataServiceDep,
    cache_svc: CacheServiceDep,
) -> HotelSegmentBenchmarkResponse:
    """Сравнение отеля с сегментом «район × размерная категория».

    Метрики объекта берутся из его последнего снимка (`as_of`), метрики сегмента —
    из последних снимков соседей за окно `segment_window_days` дней. Снимок объекта
    может быть заметно старше окна сегмента, поэтому дата возвращается явно.
    """
    cache_key = f"hotels:segment-benchmark:{hotel_id}"
    cached = await cache_svc.get(cache_key)
    if cached:
        try:
            return HotelSegmentBenchmarkResponse(**cached)
        except ValidationError:
            logger.warning("Corrupted segment-benchmark cache for %s, recalculating", hotel_id)

    hotel = await data_svc.get_hotel_by_id(hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    own_stats = await data_svc.get_hotel_latest_stats(hotel_id)
    hotel_dict = hotel.model_dump()
    rooms_num = own_stats.get("rooms_num") or hotel_dict.get("rooms_num") or 0
    if rooms_num and rooms_num <= 15:
        size_bucket = "mini"
    elif rooms_num and rooms_num <= 50:
        size_bucket = "mid"
    else:
        size_bucket = "large"
    district = hotel_dict.get("district")

    segment = await data_svc.compute_segment_metrics(
        district=district,
        size_bucket=size_bucket,
        exclude_hotel_id=hotel_id,
    )

    response = HotelSegmentBenchmarkResponse(
        hotel=HotelSegmentBenchmarkHotel(
            id=hotel_id,
            name=hotel_dict.get("name"),
            district=district,
            rooms_num=rooms_num if rooms_num else None,
        ),
        segment=HotelSegmentBenchmarkSegment(district=district, size_bucket=size_bucket),
        hotel_metrics=HotelSegmentMetrics(
            occupancy=own_stats.get("occupancy"),
            min_price=own_stats.get("min_price"),
        ),
        segment_metrics=SegmentAvgMetrics(
            n=segment.get("n", 0),
            avg_occupancy=segment.get("avg_occupancy"),
            avg_price=segment.get("avg_price"),
        ),
        n_in_segment=segment.get("n", 0),
        as_of=own_stats.get("date"),
        segment_window_days=segment.get("window_days", SEGMENT_WINDOW_DAYS),
    )
    await cache_svc.set(cache_key, response.model_dump(), ttl=600)
    return response
