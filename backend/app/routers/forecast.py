"""API для прогнозирования загрузки."""
import asyncio
import time
from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Any
import logging

from app.models.schemas import (
    ForecastRequest, ForecastResponse, ForecastPoint,
    EnsembleResponse, CompareAllResponse,
    ForecastValidationResponse, ValidationPoint,
)
from app.constants import DEFAULT_DISTRICT
from app.dependencies import (
    DataServiceDep,
    ProphetServiceDep,
    XGBoostServiceDep,
    EnsembleServiceDep,
    WeatherServiceDep,
    CacheServiceDep,
)
from app.executor import run_sync
from app.services.cache_service import build_ensemble_cache_key

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
    min_history: int,
    data_svc,
    weather_svc,
    model_name: str = "model",
    **extra_kwargs,
) -> ForecastResponse:
    """Общий пайплайн для endpoint'ов прогнозирования.

    Args:
        forecast_fn: async функция модели (forecast_occupancy_async)
        min_history: минимум точек истории для реального прогноза
        model_name: имя модели для логов
        extra_kwargs: доп. параметры для forecast_fn (n_lags, model и т.д.)

    Raises:
        HTTPException 422: если в БД < min_history точек истории.
    """
    if not request.hotel_id and not request.district:
        raise HTTPException(400, "Укажите hotel_id или district")

    history = await _get_history(request.hotel_id, request.district, data_svc)
    history = [h for h in history if h.get("occupancy") is not None]
    history_points = len(history)

    if history_points < min_history:
        raise HTTPException(
            422,
            f"Недостаточно данных для {model_name}: {history_points} точек, "
            f"требуется минимум {min_history}",
        )

    weather_data, events_data = await _get_weather_and_events(
        history, request.days_ahead, weather_svc, data_svc
    )
    forecast = await forecast_fn(
        history=history,
        days_ahead=request.days_ahead,
        weather_data=weather_data,
        events_data=events_data,
        **extra_kwargs,
    )

    return ForecastResponse(
        hotel_id=request.hotel_id,
        district=request.district,
        forecast=forecast,
        history_points=history_points,
    )


@router.post("", response_model=ForecastResponse)
async def get_forecast(
    request: ForecastRequest,
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    weather_svc: WeatherServiceDep,
):
    """Прогноз загруженности (Prophet + weather/events regressors)."""
    return await _run_forecast(
        request=request,
        forecast_fn=prophet_svc.forecast_occupancy_async,
        min_history=7,
        data_svc=data_svc,
        weather_svc=weather_svc,
        model_name="Prophet",
    )


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
    cache_key = build_ensemble_cache_key(district=district, days=days_ahead, method=method)
    cached = await cache_svc.get(cache_key)
    if cached:
        logger.info(f"Ensemble forecast cache hit: {district}")
        return cached

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

    # Fire-and-forget: persist ensemble forecasts for later validation
    try:
        asyncio.create_task(
            data_svc.save_ensemble_forecasts(
                district=district,
                forecasts=[
                    {
                        "date": f.date if hasattr(f, "date") else f["date"],
                        "occupancy": f.occupancy if hasattr(f, "occupancy") else f["occupancy"],
                        "lower": getattr(f, "lower_bound", None),
                        "upper": getattr(f, "upper_bound", None),
                    }
                    for f in result.get("ensemble", [])
                ],
            )
        )
    except Exception as e:
        logger.warning("Could not schedule save_ensemble_forecasts: %s", e)

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


LLM_EXPLAIN_TIMEOUT_S = 5.0


def _extract_factors_from_ensemble(result: dict) -> list[dict]:
    """Достаёт топ-5 факторов из feature_importance ensemble."""
    fi = (result or {}).get("feature_importance", {})
    if isinstance(fi, dict):
        # Может быть {"xgboost": {...}} или плоским dict
        inner = fi.get("xgboost", fi)
        if isinstance(inner, dict):
            return [
                {"name": k, "importance": v}
                for k, v in sorted(inner.items(), key=lambda x: -x[1])[:5]
            ]
    return []


def _build_factor_explanation(district: str, days: int, factors: list[dict]) -> str:
    """Возвращает русский текст-объяснение прогноза на основе топ-факторов XGBoost."""
    if not factors:
        return (
            f"Прогноз на {days} дней по району «{district}» построен на ансамбле моделей. "
            f"Подробное объяснение временно недоступно (AI-сервис не отвечает)."
        )
    top = ", ".join(f["name"] for f in factors[:3])
    return (
        f"Прогноз на {days} дней по району «{district}» опирается на исторический ряд занятости "
        f"и набор признаков. Главные факторы по важности: {top}. "
        f"Развёрнутое AI-объяснение временно недоступно — показаны топ-5 факторов из XGBoost."
    )


