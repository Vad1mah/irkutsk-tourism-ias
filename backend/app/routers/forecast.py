"""API для прогнозирования загрузки."""
import asyncio
import hashlib
import time
from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Any
import random
import logging

from app.models.schemas import (
    ForecastRequest, ForecastResponse, ForecastPoint,
    EnsembleResponse, CompareModelsResponse, CompareAllResponse,
)
from app.constants import DEFAULT_DISTRICT
from app.dependencies import (
    DataServiceDep,
    ProphetServiceDep,
    NeuralProphetServiceDep,
    XGBoostServiceDep,
    EnsembleServiceDep,
    WeatherServiceDep,
    HolidaysServiceDep,
    CacheServiceDep,
)
from app.executor import run_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/forecast", tags=["forecast"])

FORECAST_CACHE_TTL = 1800  # 30 минут

_compare_locks: dict[str, asyncio.Lock] = {}
_compare_results: dict[str, tuple[float, Any]] = {}
_COMPARE_TTL = 1800
_MAX_CACHE = 50


def _evict_compare_cache() -> None:
    now = time.time()
    expired = [k for k, (ts, _) in _compare_results.items() if now - ts > _COMPARE_TTL]
    for k in expired:
        _compare_results.pop(k, None)
        _compare_locks.pop(k, None)
    if len(_compare_results) >= _MAX_CACHE:
        oldest = min(_compare_results, key=lambda k: _compare_results[k][0])
        _compare_results.pop(oldest, None)
        _compare_locks.pop(oldest, None)


def _generate_demo_history(district: str, days: int = 90, holidays_svc=None) -> list[dict]:
    """Генерация демо-данных истории загруженности."""
    random.seed(int(hashlib.md5(district.encode()).hexdigest(), 16) % 10000)
    history = []
    base_date = date.today() - timedelta(days=days)

    for i in range(days):
        d = base_date + timedelta(days=i)
        # Базовая загруженность с сезонностью
        base = 45 + 15 * (1 + 0.5 * (d.month in [6, 7, 8, 12, 1]))
        # Выходные выше
        weekend_boost = 15 if d.weekday() >= 5 else 0
        # Праздники
        is_holiday = holidays_svc.is_holiday(d) if holidays_svc else False
        holiday_boost = 20 if is_holiday else 0
        # Случайный шум
        noise = random.uniform(-10, 10)
        occupancy = max(20, min(95, base + weekend_boost + holiday_boost + noise))

        history.append({"date": d, "occupancy": occupancy})

    return history


def _generate_demo_forecast(district: str, days_ahead: int, holidays_svc=None) -> list[ForecastPoint]:
    """Генерация демо-прогноза без Prophet."""
    random.seed(hash(district) % 1000 + days_ahead)
    forecast = []

    for i in range(days_ahead):
        d = date.today() + timedelta(days=i + 1)
        base = 50 + 10 * (1 + 0.3 * (d.month in [6, 7, 8, 12, 1]))
        weekend_boost = 12 if d.weekday() >= 5 else 0
        is_holiday = holidays_svc.is_holiday(d) if holidays_svc else False
        holiday_boost = 15 if is_holiday else 0
        noise = random.uniform(-5, 5)
        occupancy = max(25, min(90, base + weekend_boost + holiday_boost + noise))

        forecast.append(ForecastPoint(
            date=d,
            occupancy=round(occupancy, 1),
            lower_bound=round(max(10, occupancy - 15), 1),
            upper_bound=round(min(100, occupancy + 15), 1),
        ))

    return forecast


async def _get_history(hotel_id: str | None, district: str | None, data_svc=None) -> list[dict]:
    """Получить историю загрузки из БД."""
    history = []
    try:
        if hotel_id:
            stats = await data_svc.get_hotel_statistics(hotel_id=hotel_id)
            history = [
                {"date": s.date, "occupancy": 100 - (s.available_rooms_percent or 0)}
                for s in stats
            ]
        elif district:
            history_data = await data_svc.get_occupancy_by_district(district)
            history = [
                {"date": row["date"], "occupancy": row["avg_occupancy"]}
                for row in history_data
            ]
    except Exception as e:
        logger.error(f"DB error getting history: {e}")
    return history


