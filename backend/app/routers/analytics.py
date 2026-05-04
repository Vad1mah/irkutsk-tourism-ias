"""API для продвинутой аналитики."""
import asyncio
import csv
import io
import time
from datetime import date, date as _date, timedelta
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from collections import defaultdict
import logging

from app.constants import VALID_DISTRICTS, CITY_TO_DISTRICT, DEFAULT_DISTRICT, DISTRICT_CENTERS, SEASON_MONTHS, MIN_SAMPLES_PER_MONTH
from app.services.methodology_service import methodology_service
from app.dependencies import (
    DataServiceDep, WeatherServiceDep, EnsembleServiceDep, CacheServiceDep,
)
from app.services.protocols import DataServiceProtocol
from pydantic import ValidationError
from app.models.schemas import (
    KPIResponse, CityHotels,
    TripSummary, EventBrief, WeatherDay, BestDate,
    AnalyticsMetadataResponse, DataDateRange, GapPeriod,
    BookingPacePoint, BookingPaceSummary, BookingPaceResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

TOURIST_DISTRICTS = set(VALID_DISTRICTS)

_forecast_locks: dict[str, asyncio.Lock] = {}
_forecast_results: dict[str, tuple[float, dict]] = {}
_FORECAST_TTL = 300
_MAX_CACHE = 50


def _evict_expired(cache: dict, ttl: float) -> None:
    now = time.time()
    expired = [k for k, (ts, _) in cache.items() if now - ts > ttl]
    for k in expired:
        cache.pop(k, None)
        _forecast_locks.pop(k, None)
    if len(cache) >= _MAX_CACHE:
        oldest = min(cache, key=lambda k: cache[k][0])
        del cache[oldest]
        _forecast_locks.pop(oldest, None)


async def _get_shared_forecast(
    data: Any,
    weather_svc: Any,
    ensemble_svc: Any,
    district: str,
    days: int,
) -> dict:
    """Ensemble прогноз с дедупликацией: второй запрос ждёт первый."""
    key = f"{district}:{days}"
    now = time.time()

    if key in _forecast_results:
        ts, result = _forecast_results[key]
        if now - ts < _FORECAST_TTL:
            return result

    if key not in _forecast_locks:
        _forecast_locks[key] = asyncio.Lock()

    async with _forecast_locks[key]:
        if key in _forecast_results:
            ts, result = _forecast_results[key]
            if now - ts < _FORECAST_TTL:
                return result

        history = await data.get_occupancy_by_district(district)
        history_dicts = [
            {"date": r["date"], "occupancy": r["avg_occupancy"]}
            for r in history if r.get("avg_occupancy") is not None
        ]
        if len(history_dicts) < 14:
            return {}

        forecast_dates = [date.today() + timedelta(days=i) for i in range(days)]
        weather_data = await weather_svc.get_weather_for_dates(forecast_dates)
        result = await ensemble_svc.forecast_ensemble_async(
            history=history_dicts,
            days_ahead=days,
            weather_data=weather_data,
            method="weighted_average",
            district=district,
        )
        _evict_expired(_forecast_results, _FORECAST_TTL)
        _forecast_results[key] = (time.time(), result)
        return result


def _get_month_name(month: int) -> str:
    """Получить название месяца."""
    months = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", 
              "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    return months[month - 1] if 1 <= month <= 12 else "?"


def _get_season(month: int) -> str:
    """Определить сезон по месяцу."""
    for season, months in SEASON_MONTHS.items():
        if month in months:
            return season
    return "autumn"


@router.get("/correlation")
async def get_correlation_data(
    data: DataServiceDep,
    cache: CacheServiceDep,
    year: int | None = None,
) -> dict[str, Any]:
    """
    Получить данные корреляции событий и загруженности из БД.

    Args:
        year: Год для фильтрации (None = все годы)

    Включает информацию о пропущенных периодах данных.
    """
    cache_key = f"analytics:correlation:{year}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    stats, events_data = await asyncio.gather(
        data.get_monthly_statistics(year=year),
        data.get_events_by_month(year=year),
    )

    all_stats = (await data.get_monthly_statistics()) if year else stats
    available_years = sorted(set(
        int(row.get("date_str", "")[:4]) 
        for row in all_stats 
        if row.get("date_str") and len(row.get("date_str", "")) >= 4
    ))
    
    if not stats:
        return {
            "months": [],
            "correlation_coefficient": None,
            "avg_occupancy": None,
            "peak_month": None,
            "low_month": None,
            "missing_periods": [],
            "available_years": available_years,
            "selected_year": year,
            "message": f"Нет данных статистики{f' за {year} год' if year else ''}"
        }
    
    # Агрегируем по месяцам
    monthly_stats = defaultdict(lambda: {"occupancy": [], "price": [], "events": 0})
    
    for row in stats:
        date_str = row.get("date_str", "")
        if len(date_str) >= 7:  # "2025-01" -> month = "01"
            try:
                row_year = int(date_str[:4])
                month = int(date_str[5:7])
                # Фильтр по году (если указан)
                if year and row_year != year:
                    continue
                monthly_stats[month]["occupancy"].append(row.get("avg_occupancy", 0) or 0)
                monthly_stats[month]["price"].append(row.get("avg_price", 0) or 0)
            except (ValueError, IndexError):
                continue
    
    # Подсчёт событий по месяцам
    for row in events_data:
        date_str = row.get("date_str", "")
        if len(date_str) >= 7:
            try:
                row_year = int(date_str[:4])
                month = int(date_str[5:7])
                if year and row_year != year:
                    continue
                monthly_stats[month]["events"] += row.get("events_count", 0) or 0
            except (ValueError, IndexError):
                continue
    
    # Формируем результат
    months_data = []
    missing_periods = []  # Пропущенные периоды

    for month in range(1, 13):
        month_data = monthly_stats.get(month, {"occupancy": [], "price": [], "events": 0})
        occupancies = month_data["occupancy"]
        prices = month_data["price"]

        samples = len(occupancies)
        avg_occ = round(sum(occupancies) / samples, 1) if occupancies else 0
        avg_price = round(sum(prices) / len(prices)) if prices else 0

        has_data = samples > 0
        is_gap = samples < MIN_SAMPLES_PER_MONTH

        months_data.append({
            "month": _get_month_name(month),
            "occupancy": avg_occ,
            "avgPrice": avg_price,
            "events": month_data["events"],
            "season": _get_season(month),
            "hasData": has_data,
            "samples": samples,
            "is_gap": is_gap,
        })

        # Если нет данных или gap — добавляем в missing_periods
        if not has_data:
            missing_periods.append({
                "month": _get_month_name(month),
                "monthIndex": month,
                "reason": "Парсер был неактивен" if year == 2025 and month in [7, 8, 9] else "Нет данных",
            })
        elif is_gap:
            missing_periods.append({
                "month": _get_month_name(month),
                "monthIndex": month,
                "reason": f"Малая выборка ({samples} записей)",
            })

    # Расчёт корреляции Пирсона только по месяцам с достаточной выборкой
    filtered_pairs = [
        (m["events"], m["occupancy"])
        for m in months_data
        if not m["is_gap"] and m["occupancy"] is not None
    ]

    correlation: float | None = None
    if len(filtered_pairs) >= 3:
        n = len(filtered_pairs)
        events_vals = [p[0] for p in filtered_pairs]
        occ_vals = [p[1] for p in filtered_pairs]

        mean_occ = sum(occ_vals) / n
        mean_evt = sum(events_vals) / n

        numerator = sum((o - mean_occ) * (e - mean_evt) for e, o in filtered_pairs)
        denom_occ = sum((o - mean_occ) ** 2 for o in occ_vals) ** 0.5
        denom_evt = sum((e - mean_evt) ** 2 for e in events_vals) ** 0.5

        if denom_occ * denom_evt > 0:
            correlation = round(numerator / (denom_occ * denom_evt), 2)

    # Пик и минимум (только из месяцев с достаточными данными)
    valid_months = [m for m in months_data if not m["is_gap"] and m["occupancy"] > 0]
    peak_month = max(valid_months, key=lambda x: x["occupancy"])["month"] if valid_months else None
    low_month = min(valid_months, key=lambda x: x["occupancy"])["month"] if valid_months else None

    avg_occupancy = round(sum(m["occupancy"] for m in valid_months) / len(valid_months), 1) if valid_months else None

    result = {
        "months": months_data,
        "correlation_coefficient": correlation,
        "avg_occupancy": avg_occupancy,
        "peak_month": peak_month,
        "low_month": low_month,
        "missing_periods": missing_periods,
        "data_coverage": f"{len(valid_months)}/12 месяцев",
        "available_years": available_years,
        "selected_year": year,
    }
    await cache.set(cache_key, result, ttl=300)
    return result