async def _explain_with_fallback(
    district: str,
    days_ahead: int,
    target_date: str | None,
) -> dict:
    """Вызывает forecast_agent с таймаутом; при ошибке возвращает factor-only fallback."""
    from app.services.forecast_agent import forecast_agent

    factors: list[dict] = []
    source: str = "llm_error"
    try:
        result = await asyncio.wait_for(
            forecast_agent.run(
                district=district,
                days_ahead=days_ahead,
                target_date=target_date,
            ),
            timeout=LLM_EXPLAIN_TIMEOUT_S,
        )
        factors = _extract_factors_from_ensemble(result)
        if result and result.get("explanation"):
            return {
                "district": district,
                "target_date": target_date or str(date.today() + timedelta(days=7)),
                "best_model": result.get("best_model", ""),
                "forecasts": result.get("forecasts", {}),
                "factors": factors or result.get("factors", []),
                "explanation": result.get("explanation", ""),
                "recommendation": result.get("recommendation", ""),
                "processing_time": round(result.get("processing_time", 0), 2),
                "error": result.get("error"),
                "source": "llm",
            }
        # result returned but no explanation — fall through to factor-only fallback
        logger.info("forecast.explain: run() returned empty explanation, using factor-only fallback")
        source = "llm_empty"
    except asyncio.TimeoutError:
        logger.warning("forecast.explain timed out after %.1fs", LLM_EXPLAIN_TIMEOUT_S)
        factors = []
        source = "llm_timeout"
    except Exception as exc:
        logger.warning("forecast.explain LLM error: %s — using factor-only fallback", exc)
        factors = []
        source = "llm_error"

    fallback_text = _build_factor_explanation(district, days_ahead, factors)
    return {
        "district": district,
        "target_date": target_date or str(date.today() + timedelta(days=7)),
        "best_model": "",
        "forecasts": {},
        "factors": factors,
        "explanation": fallback_text,
        "recommendation": "",
        "processing_time": 0,
        "error": None,
        "source": source,
    }


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

    При недоступности AI-сервиса возвращает factor-only fallback (HTTP 200, source=fallback).

    Args:
        district: Район для прогноза
        days_ahead: Количество дней прогноза
        target_date: Конкретная дата для объяснения (YYYY-MM-DD)
    """
    return await _explain_with_fallback(district, days_ahead, target_date)


@router.get("/{district}/validation", response_model=ForecastValidationResponse)
async def forecast_validation(
    district: str,
    data: DataServiceDep,
    days_back: int = Query(14, ge=1, le=90),
) -> ForecastValidationResponse:
    """Forecast vs Actual для самовалидации модели.

    Сравнивает ранее сохранённые ensemble-прогнозы с фактическими данными
    за последние days_back дней. Если прогнозов нет — возвращает samples=0.

    Args:
        district: Название района (напр. «Иркутский»).
        days_back: Горизонт сравнения в днях (1–90).

    Returns:
        RMSE, MAE и попарные ряды forecasted/actual.
    """
    import math
    from datetime import date, timedelta

    today = date.today()
    target_dates = [today - timedelta(days=i) for i in range(days_back, 0, -1)]

    try:
        saved = await data.get_saved_forecasts(district=district, dates=target_dates)
    except Exception:
        logger.warning("forecast_validation: get_saved_forecasts failed", exc_info=True)
        saved = {}

    try:
        actual_rows = await data.get_occupancy_by_district(
            district, date_from=target_dates[0], date_to=target_dates[-1]
        )
    except Exception:
        logger.warning("forecast_validation: get_occupancy_by_district failed", exc_info=True)
        actual_rows = []

    actual_map: dict[date, float] = {
        r["date"]: r["avg_occupancy"]
        for r in actual_rows
        if r.get("avg_occupancy") is not None
    }

    pairs: list[tuple[float, float]] = []
    forecasted: list[ValidationPoint] = []
    actual: list[ValidationPoint] = []
    for d in target_dates:
        f = saved.get(d)
        a = actual_map.get(d)
        if f is None or a is None:
            continue
        pairs.append((f, a))
        forecasted.append(ValidationPoint(date=d.isoformat(), occupancy=f))
        actual.append(ValidationPoint(date=d.isoformat(), occupancy=a))

    if not pairs:
        return ForecastValidationResponse(
            district=district, days_back=days_back, samples=0,
            rmse=None, mae=None, mae_per_day=[], forecasted=[], actual=[],
        )

    rmse = math.sqrt(sum((f - a) ** 2 for f, a in pairs) / len(pairs))
    mae = sum(abs(f - a) for f, a in pairs) / len(pairs)
    return ForecastValidationResponse(
        district=district,
        days_back=days_back,
        samples=len(pairs),
        rmse=round(rmse, 2),
        mae=round(mae, 2),
        mae_per_day=[round(abs(f - a), 2) for f, a in pairs],
        forecasted=forecasted,
        actual=actual,
    )