async def _get_weather_and_events(
    history: list[dict],
    days_ahead: int,
    weather_svc,
    data_svc,
) -> tuple[dict, list]:
    """Получить погоду и события для прогноза."""
    weather_data: dict = {}
    events_data: list = []

    if not history:
        return weather_data, events_data

    try:
        all_dates = [h["date"] for h in history]
        last_date = max(all_dates) if all_dates else date.today()
        for i in range(days_ahead):
            all_dates.append(last_date + timedelta(days=i + 1))
        weather_data = await weather_svc.get_weather_for_dates(all_dates)
    except Exception as e:
        logger.warning(f"Weather error: {e}")

    try:
        events_raw = await data_svc.get_events()
        events_data = [
            {"date_start": e.get("date_start"), "title": e.get("title"), "event_type": e.get("event_type")}
            for e in events_raw
            if e.get("date_start")
        ]
    except Exception as e:
        logger.warning(f"Events error: {e}")

    return weather_data, events_data


async def _run_forecast(
    request: ForecastRequest,
    forecast_fn,
    fallback_fn,
    min_history: int,
    data_svc,
    weather_svc,
    holidays_svc,
    model_name: str = "model",
    demo_days: int = 90,
    **extra_kwargs,
) -> ForecastResponse:
    """Общий пайплайн для endpoint'ов прогнозирования.

    Args:
        forecast_fn: async функция модели (forecast_occupancy_async)
        fallback_fn: async функция fallback-модели при ошибке
        min_history: минимум точек истории для реального прогноза
        model_name: имя модели для логов
        demo_days: дней демо-истории при недостатке данных
        extra_kwargs: доп. параметры для forecast_fn (n_lags, model и т.д.)
    """
    if not request.hotel_id and not request.district:
        raise HTTPException(400, "Укажите hotel_id или district")

    history = await _get_history(request.hotel_id, request.district, data_svc)
    history = [h for h in history if h.get("occupancy") is not None]
    history_points = len(history)
    data_source = "real"

    if len(history) >= min_history:
        weather_data, events_data = await _get_weather_and_events(
            history, request.days_ahead, weather_svc, data_svc
        )
        try:
            forecast = await forecast_fn(
                history=history,
                days_ahead=request.days_ahead,
                weather_data=weather_data,
                events_data=events_data,
                **extra_kwargs,
            )
        except Exception as e:
            logger.error(f"{model_name} error: {e}")
            if fallback_fn is None:
                raise
            forecast = await fallback_fn(
                history=history,
                days_ahead=request.days_ahead,
                weather_data=weather_data,
                events_data=events_data,
            )
    else:
        data_source = "demo"
        district_name = request.district or DEFAULT_DISTRICT
        demo_history = _generate_demo_history(district_name, days=demo_days, holidays_svc=holidays_svc)
        history_points = len(demo_history)
        try:
            forecast = await forecast_fn(
                history=demo_history,
                days_ahead=request.days_ahead,
                **extra_kwargs,
            )
        except Exception as e:
            logger.error(f"{model_name} demo error: {e}")
            forecast = _generate_demo_forecast(district_name, request.days_ahead, holidays_svc)

    return ForecastResponse(
        hotel_id=request.hotel_id,
        district=request.district,
        forecast=forecast,
        history_points=history_points,
        data_source=data_source,
    )


@router.post("", response_model=ForecastResponse)
async def get_forecast(
    request: ForecastRequest,
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    weather_svc: WeatherServiceDep,
    holidays_svc: HolidaysServiceDep,
):
    """Прогноз загруженности (Prophet + weather/events regressors)."""
    return await _run_forecast(
        request=request,
        forecast_fn=prophet_svc.forecast_occupancy_async,
        fallback_fn=None,
        min_history=7,
        data_svc=data_svc,
        weather_svc=weather_svc,
        holidays_svc=holidays_svc,
        model_name="Prophet",
    )