@router.get("/districts")
async def get_districts_data(data: DataServiceDep, cache: CacheServiceDep) -> list[dict[str, Any]]:
    """
    Получить статистику по районам из БД.
    Фильтруем только туристически значимые районы Байкала.
    """
    cache_key = "analytics:districts"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    # Сначала пробуем полную статистику
    districts = await data.get_districts_statistics()

    # Если нет статистики — берём хотя бы количество отелей
    if not districts:
        districts_basic = await data.get_hotels_by_district()
        result = [
            {
                "district": row.get("district"),
                "occupancy": 0,
                "freeRooms": 0,
                "totalRooms": 0,
                "avgPrice": 0,
                "hotelsCount": row.get("hotels_count", 0) or 0,
            }
            for row in districts_basic 
            if row.get("district") and row.get("district") in TOURIST_DISTRICTS
        ]
        await cache.set(cache_key, result, ttl=120)
        return result
    
    result = []
    for row in districts:
        district = row.get("district")
        # Фильтруем только туристические районы
        if not district or district not in TOURIST_DISTRICTS:
            continue
            
        total_rooms = row.get("total_rooms", 0) or 0
        free_rooms = row.get("free_rooms", 0) or 0
        avg_occupancy = row.get("avg_occupancy", 0) or 0
        avg_price = row.get("avg_price", 0) or 0
        
        count = row.get("hotels_count", 0) or 0
        result.append({
            "district": district,
            "occupancy": round(avg_occupancy, 1),
            "freeRooms": int(free_rooms),
            "totalRooms": int(total_rooms),
            "avgPrice": round(avg_price),
            "hotelsCount": count,
            "confidence": "high" if count >= 10 else "medium" if count >= 3 else "low",
        })
    
    await cache.set(cache_key, result, ttl=120)
    return result


@router.get("/recommendations")
async def get_recommendations(data: DataServiceDep, cache: CacheServiceDep) -> list[dict[str, Any]]:
    """
    Генерировать рекомендации на основе реальных данных из БД.
    """
    cache_key = "analytics:recommendations"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    districts, stats = await asyncio.gather(
        data.get_districts_statistics(),
        data.get_monthly_statistics(),
    )

    recommendations = []
    
    # Анализ районов (только туристические)
    if districts:
        # Фильтруем только туристические районы
        tourist_districts = [
            d for d in districts 
            if d.get("district") in TOURIST_DISTRICTS
        ]
        # Найти район с минимальной загрузкой для туристов
        valid_districts = [d for d in tourist_districts if (d.get("avg_occupancy") or 0) > 0]
        if valid_districts:
            min_occ_district = min(valid_districts, key=lambda x: x.get("avg_occupancy", 100))
            max_occ_district = max(valid_districts, key=lambda x: x.get("avg_occupancy", 0))
            
            if min_occ_district.get("district"):
                recommendations.append({
                    "type": "tourist",
                    "title": f"Отдых в {min_occ_district['district']} районе",
                    "description": f"Низкая загруженность ({round(min_occ_district.get('avg_occupancy', 0))}%) — больше свободных номеров и меньше очередей.",
                    "period": "Сейчас",
                    "savings": f"{100 - round(min_occ_district.get('avg_occupancy', 0))}% номеров свободно",
                })
            
            if max_occ_district.get("district") and max_occ_district.get("avg_occupancy", 0) > 50:
                recommendations.append({
                    "type": "hotelier",
                    "title": f"Высокий спрос в {max_occ_district['district']} районе",
                    "description": f"Загруженность {round(max_occ_district.get('avg_occupancy', 0))}% — можно повысить цены.",
                    "period": "Текущий период",
                    "increase": f"+{round(max_occ_district.get('avg_occupancy', 0) / 5)}% к цене",
                })
    
    # Анализ сезонности по данным
    if stats:
        monthly_avg = defaultdict(list)
        for row in stats:
            date_str = row.get("date_str", "")
            if len(date_str) >= 7:
                try:
                    month = int(date_str[5:7])
                    monthly_avg[month].append(row.get("avg_occupancy", 0) or 0)
                except (ValueError, IndexError):
                    continue
        
        if monthly_avg:
            month_averages = {m: sum(v)/len(v) for m, v in monthly_avg.items() if v}
            
            if month_averages:
                current_month = date.today().month
                peak_month = max(month_averages, key=month_averages.get)
                low_month = min(month_averages, key=month_averages.get)
                
                # Определяем временную привязку (прошёл месяц или нет)
                def _month_period(m: int) -> str:
                    if m > current_month:
                        return _get_month_name(m)
                    elif m == current_month:
                        return f"{_get_month_name(m)} (сейчас)"
                    else:
                        return f"{_get_month_name(m)} (следующий год)"
                
                recommendations.append({
                    "type": "tourist",
                    "title": f"Лучшее время для поездки — {_get_month_name(low_month)}",
                    "description": f"Минимальная загруженность ({round(month_averages[low_month])}%) и низкие цены.",
                    "period": _month_period(low_month),
                    "savings": f"до {round(100 - month_averages[low_month])}% экономии",
                })
                
                recommendations.append({
                    "type": "hotelier",
                    "title": f"Пик сезона — {_get_month_name(peak_month)}",
                    "description": f"Загруженность {round(month_averages[peak_month])}%. Оптимальное время для повышения цен.",
                    "period": _month_period(peak_month),
                    "increase": f"+{round(month_averages[peak_month] / 4)}% к цене",
                })
    
    if not recommendations:
        recommendations = [{
            "type": "info",
            "title": "Недостаточно данных",
            "description": "Для генерации рекомендаций необходимо больше данных.",
            "period": "—",
        }]

    await cache.set(cache_key, recommendations, ttl=300)
    return recommendations