@router.get("/holidays")
async def get_holidays(
    holidays_svc: HolidaysServiceDep,
    date_from: date | None = None,
    date_to: date | None = None,
):
    """Получить праздники в диапазоне дат."""
    if not date_from:
        date_from = date.today()
    if not date_to:
        date_to = date_from + timedelta(days=365)

    holidays_list = holidays_svc.get_holidays_in_range(date_from, date_to)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "holidays": [
            {"date": str(h["date"]), "name": h["name"]}
            for h in holidays_list
        ],
    }


@router.get("/weather")
async def get_weather(
    weather_svc: WeatherServiceDep,
    days: int = 14,
):
    """Получить прогноз погоды."""
    if days < 1 or days > 16:
        raise HTTPException(400, "days должен быть от 1 до 16")
    forecast = await weather_svc.get_forecast_weather(days)
    return {
        "location": DEFAULT_DISTRICT,
        "forecasts": forecast,
    }


@router.post("/neural", response_model=ForecastResponse)
async def get_neural_forecast(
    request: ForecastRequest,
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    neuralprophet_svc: NeuralProphetServiceDep,
    weather_svc: WeatherServiceDep,
    holidays_svc: HolidaysServiceDep,
):
    """Прогноз загруженности (NeuralProphet + авторегрессия + events)."""
    return await _run_forecast(
        request=request,
        forecast_fn=neuralprophet_svc.forecast_occupancy_async,
        fallback_fn=prophet_svc.forecast_occupancy_async,
        min_history=14,
        data_svc=data_svc,
        weather_svc=weather_svc,
        holidays_svc=holidays_svc,
        model_name="NeuralProphet",
        n_lags=14,
    )


@router.get("/compare", response_model=CompareModelsResponse)
async def compare_models(
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    neuralprophet_svc: NeuralProphetServiceDep,
    weather_svc: WeatherServiceDep,
    district: str = DEFAULT_DISTRICT,
    days_ahead: int = 14,
):
    """Сравнить прогнозы Prophet и NeuralProphet."""
    history = await _get_history(None, district, data_svc)

    if len(history) < 14:
        raise HTTPException(status_code=400, detail="Недостаточно данных для сравнения")

    weather_data, events_data = await _get_weather_and_events(
        history, days_ahead, weather_svc, data_svc
    )

    prophet_forecast: list[ForecastPoint] = []
    try:
        prophet_forecast = await prophet_svc.forecast_occupancy_async(
            history=history, days_ahead=days_ahead,
            weather_data=weather_data, events_data=events_data,
        )
    except Exception as e:
        logger.error(f"Prophet error: {e}")

    neural_forecast: list[ForecastPoint] = []
    try:
        neural_forecast = await neuralprophet_svc.forecast_occupancy_async(
            history=history, days_ahead=days_ahead,
            weather_data=weather_data, events_data=events_data,
            n_lags=14,
        )
    except Exception as e:
        logger.error(f"NeuralProphet error: {e}")

    return {
        "district": district,
        "history_points": len(history),
        "prophet": [{"date": f.date, "occupancy": f.occupancy} for f in prophet_forecast],
        "neuralprophet": [{"date": f.date, "occupancy": f.occupancy} for f in neural_forecast],
    }


@router.post("/xgboost", response_model=ForecastResponse)
async def get_xgboost_forecast(
    request: ForecastRequest,
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    xgboost_svc: XGBoostServiceDep,
    weather_svc: WeatherServiceDep,
    holidays_svc: HolidaysServiceDep,
):
    """Прогноз загруженности (XGBoost/LightGBM + 25 фичей)."""
    return await _run_forecast(
        request=request,
        forecast_fn=xgboost_svc.forecast_occupancy_async,
        fallback_fn=prophet_svc.forecast_occupancy_async,
        min_history=30,
        data_svc=data_svc,
        weather_svc=weather_svc,
        holidays_svc=holidays_svc,
        model_name="XGBoost",
        demo_days=60,
        model="ensemble",
    )