@router.get("/kpi", response_model=KPIResponse)
async def get_kpi(data: DataServiceDep, cache: CacheServiceDep) -> KPIResponse:
    """
    Получить ключевые метрики из БД.
    """
    cache_key = "analytics:kpi"
    cached = await cache.get(cache_key)
    if cached:
        try:
            return KPIResponse(**cached)
        except (ValidationError, TypeError):
            logger.warning("Corrupted KPI cache, recalculating")

    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    metrics, districts = await asyncio.gather(
        data.get_total_metrics(),
        data.get_districts_statistics(),
    )

    # Расчёт общих показателей
    total_rooms = sum(d.get("total_rooms", 0) or 0 for d in districts) if districts else 0
    free_rooms = sum(d.get("free_rooms", 0) or 0 for d in districts) if districts else 0
    avg_occupancy = 0.0
    avg_price = None
    if districts:
        occupancies = [d.get("avg_occupancy", 0) or 0 for d in districts if d.get("avg_occupancy")]
        avg_occupancy = round(sum(occupancies) / len(occupancies), 1) if occupancies else 0.0
        prices = [d.get("avg_price", 0) or 0 for d in districts if d.get("avg_price")]
        avg_price = round(sum(prices) / len(prices)) if prices else None

    result = KPIResponse(
        total_hotels=metrics.get("total_hotels", 0) or 0,
        total_cities=metrics.get("total_cities", 0) or 0,
        total_events=metrics.get("total_events", 0) or 0,
        total_rooms=total_rooms,
        free_rooms=free_rooms,
        avg_occupancy=avg_occupancy,
        avg_price=avg_price,
    )
    await cache.set(cache_key, result.model_dump(), ttl=300)
    return result


@router.get("/events-impact")
async def get_events_impact(
    data: DataServiceDep,
    cache: CacheServiceDep,
    method: Literal["naive", "seasonal_corrected"] = "seasonal_corrected",
    window_weeks: int = Query(3, ge=1, le=52, description="Окно для baseline-расчёта (недели). Используется в seasonal_corrected."),
) -> list[dict[str, Any]]:
    """Влияние событий на загруженность: сравнение в дни событий vs обычные дни.

    Args:
        method: Метод расчёта. ``naive`` — простая разница event_day vs avg.
            ``seasonal_corrected`` — скорректированный baseline по weekday ±window_weeks недель,
            исключая дни других событий.
        window_weeks: Размер окна для baseline (недели), только для seasonal_corrected.
    """
    cache_key = f"analytics:events-impact:{DEFAULT_DISTRICT}:{method}:{window_weeks}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if method == "naive":
        result = await _events_impact_naive(data)
    else:
        result = await _events_impact_seasonal_corrected(data, window_weeks=window_weeks)

    await cache.set(cache_key, result, ttl=300)
    return result


def _resolve_district(e: dict) -> str:
    """Резолвит район из event-dict: либо явный district, либо CITY_TO_DISTRICT по location."""
    d = e.get("district")
    if d:
        return d
    location = (e.get("location") or "").lower()
    return next(
        (dist for city, dist in CITY_TO_DISTRICT.items() if city in location),
        DEFAULT_DISTRICT,
    )


def _to_date(val: object) -> _date | None:
    """Конвертирует строку/date в _date, возвращает None при ошибке."""
    if val is None:
        return None
    if isinstance(val, _date):
        return val
    try:
        return _date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


async def _events_impact_seasonal_corrected(
    data: DataServiceProtocol,
    window_weeks: int = 3,
) -> list[dict[str, Any]]:
    """Corrected impact: baseline по weekday в окне ±N недель, исключая другие event-дни."""
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    events = await data.get_events()
    if not events:
        return []

    # Карта occupancy по районам (резолвим район через _resolve_district)
    districts = {_resolve_district(e) for e in events if e.get("date_start")}
    history_per_district: dict[str, list[tuple[_date, float]]] = {}
    for d in districts:
        rows = await data.get_occupancy_by_district(d)
        history_per_district[d] = [
            (r["date"], r["avg_occupancy"])
            for r in rows
            if r.get("avg_occupancy") is not None
        ]

    # Множество дат-событий для исключения из baseline (с поддержкой многодневных событий)
    event_dates_per_district: dict[str, set[_date]] = {}
    for e in events:
        d = _resolve_district(e)
        ds = _to_date(e.get("date_start"))
        de = _to_date(e.get("date_end")) or ds
        if not ds:
            continue
        cur = ds
        while cur <= de:
            event_dates_per_district.setdefault(d, set()).add(cur)
            cur += timedelta(days=1)

    result: list[dict[str, Any]] = []
    for e in events:
        d = _resolve_district(e)
        ds = _to_date(e.get("date_start"))
        if not ds:
            continue
        history = history_per_district.get(d, [])
        observed = next((occ for dd, occ in history if dd == ds), None)
        if observed is None:
            continue
        baseline = methodology_service.compute_seasonal_baseline(
            target_date=ds,
            target_weekday=ds.weekday(),
            occupancy_history=history,
            event_dates=event_dates_per_district.get(d, set()),
            window_weeks=window_weeks,
        )
        impact = methodology_service.corrected_impact(observed=observed, baseline=baseline)
        result.append({
            "event": e.get("title"),
            "date": ds.isoformat(),
            "district": d,
            "occupancy_on_day": round(observed, 2),
            **impact,
        })

    # Сортировка по модулю delta_pct убыв.
    result.sort(key=lambda r: abs(r.get("delta_pct") or 0), reverse=True)
    return result


async def _events_impact_naive(data: DataServiceProtocol) -> list[dict[str, Any]]:
    """Наивный расчёт влияния событий: разница загруженности в день события vs среднее."""
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    default_occ = await data.get_occupancy_by_district(DEFAULT_DISTRICT)
    if not default_occ:
        return []
    occ_dates = [row["date"] for row in default_occ if row.get("date")]
    if not occ_dates:
        return []
    data_start = min(occ_dates)
    data_end = max(occ_dates)

    events = await data.get_events(date_from=data_start, date_to=data_end)
    if not events:
        return []

    district_occupancy_cache: dict[str, list[dict]] = {DEFAULT_DISTRICT: default_occ}

    async def _get_district_occupancy(district: str) -> list[dict]:
        if district not in district_occupancy_cache:
            district_occupancy_cache[district] = await data.get_occupancy_by_district(district)
        return district_occupancy_cache[district]

    def _find_nearest_occupancy(occ_map: dict, target: date, max_delta: int = 3) -> float | None:
        for delta in range(max_delta + 1):
            for d in (target + timedelta(days=delta), target - timedelta(days=delta)):
                if d in occ_map:
                    return occ_map[d]
        return None

    seen_dates: set[date] = set()
    diverse_events = []
    for event in events:
        ds = event.get("date_start")
        if isinstance(ds, str):
            try:
                ds = date.fromisoformat(ds[:10])
            except ValueError:
                continue
        if ds and ds not in seen_dates:
            seen_dates.add(ds)
            diverse_events.append(event)
        if len(diverse_events) >= 30:
            break

    result = []
    for event in diverse_events:
        title = event.get("title", "")
        date_start = event.get("date_start")

        if not date_start:
            continue

        district = _resolve_district(event)

        if isinstance(date_start, str):
            try:
                date_start = date.fromisoformat(date_start[:10])
            except ValueError:
                continue

        date_str = date_start.strftime("%d.%m") if isinstance(date_start, date) else str(date_start)[:10]

        occupancy_data = await _get_district_occupancy(district)
        occupancy_map = {row["date"]: row["avg_occupancy"] for row in occupancy_data}

        event_day_occ = occupancy_map.get(date_start) or _find_nearest_occupancy(occupancy_map, date_start)
        all_values = [v for v in occupancy_map.values() if v is not None]
        avg_occ = round(sum(all_values) / len(all_values), 1) if all_values else None

        impact = None
        if event_day_occ is not None and avg_occ is not None:
            impact = round(event_day_occ - avg_occ, 1)

        if impact is None:
            continue

        result.append({
            "event": title[:50] if title else "Событие",
            "date": date_str,
            "district": district,
            "source": event.get("source_id", ""),
            "occupancy_on_day": round(event_day_occ, 1) if event_day_occ else None,
            "avg_occupancy": avg_occ,
            "impact": impact,
        })

    result.sort(key=lambda x: abs(x.get("impact") or 0), reverse=True)
    return result


@router.get("/hotels-by-city", response_model=list[CityHotels])
async def get_hotels_by_city(data: DataServiceDep) -> list[CityHotels]:
    """Получить распределение отелей по городам."""
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    hotels_data = await data.get_hotels_by_city()
    return [CityHotels(city=row.get("city", ""), count=row.get("hotels_count", 0) or 0) for row in hotels_data if row.get("city")]


@router.get("/hotels-by-district")
async def get_hotels_by_district(data: DataServiceDep) -> list[dict[str, Any]]:
    """
    Получить распределение отелей по районам с ценами.
    Возвращает: district, count, avg_price, avg_rating
    """
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    # Получаем количество отелей
    district_counts = await data.get_hotels_by_district()

    # Получаем статистику с ценами
    district_stats = await data.get_districts_statistics()
    
    # Создаём словарь цен по районам
    price_lookup = {
        row.get("district"): row.get("avg_price", 0) or 0
        for row in (district_stats or [])
        if row.get("district")
    }
    
    result = []
    for row in district_counts:
        district = row.get("district")
        if not district or district not in TOURIST_DISTRICTS:
            continue
        result.append({
            "district": district,
            "count": row.get("hotels_count", 0) or 0,
            "avg_price": price_lookup.get(district, None),
            "avg_rating": row.get("avg_rating"),
        })
    
    return result


@router.get("/heatmap")
async def get_heatmap_data(data: DataServiceDep, cache: CacheServiceDep, days: int = 14) -> dict[str, Any]:
    """Получить данные для тепловой карты загруженности (районы x даты)."""
    if days < 1 or days > 90:
        raise HTTPException(400, "days должен быть от 1 до 90")

    cache_key = f"analytics:heatmap:{days}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    from datetime import timedelta

    # Получаем данные по всем районам (только туристические)
    districts_data = await data.get_districts_statistics()
    if not districts_data:
        return {"data": [], "districts": [], "dates": []}

    # Фильтруем только туристические районы
    districts = [
        d.get("district") for d in districts_data
        if d.get("district") and d.get("district") in TOURIST_DISTRICTS
    ]

    # Параллельное получение данных по всем районам (вместо N+1)
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    async def fetch_district_data(district: str):
        try:
            return district, await data.get_occupancy_by_district(district)
        except Exception as e:
            logger.error(f"Failed to get data for {district}: {e}")
            return district, []

    results = await asyncio.gather(*[fetch_district_data(d) for d in districts])

    all_dates = [str(start_date + timedelta(days=i)) for i in range(days + 1)]

    heatmap_data = []
    for district, history in results:
        occ_map: dict[str, float] = {}
        for row in history:
            row_date = row.get("date")
            if row_date and start_date <= row_date <= end_date:
                occ_map[str(row_date)] = round(row.get("avg_occupancy", 0) or 0, 1)

        last_val = None
        for d in all_dates:
            if d in occ_map:
                last_val = occ_map[d]
            if last_val is not None:
                heatmap_data.append({
                    "district": district,
                    "date": d,
                    "occupancy": occ_map.get(d, last_val),
                })

    result = {
        "data": heatmap_data,
        "districts": districts,
        "dates": all_dates,
    }
    await cache.set(cache_key, result, ttl=120)
    return result


@router.get("/data-coverage")
async def get_data_coverage(
    data: DataServiceDep,
    district: str = DEFAULT_DISTRICT,
) -> dict[str, Any]:
    """Проверить покрытие данных по загрузке отелей."""
    if district and district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    from collections import defaultdict

    # Получаем все данные по району
    history_data = await data.get_occupancy_by_district(district)

    if not history_data:
        return {
            "district": district,
            "has_data": False,
            "message": "Нет данных по этому району",
            "date_range": None,
            "gaps": [],
            "monthly_coverage": [],
        }

    # Собираем все даты
    dates = []
    by_month = defaultdict(list)

    for row in history_data:
        d = row.get("date")
        if d:
            dates.append(d)
            month_key = f"{d.year}-{d.month:02d}"
            by_month[month_key].append(row.get("avg_occupancy", 0))

    if not dates:
        return {
            "district": district,
            "has_data": False,
            "message": "Нет валидных дат в данных",
            "date_range": None,
            "gaps": [],
            "monthly_coverage": [],
        }

    # Определяем диапазон
    min_date = min(dates)
    max_date = max(dates)

    # Ищем пропуски (gaps) — месяцы без данных внутри диапазона
    gaps = []
    current = date(min_date.year, min_date.month, 1)
    end = date(max_date.year, max_date.month, 1)

    while current <= end:
        month_key = f"{current.year}-{current.month:02d}"
        if month_key not in by_month:
            gaps.append({
                "month": month_key,
                "year": current.year,
                "month_num": current.month,
            })

        # Следующий месяц
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    # Статистика по месяцам
    monthly_coverage = []
    for month_key in sorted(by_month.keys()):
        values = by_month[month_key]
        monthly_coverage.append({
            "month": month_key,
            "days_count": len(values),
            "avg_occupancy": round(sum(values) / len(values), 1) if values else 0,
            "min_occupancy": round(min(values), 1) if values else 0,
            "max_occupancy": round(max(values), 1) if values else 0,
        })

    return {
        "district": district,
        "has_data": True,
        "date_range": {
            "start": str(min_date),
            "end": str(max_date),
            "total_days": len(dates),
        },
        "gaps": gaps,
        "gaps_count": len(gaps),
        "monthly_coverage": monthly_coverage,
    }


@router.get("/metadata", response_model=AnalyticsMetadataResponse)
async def get_metadata(
    data: DataServiceDep,
    cache: CacheServiceDep,
) -> AnalyticsMetadataResponse:
    """Метаданные системы: счётчики, диапазон данных, gap-периоды."""
    cache_key = "analytics:metadata"
    cached = await cache.get(cache_key)
    if cached:
        return AnalyticsMetadataResponse.model_validate(cached)

    hotels, events, date_range, gaps, last = await asyncio.gather(
        data.get_hotels_count(),
        data.get_events_count(),
        data.get_data_date_range(),
        data.detect_gap_periods(min_days=7),
        data.get_last_data_refresh(),
    )

    response = AnalyticsMetadataResponse(
        hotels_count=hotels,
        events_count=events,
        data_range=DataDateRange(**date_range),
        last_refresh=last.isoformat() if last else None,
        gap_periods=[GapPeriod(**g) for g in gaps],
    )
    await cache.set(cache_key, response.model_dump(by_alias=True), ttl=300)
    return response