@router.get("/ensemble", response_model=EnsembleResponse)
async def get_ensemble_forecast(
    data_svc: DataServiceDep,
    cache_svc: CacheServiceDep,
    weather_svc: WeatherServiceDep,
    ensemble_svc: EnsembleServiceDep,
    district: str = DEFAULT_DISTRICT,
    days_ahead: int = Query(14, ge=1, le=365),
    method: str = "weighted_average",
):
    """
    Ensemble прогноз: Prophet + NeuralProphet + XGBoost.

    Методы объединения:
    - simple_average: Простое среднее
    - weighted_average: Взвешенное по качеству
    - best_model: Лучшая модель
    """
    cache_key = cache_svc.cache_key("forecast:ensemble", district, days_ahead, method)
    cached = await cache_svc.get(cache_key)
    if cached:
        logger.info(f"Ensemble forecast cache hit: {district}")
        return cached

    history = []
    weather_data = {}
    events_data = []
    price_data = []

    try:
        history_data = await data_svc.get_occupancy_by_district(district)
        history = [
            {"date": row["date"], "occupancy": row["avg_occupancy"]}
            for row in history_data
        ]
        # Извлекаем цены из тех же данных
        price_data = [
            {"date": row["date"], "price": row.get("avg_price")}
            for row in history_data
            if row.get("avg_price")
        ]
    except Exception as e:
        logger.error(f"DB error: {e}")

    if len(history) < 30:
        raise HTTPException(status_code=400, detail="Недостаточно данных для ensemble (нужно минимум 30 точек)")

    try:
        all_dates = [h["date"] for h in history]
        last_date = max(all_dates)
        for i in range(days_ahead):
            all_dates.append(last_date + timedelta(days=i + 1))
        weather_data = await weather_svc.get_weather_for_dates(all_dates)
    except Exception as e:
        logger.warning(f"Weather error: {e}")

    try:
        events_raw = await data_svc.get_events()
        events_data = [
            {"date_start": e.get("date_start"), "title": e.get("title"), "event_type": e.get("event_type")}
            for e in events_raw if e.get("date_start")
        ]
    except Exception as e:
        logger.warning(f"Events error: {e}")

    try:
        result = await ensemble_svc.forecast_ensemble_async(
            history=history,
            days_ahead=days_ahead,
            weather_data=weather_data,
            events_data=events_data,
            method=method,
            district=district,
        )
    except Exception as e:
        logger.error(f"Ensemble forecast error: {e}", exc_info=True)
        raise HTTPException(500, "Ошибка прогнозирования")

    response = {
        "district": district,
        "history_points": len(history),
        "method": method,
        "weights": result.get("weights", {}),
        "ensemble": [
            {"date": str(f.date), "occupancy": f.occupancy, "lower": f.lower_bound, "upper": f.upper_bound}
            for f in result.get("ensemble", [])[:days_ahead]
        ],
        "models": {
            model: [
                {
                    "date": str(f.date),
                    "occupancy": f.occupancy,
                    "lower": getattr(f, "lower_bound", f.occupancy * 0.85),
                    "upper": getattr(f, "upper_bound", f.occupancy * 1.15),
                }
                for f in forecasts
            ]
            for model, forecasts in result.get("models", {}).items()
        },
    }

    await cache_svc.set(cache_key, response, ttl=FORECAST_CACHE_TTL)
    return response