@router.get("/price-history")
async def get_price_history(
    data: DataServiceDep,
    district: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """
    Получить историю цен на отели.

    Args:
        district: Район (None = все районы)
        days: Количество дней истории (1-365)

    Returns:
        История цен по датам и тренд
    """
    if days < 1 or days > 365:
        raise HTTPException(400, "days должен быть от 1 до 365")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    from datetime import timedelta
    from collections import defaultdict

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Получаем данные
    if district:
        if district not in TOURIST_DISTRICTS:
            raise HTTPException(400, f"Неизвестный район: {district}")
        history = await data.get_occupancy_by_district(district)
    else:
        # Все туристические районы - параллельный запрос
        async def fetch_dist_data(dist):
            try:
                return await data.get_occupancy_by_district(dist)
            except Exception as e:
                logger.error(f"Failed to get data for {dist}: {e}")
                return []

        results = await asyncio.gather(*[fetch_dist_data(d) for d in TOURIST_DISTRICTS])
        history = []
        for dist_history in results:
            history.extend(dist_history)

    if not history:
        return {
            "district": district or "all",
            "prices": [],
            "trend": None,
            "message": "Нет данных о ценах",
        }

    # Агрегируем по датам
    daily_prices = defaultdict(list)
    for row in history:
        row_date = row.get("date")
        price = row.get("avg_price") or row.get("min_price")
        if row_date and price and start_date <= row_date <= end_date:
            daily_prices[str(row_date)].append(price)

    # Формируем результат
    prices = []
    for date_str in sorted(daily_prices.keys()):
        prices_list = daily_prices[date_str]
        avg_price = round(sum(prices_list) / len(prices_list)) if prices_list else 0
        prices.append({
            "date": date_str,
            "avg_price": avg_price,
            "min_price": min(prices_list) if prices_list else 0,
            "max_price": max(prices_list) if prices_list else 0,
            "samples": len(prices_list),
        })

    # Расчёт тренда (последние 7 дней vs предыдущие 7 дней)
    trend = None
    if len(prices) >= 14:
        recent = [p["avg_price"] for p in prices[-7:]]
        previous = [p["avg_price"] for p in prices[-14:-7]]
        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)
        change_pct = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
        trend = {
            "direction": "up" if change_pct > 2 else "down" if change_pct < -2 else "stable",
            "change_percent": round(change_pct, 1),
            "recent_avg": round(recent_avg),
            "previous_avg": round(previous_avg),
        }

    return {
        "district": district or "all",
        "prices": prices,
        "trend": trend,
        "period": {
            "start": str(start_date),
            "end": str(end_date),
            "days": days,
        },
    }


@router.get("/trip-summary", response_model=TripSummary)
async def get_trip_summary(
    data: DataServiceDep,
    weather_svc: WeatherServiceDep,
    ensemble_svc: EnsembleServiceDep,
    cache: CacheServiceDep,
    district: str = DEFAULT_DISTRICT,
    days: int = 14,
) -> TripSummary:
    """Сводка для планирования поездки: прогноз + погода + события + отели."""
    if district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if days < 1 or days > 30:
        raise HTTPException(400, "days должен быть от 1 до 30")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    cache_key = f"trip_summary:{district}:{days}"
    cached = await cache.get(cache_key)
    if cached:
        try:
            return TripSummary(**cached)
        except (ValidationError, TypeError):
            logger.warning("Corrupted trip_summary cache, recalculating")

    forecast_occ = 50.0
    trend = "stable"
    forecast_source = "fallback"
    try:
        result = await _get_shared_forecast(data, weather_svc, ensemble_svc, district, days)
        points = result.get("ensemble", [])
        if points:
            values = [p.occupancy for p in points]
            forecast_occ = round(sum(values) / len(values), 1)
            forecast_source = "ensemble"
            if len(values) >= 2:
                first_half = sum(values[:len(values)//2]) / max(1, len(values)//2)
                second_half = sum(values[len(values)//2:]) / max(1, len(values) - len(values)//2)
                diff = second_half - first_half
                trend = "growing" if diff > 3 else "declining" if diff < -3 else "stable"
    except Exception as e:
        logger.error(f"Ensemble forecast failed for trip-summary: {e}")

    level = "low" if forecast_occ < 40 else "high" if forecast_occ > 70 else "medium"

    weather_days: list[WeatherDay] = []
    try:
        w = await weather_svc.get_forecast_weather(min(days, 16))
        for day in (w or [])[:days]:
            weather_days.append(WeatherDay(
                date=str(day.get("date", "")),
                temp_max=day.get("temperature_max", 0),
                temp_min=day.get("temperature_min", 0),
                weather_code=day.get("weather_code", 0),
                description=day.get("weather_description", ""),
            ))
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")

    top_events: list[EventBrief] = []
    events_count = 0
    try:
        today = date.today()
        events = await data.get_events(
            date_from=today,
            date_to=today + timedelta(days=days),
        )
        events_count = len(events)
        for ev in events[:3]:
            ds = ev.get("date_start")
            top_events.append(EventBrief(
                title=ev.get("title", "")[:60],
                date=str(ds) if ds else "",
                event_type=ev.get("event_type"),
            ))
    except Exception as e:
        logger.error(f"Events fetch failed: {e}")

    # available_hotels (имя в JSON для фронта): фактически SUM(free_rooms_amount) по району
    # из get_districts_statistics — суммарное число свободных номеров на последнюю дату, не число отелей.
    available_hotels = 0
    avg_price: float | None = None
    try:
        districts_stats = await data.get_districts_statistics()
        for d in districts_stats:
            if d.get("district") == district:
                available_hotels = d.get("free_rooms", 0) or 0
                avg_price = d.get("avg_price") or None
                break
    except Exception as e:
        logger.error(f"District stats failed: {e}")

    recs = {
        "low": f"Отличное время для поездки в {district} район! Загрузка всего {forecast_occ}% — много свободных номеров.",
        "medium": f"Умеренная загрузка в {district} районе ({forecast_occ}%). Номеров достаточно — можно выбирать без спешки.",
        "high": f"Высокая загрузка в {district} районе ({forecast_occ}%). Бронируйте как можно раньше!",
    }

    summary = TripSummary(
        district=district,
        forecast_occupancy=forecast_occ,
        occupancy_level=level,
        occupancy_trend=trend,
        forecast_source=forecast_source,
        weather=weather_days,
        events_count=events_count,
        top_events=top_events,
        available_hotels=available_hotels,
        avg_price=avg_price,
        recommendation=recs[level],
    )

    await cache.set(cache_key, summary.model_dump(), ttl=900)
    return summary


@router.get("/best-dates", response_model=list[BestDate])
async def get_best_dates(
    data: DataServiceDep,
    weather_svc: WeatherServiceDep,
    ensemble_svc: EnsembleServiceDep,
    cache: CacheServiceDep,
    district: str = DEFAULT_DISTRICT,
    days_ahead: int = 14,
) -> list[BestDate]:
    """Топ-5 лучших дат для поездки (минимальная прогнозная загрузка)."""
    if district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if days_ahead < 7 or days_ahead > 30:
        raise HTTPException(400, "days_ahead должен быть от 7 до 30")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    cache_key = f"best_dates:{district}:{days_ahead}"
    cached = await cache.get(cache_key)
    if cached:
        try:
            return [BestDate(**item) for item in cached]
        except (ValidationError, TypeError):
            logger.warning("Corrupted best_dates cache, recalculating")

    forecast_points: list[dict] = []
    try:
        result = await _get_shared_forecast(data, weather_svc, ensemble_svc, district, days_ahead)
        forecast_points = result.get("ensemble", [])
    except Exception as e:
        logger.error(f"Ensemble forecast failed for best-dates: {e}")

    if not forecast_points:
        return []

    weather_map: dict[str, float] = {}
    try:
        coords = DISTRICT_CENTERS.get(district)
        w = await weather_svc.get_forecast_weather(
            min(days_ahead, 16),
            lat=coords[0] if coords else None,
            lon=coords[1] if coords else None,
        )
        for day in w or []:
            weather_map[str(day.get("date", ""))] = day.get("temperature_max", 0)
    except Exception as e:
        logger.error(f"Weather fetch failed for best-dates: {e}")

    events_map: dict[str, list[str]] = defaultdict(list)
    try:
        today = date.today()
        events = await data.get_events(
            date_from=today,
            date_to=today + timedelta(days=days_ahead),
        )
        for ev in events:
            ds = ev.get("date_start")
            if ds:
                events_map[str(ds)].append(ev.get("title", "")[:40])
    except Exception as e:
        logger.error(f"Events fetch failed for best-dates: {e}")

    scored: list[BestDate] = []
    for point in forecast_points:
        d = str(point.date)
        occ = point.occupancy
        temp = weather_map.get(d)
        evts = events_map.get(d, [])

        score = max(0, 100 - occ)
        if temp is not None:
            score += min(20, max(-10, temp) * 0.7)
        if len(evts) > 0:
            score -= len(evts) * 3

        scored.append(BestDate(
            date=d,
            predicted_occupancy=round(occ, 1),
            weather_temp=round(temp, 1) if temp is not None else None,
            events=evts,
            score=round(max(0, min(100, score)), 1),
        ))

    # Фильтруем прошлые даты (I-2: best-dates не должны содержать вчерашние даты)
    today_str = str(date.today())
    scored = [s for s in scored if s.date >= today_str]

    scored.sort(key=lambda x: x.score, reverse=True)
    top5 = scored[:5]

    await cache.set(cache_key, [b.model_dump() for b in top5], ttl=1800)
    return top5


@router.get("/hotels-map")
async def analytics_hotels_map(
    data: DataServiceDep,
    cache: CacheServiceDep,
    district: str | None = Query(default=None, description="Район; без параметра — все отели с координатами"),
) -> dict[str, Any]:
    """Данные для карты: отели с координатами + загрузка по районам."""
    if not data.is_connected:
        raise HTTPException(503, "Database unavailable")
    cache_key = f"hotels_map:{district or 'all'}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        (hotels_list, _), districts_stats, hotel_stats = await asyncio.gather(
            data.get_hotels(limit=2000),
            data.get_districts_statistics(),
            data.get_latest_hotel_stats(),
        )
    except Exception:
        logger.exception("hotels-map: data fetch failed")
        raise HTTPException(503, "Не удалось получить данные")

    occ_by_district: dict[str, dict] = {
        d.get("district", ""): d for d in (districts_stats or [])
    }

    hotels: list[dict[str, Any]] = []
    total_rooms = 0
    free_rooms = 0
    for h in hotels_list:
        if not h.lat or not h.lon:
            continue
        if district and h.district != district:
            continue
        d_occ = (occ_by_district.get(h.district) or {}).get("avg_occupancy", 0) or 0
        hs = hotel_stats.get(h.id, {})

        hotels.append({
            "id": h.id, "name": h.name, "city": h.city or "",
            "district": h.district or "", "lat": float(h.lat), "lon": float(h.lon),
            "rating": float(h.rating) if h.rating is not None else None,
            "min_price": float(h.min_price) if h.min_price is not None else None,
            "rooms_num": hs.get("rooms_num", 0) or 0,
            "free_rooms": hs.get("free_rooms", 0) or 0,
            "occupancy": round(float(d_occ), 1),
            "max_capacity": hs.get("max_capacity", 0) or 0,
        })

    for d in (districts_stats or []):
        if district and d.get("district") != district:
            continue
        if d.get("district") in TOURIST_DISTRICTS:
            total_rooms += d.get("total_rooms", 0) or 0
            free_rooms += d.get("free_rooms", 0) or 0

    response: dict[str, Any] = {
        "hotels": hotels, "total_hotels": len(hotels),
        "total_rooms": total_rooms, "free_rooms": free_rooms,
        "avg_occupancy": round(100 - free_rooms / total_rooms * 100, 1) if total_rooms else 0,
    }
    await cache.set(cache_key, response, ttl=300)
    return response


@router.get("/poi")
async def get_points_of_interest(
    category: Literal["tourism", "nature", "culture", "transport", "bus_station", "train", "all"] = "tourism",
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    """Достопримечательности и POI из OpenStreetMap.

    Categories: tourism, nature, culture, transport, bus_station, train
    """
    from app.services.poi_service import poi_service, POI_CATEGORIES

    if category == "all":
        data = await poi_service.get_all_categories(limit_per_category=limit)
        return {"categories": {k: {"label": POI_CATEGORIES[k]["label"], "items": v} for k, v in data.items()}}

    live_pois = await poi_service.get_pois(category=category, limit=limit)
    if live_pois:
        pois = live_pois
        data_source = "overpass"
    else:
        pois = await poi_service.get_pois_with_fallback(category=category, limit=limit)
        data_source = "fallback"
    cat_info = POI_CATEGORIES.get(category, {})
    return {
        "category": category,
        "label": cat_info.get("label", category),
        "items": pois,
        "total": len(pois),
        "data_source": data_source,
    }


@router.get("/price-recommendation")
async def get_price_recommendation(
    data: DataServiceDep,
    ensemble_svc: EnsembleServiceDep,
    weather_svc: WeatherServiceDep,
    cache: CacheServiceDep,
    district: str = DEFAULT_DISTRICT,
) -> dict[str, Any]:
    """Рекомендация оптимальной цены на основе прогноза загрузки и сезонности.

    Логика: при высокой прогнозной загрузке (>60%) — повышение цены,
    при низкой (<35%) — скидки для привлечения гостей.
    """
    if district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    cache_key = f"price_rec:{district}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    districts_stats = await data.get_districts_statistics()
    current_price = 0
    current_occ = 0
    for d in districts_stats:
        if d.get("district") == district:
            current_price = d.get("avg_price", 0) or 0
            current_occ = d.get("avg_occupancy", 0) or 0
            break

    if not current_price:
        return {"district": district, "recommendation": "Недостаточно данных о ценах", "adjustments": []}

    forecast_occ = current_occ
    try:
        result = await _get_shared_forecast(data, weather_svc, ensemble_svc, district, 7)
        points = result.get("ensemble", [])
        if points:
            forecast_occ = round(sum(p.occupancy for p in points) / len(points), 1)
    except Exception:
        pass

    adjustments = []
    if forecast_occ > 75:
        pct = min(30, round((forecast_occ - 60) * 0.8))
        adjustments.append({
            "period": "Ближайшая неделя",
            "direction": "up",
            "percent": pct,
            "recommended_price": round(current_price * (1 + pct / 100)),
            "reason": f"Прогноз загрузки {forecast_occ}% — высокий спрос",
        })
    elif forecast_occ > 55:
        pct = min(15, round((forecast_occ - 50) * 0.5))
        adjustments.append({
            "period": "Ближайшая неделя",
            "direction": "up",
            "percent": pct,
            "recommended_price": round(current_price * (1 + pct / 100)),
            "reason": f"Прогноз загрузки {forecast_occ}% — умеренный спрос",
        })
    elif forecast_occ < 35:
        pct = min(25, round((40 - forecast_occ) * 0.8))
        adjustments.append({
            "period": "Ближайшая неделя",
            "direction": "down",
            "percent": pct,
            "recommended_price": round(current_price * (1 - pct / 100)),
            "reason": f"Прогноз загрузки {forecast_occ}% — низкий спрос, скидки привлекут гостей",
        })
    else:
        adjustments.append({
            "period": "Ближайшая неделя",
            "direction": "stable",
            "percent": 0,
            "recommended_price": current_price,
            "reason": f"Прогноз загрузки {forecast_occ}% — цена оптимальна",
        })

    response = {
        "district": district,
        "current_avg_price": current_price,
        "current_occupancy": current_occ,
        "forecast_occupancy": forecast_occ,
        "adjustments": adjustments,
        "methodology": "Ценовая рекомендация основана на прогнозе загрузки Ensemble (Prophet+NeuralProphet+XGBoost). При загрузке >75% — повышение до +30%, при <35% — скидка до -25%.",
    }
    await cache.set(cache_key, response, ttl=1800)
    return response


@router.get("/rosstat")
async def get_rosstat_context(data: DataServiceDep) -> dict[str, Any]:
    """Контекст данных Росстата по туризму Иркутской области.

    Официальная статистика КСР (коллективных средств размещения) за 2024 год
    + сравнение с данными системы.
    """
    rosstat_2024 = {
        "year": 2024,
        "source": "Росстат, форма 1-КСР, Иркутскстат",
        "total_ksr": 549,
        "hotels_hostels_motels": 370,
        "sanatoriums_camps_bases": 179,
        "top_districts": {
            "Иркутск": 173,
            "Ольхонский": 82,
            "Иркутский": 51,
            "Слюдянский": 43,
        },
        "avg_rooms_per_ksr": 27,
        "avg_beds_per_ksr": 72,
        "avg_annual_revenue_mln": 19.5,
        "revenue_growth_yoy": 11.0,
        "employees": 5843,
        "year_round_share": 80.0,
    }

    system_stats = {"total_hotels": 0, "total_cities": 0, "avg_occupancy": 0}
    try:
        metrics = await data.get_total_metrics()
        system_stats = {
            "total_hotels": metrics.get("total_hotels", 0),
            "total_cities": metrics.get("total_cities", 0),
            "avg_occupancy": round(metrics.get("avg_occupancy", 0) or 0, 1),
        }
    except Exception:
        pass

    coverage = round(system_stats["total_hotels"] / rosstat_2024["total_ksr"] * 100, 1) if rosstat_2024["total_ksr"] else 0

    return {
        "rosstat": rosstat_2024,
        "system": system_stats,
        "comparison": {
            "coverage_percent": coverage,
            "description": f"Система мониторит {system_stats['total_hotels']} из {rosstat_2024['total_ksr']} КСР региона ({coverage}% покрытие)",
        },
        "note": "Данные Росстата — годовая отчётность (форма 1-КСР). Данные системы — оперативный мониторинг через 101Hotels API.",
    }


_WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
_MONTHS_RU = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн",
              "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]


@router.get("/weekday-heatmap")
async def get_weekday_heatmap(
    data: DataServiceDep,
    cache: CacheServiceDep,
    district: str | None = Query(default=None, description="Район; без параметра — весь регион"),
) -> dict[str, Any]:
    """Тепловая карта загрузки: день недели × месяц.

    Заменяет «горизонтальные столбцы по районам» (замечание комиссии 7.04.2026):
    показывает сезонные и недельные паттерны спроса, ключевая RMS-визуализация.
    """
    if district and district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    cache_key = f"analytics:weekday_heatmap:{district or 'all'}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        cells = await data.get_weekday_heatmap(district=district)
    except Exception:
        logger.exception("weekday-heatmap: query failed")
        raise HTTPException(503, "Не удалось получить данные")

    response: dict[str, Any] = {
        "district": district,
        "data": cells,
        "weekdays": _WEEKDAYS_RU,
        "months": _MONTHS_RU,
        "methodology": (
            "Среднее значение Occupancy = (100 - available_rooms_percent), "
            "сгруппировано по (ISO день недели 1..7, месяц 1..12). Источник — hotel_statistics."
        ),
    }
    await cache.set(cache_key, response, ttl=600)
    return response


@router.get("/booking-pace", response_model=BookingPaceResponse)
async def booking_pace(
    data: DataServiceDep,
    cache: CacheServiceDep,
    district: str = DEFAULT_DISTRICT,
    days_ahead: int = Query(14, ge=1, le=90),
    lookback_days: int = Query(7, ge=1, le=30),
) -> BookingPaceResponse:
    """Proxy-pickup для будущих дат: разница загрузки между двумя временны́ми срезами.

    Методология: pickup_pct = occupancy(future_date, today) - occupancy(future_date, today - lookback_days).
    При положительной дельте загрузка «набирается» — сигнал для пересмотра тарифов.

    Ограничение текущей реализации: hotel_statistics не хранит timestamp snapshot'а,
    поэтому два среза для одной future_date недостижимы.  Endpoint возвращает
    pickup_pct=0.0 там, где данные есть, и None там, где данных нет.
    Поле methodology содержит явное описание ограничения.
    """
    cache_key = f"analytics:booking-pace:{district}:{days_ahead}:{lookback_days}"
    cached = await cache.get(cache_key)
    if cached:
        return BookingPaceResponse(**cached)

    points_raw = await data.compute_proxy_pickup(
        district=district,
        days_ahead=days_ahead,
        lookback_days=lookback_days,
    )
    pickups = [p["pickup_pct"] for p in points_raw if p.get("pickup_pct") is not None]

    if not pickups:
        trend = "стабильно"
    elif len(pickups) >= 3:
        recent_sum = sum(pickups[-3:])
        if recent_sum > 0.5:
            trend = "ускорение"
        elif recent_sum < -0.5:
            trend = "замедление"
        else:
            trend = "стабильно"
    else:
        trend = "стабильно"

    summary = BookingPaceSummary(
        avg_pickup_pct=round(sum(pickups) / len(pickups), 2) if pickups else None,
        max_pickup_pct=max(pickups) if pickups else None,
        min_pickup_pct=min(pickups) if pickups else None,
        trend=trend,
    )
    response = BookingPaceResponse(
        district=district,
        days_ahead=days_ahead,
        lookback_days=lookback_days,
        method="daily_proxy_pickup",
        methodology=(
            "pickup_pct = occupancy(future_date, today) - occupancy(future_date, today - lookback_days). "
            "Ограничение: hotel_statistics не хранит timestamp snapshot'а, поэтому два временны́х среза "
            "для одной future_date недостижимы в текущей схеме БД. "
            "pickup_pct=0.0 означает наличие данных при отсутствии временно́й дельты; "
            "pickup_pct=null — данных за эту дату нет совсем."
        ),
        points=[BookingPacePoint(**p) for p in points_raw],
        summary=summary,
    )
    await cache.set(cache_key, response.model_dump(), ttl=180)
    return response


@router.get("/pickup-pace")
async def get_pickup_pace(
    data: DataServiceDep,
    cache: CacheServiceDep,
    district: str | None = Query(default=None, description="Район; без параметра — весь регион"),
    days: int = Query(default=30, ge=1, le=180, description="Количество дней истории"),
) -> dict[str, Any]:
    """Динамика бронирований за период: ежедневный pickup и накопленный pace.

    Pickup_d = booked_d - booked_(d-1), где booked = total_rooms - free_rooms_amount.
    Pace показывает скорость набора бронирований; для отельера это сигнал
    для пересмотра тарифов (RMS-метрика).
    """
    if district and district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    cache_key = f"analytics:pickup_pace:{district or 'all'}:{days}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        rows = await data.get_pickup_pace(district=district, days=days)
    except Exception:
        logger.exception("pickup-pace: query failed")
        raise HTTPException(503, "Не удалось получить данные")

    points: list[dict[str, Any]] = []
    prev_booked: int | None = None
    for r in rows:
        total = int(r.get("total_rooms") or 0)
        free = int(r.get("free_rooms") or 0)
        booked = max(0, total - free)
        occupancy = round(booked / total * 100, 1) if total > 0 else 0.0
        pickup = (booked - prev_booked) if prev_booked is not None else 0
        points.append({
            "date": r["date"],
            "booked": booked,
            "total_rooms": total,
            "free_rooms": free,
            "hotels_count": int(r.get("hotels_count") or 0),
            "occupancy": occupancy,
            "pickup": pickup,
        })
        prev_booked = booked

    pickups = [p["pickup"] for p in points if p["pickup"] != 0]
    avg_pickup = round(sum(pickups) / len(pickups), 1) if pickups else 0.0
    max_pickup = max(pickups) if pickups else 0
    min_pickup = min(pickups) if pickups else 0

    if len(pickups) >= 7:
        recent = sum(pickups[-3:]) / 3
        earlier = sum(pickups[:3]) / 3
        if recent > earlier * 1.2:
            trend = "ускорение"
        elif recent < earlier * 0.8:
            trend = "замедление"
        else:
            trend = "стабильно"
    else:
        trend = "недостаточно данных"

    today = date.today()
    period_start = today - timedelta(days=days)

    response = {
        "district": district,
        "period": {
            "start": str(period_start),
            "end": str(today),
            "days": days,
        },
        "points": points,
        "summary": {
            "avg_pickup": avg_pickup,
            "max_pickup": max_pickup,
            "min_pickup": min_pickup,
            "trend": trend,
            "samples": len(points),
        },
        "methodology": (
            "Pickup_d = booked_d - booked_(d-1), где booked = SUM(rooms_num) - SUM(free_rooms_amount). "
            "Положительный pickup — рост бронирований за день. Pace (накопленный booked) показывает скорость набора."
        ),
    }
    await cache.set(cache_key, response, ttl=300)
    return response


@router.get("/revenue-summary")
async def get_revenue_summary(
    data: DataServiceDep,
    cache: CacheServiceDep,
) -> dict[str, Any]:
    """Сводка RMS-метрик: ADR, Occupancy, RevPAR агрегированно и по районам.

    RevPAR = ADR × (Occupancy / 100). ADR оценивается как средняя min_price
    отелей района (proxy, т. к. полная revenue-модель требует tax-данных от
    отельеров через интеграцию с PMS).
    """
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    cache_key = "analytics:revenue_summary"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    districts_stats = await data.get_districts_statistics()
    if not districts_stats:
        return {"occupancy": 0, "adr": 0, "revpar": 0, "by_district": []}

    by_district: list[dict[str, Any]] = []
    occupancies: list[float] = []
    adrs: list[float] = []
    revpars: list[float] = []
    for d in districts_stats:
        d_name = d.get("district") or ""
        if d_name not in TOURIST_DISTRICTS:
            continue
        occ = float(d.get("avg_occupancy") or 0)
        adr = float(d.get("avg_price") or 0)
        revpar = round(adr * occ / 100, 0) if adr and occ else 0
        count = int(d.get("hotels_count") or 0)

        by_district.append({
            "district": d_name,
            "occupancy": round(occ, 1),
            "adr": round(adr),
            "revpar": revpar,
            "hotels_count": count,
            "confidence": "high" if count >= 10 else "medium" if count >= 3 else "low",
        })
        occupancies.append(occ)
        adrs.append(adr)
        revpars.append(revpar)

    by_district.sort(key=lambda x: x["revpar"], reverse=True)

    response = {
        "occupancy": round(sum(occupancies) / len(occupancies), 1) if occupancies else 0,
        "adr": round(sum(adrs) / len(adrs)) if adrs else 0,
        "revpar": round(sum(revpars) / len(revpars)) if revpars else 0,
        "by_district": by_district,
        "methodology": (
            "Загрузка = средняя по району доля занятых номеров (100 − %% свободных). "
            "ADR — средний минимальный тариф номера по данным 101Hotels (прокси). "
            "RevPAR = ADR × Загрузка / 100."
        ),
    }
    await cache.set(cache_key, response, ttl=300)
    return response


_EXPORT_TYPES = ("occupancy", "events", "hotels")


@router.get("/export")
async def export_data(
    data: DataServiceDep,
    type: Literal["occupancy", "events", "hotels"] = Query(..., description="Тип данных для экспорта"),
    district: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=10000, ge=1, le=50000),
) -> StreamingResponse:
    """CSV-экспорт данных для исследовательских задач.

    Поддерживаемые type: occupancy (загрузка отелей по дням),
    events (события региона), hotels (реестр объектов размещения).
    """
    if district and district not in TOURIST_DISTRICTS:
        raise HTTPException(400, f"Неизвестный район: {district}")
    if not data.is_connected:
        raise HTTPException(503, "БД не подключена")

    if type == "occupancy":
        rows = await data.export_occupancy_rows(
            district=district, date_from=date_from, date_to=date_to, limit=limit,
        )
        fieldnames = [
            "date", "hotel_id", "hotel_name", "district", "city",
            "rooms_num", "free_rooms_amount", "available_rooms_percent", "min_price",
        ]
        filename = f"occupancy_{district or 'all'}_{date.today()}.csv"
    elif type == "events":
        events = await data.get_events(date_from=date_from, date_to=date_to, limit=limit)
        rows = [
            {
                "event_id": e.get("event_id", ""),
                "title": e.get("title", ""),
                "date_start": str(e.get("date_start") or ""),
                "date_end": str(e.get("date_end") or "") if e.get("date_end") else "",
                "event_type": e.get("event_type") or "",
                "location": e.get("location") or "",
                "source_id": e.get("source_id") or "",
                "url": e.get("url") or "",
            }
            for e in events
        ]
        fieldnames = [
            "event_id", "title", "date_start", "date_end",
            "event_type", "location", "source_id", "url",
        ]
        filename = f"events_{date.today()}.csv"
    else:  # hotels
        hotels_list, _ = await data.get_hotels(district=district, limit=limit)
        rows = [
            {
                "id": h.id,
                "name": h.name,
                "city": h.city or "",
                "district": h.district or "",
                "lat": h.lat or "",
                "lon": h.lon or "",
                "rating": h.rating or "",
                "min_price": h.min_price or "",
                "accommodation_type": h.accommodation_type or "",
            }
            for h in hotels_list
        ]
        fieldnames = [
            "id", "name", "city", "district", "lat", "lon",
            "rating", "min_price", "accommodation_type",
        ]
        filename = f"hotels_{district or 'all'}_{date.today()}.csv"

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM для корректного открытия в Excel
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Total-Rows": str(len(rows)),
        },
    )