@router.get("/compare-all", response_model=CompareAllResponse)
async def compare_all_models(
    data_svc: DataServiceDep,
    cache_svc: CacheServiceDep,
    weather_svc: WeatherServiceDep,
    ensemble_svc: EnsembleServiceDep,
    xgboost_svc: XGBoostServiceDep,
    district: str = DEFAULT_DISTRICT,
    test_days: int = Query(default=14, ge=3, le=90),
):
    """
    Сравнить все модели на тестовых данных.

    Возвращает метрики качества (RMSE, MAE) для:
    - Prophet
    - NeuralProphet
    - XGBoost
    - Ensemble
    """
    cache_key = cache_svc.cache_key("forecast:compare", district, test_days)
    cached = await cache_svc.get(cache_key)
    if cached:
        logger.info(f"Compare models cache hit: {district}")
        return cached

    lock_key = f"{district}:{test_days}"
    now = time.time()
    if lock_key in _compare_results:
        ts, result = _compare_results[lock_key]
        if now - ts < _COMPARE_TTL:
            return result

    if lock_key not in _compare_locks:
        _compare_locks[lock_key] = asyncio.Lock()

    async with _compare_locks[lock_key]:
        if lock_key in _compare_results:
            ts, result = _compare_results[lock_key]
            if now - ts < _COMPARE_TTL:
                return result

        history = []
        weather_data = {}
        events_data = []

        try:
            history_data = await data_svc.get_occupancy_by_district(district)
            history = [
                {"date": row["date"], "occupancy": row["avg_occupancy"]}
                for row in history_data
            ]
        except Exception as e:
            logger.error(f"DB error: {e}")

        if len(history) < test_days + 30:
            raise HTTPException(status_code=400, detail=f"Недостаточно данных (нужно минимум {test_days + 30} точек)")

        try:
            all_dates = [h["date"] for h in history]
            weather_data = await weather_svc.get_weather_for_dates(all_dates)
        except Exception as e:
            logger.warning(f"Не удалось загрузить погоду для сравнения: {e}")

        try:
            events_raw = await data_svc.get_events()
            events_data = [
                {"date_start": e.get("date_start"), "title": e.get("title"), "event_type": e.get("event_type")}
                for e in events_raw if e.get("date_start")
            ]
        except Exception as e:
            logger.warning(f"Не удалось загрузить события для сравнения: {e}")

        metrics = await run_sync(
            ensemble_svc.compare_models,
            history=history,
            weather_data=weather_data,
            events_data=events_data,
            test_days=test_days,
        )

        feature_importance = {}
        try:
            feature_importance = xgboost_svc.get_feature_importance()
        except Exception as e:
            logger.warning(f"Не удалось получить feature importance: {e}")

        response = {
            "district": district,
            "history_points": len(history),
            "test_days": test_days,
            "metrics": metrics,
            "feature_importance": feature_importance,
        }

        _evict_compare_cache()
        _compare_results[lock_key] = (time.time(), response)
        await cache_svc.set(cache_key, response, ttl=FORECAST_CACHE_TTL)
        return response


@router.get("/explain")
async def get_explained_forecast(
    district: str = DEFAULT_DISTRICT,
    days_ahead: int = Query(14, ge=1, le=365),
    target_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    """
    Объяснимый прогноз с LangGraph Agent.

    Возвращает:
    - Прогнозы всех моделей
    - Факторы влияния
    - Объяснение на естественном языке
    - Рекомендации

    Args:
        district: Район для прогноза
        days_ahead: Количество дней прогноза
        target_date: Конкретная дата для объяснения (YYYY-MM-DD)
    """
    # Импортируем forecast_agent локально т.к. он сложный
    from app.services.forecast_agent import forecast_agent

    try:
        result = await forecast_agent.run(
            district=district,
            days_ahead=days_ahead,
            target_date=target_date,
        )
        
        return {
            "district": district,
            "target_date": target_date or str(date.today() + timedelta(days=7)),
            "best_model": result.get("best_model", ""),
            "forecasts": result.get("forecasts", {}),
            "factors": result.get("factors", []),
            "explanation": result.get("explanation", ""),
            "recommendation": result.get("recommendation", ""),
            "processing_time": round(result.get("processing_time", 0), 2),
            "error": result.get("error"),
        }
    except Exception as e:
        logger.error(f"Explain forecast error: {e}")
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать объяснение прогноза.")
