"""API для прогнозирования загрузки."""
import asyncio
import time
from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Any
import logging

from app.models.schemas import (
    ForecastRequest, ForecastResponse, EnsembleResponse, CompareAllResponse,
    ForecastValidationResponse, ValidationPoint,
    HotelValidationResponse, HotelValidationSummaryResponse, HotelValidationSummaryItem,
)
from app.constants import DEFAULT_DISTRICT, DISTRICT_CENTERS, MAX_FORECAST_HORIZON_DAYS
from app.services.weather_service import IRKUTSK_LAT, IRKUTSK_LON
from app.dependencies import (
    DataServiceDep,
    ProphetServiceDep,
    XGBoostServiceDep,
    EnsembleServiceDep,
    WeatherServiceDep,
    CacheServiceDep,
)
from app.executor import run_sync
from app.services.cache_service import build_ensemble_cache_key, compute_ensemble_data_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/forecast", tags=["forecast"])

FORECAST_CACHE_TTL = 1800  # 30 минут
# Ответ, в котором отработали не все модели ансамбля, живёт в кэше пять минут: столько же
# он будет расходиться с таблицей метрик после починки упавшей модели. Не ноль — иначе во
# время аварии каждый запрос заново обучает ML, а это уже клало хост.
FORECAST_DEGRADED_CACHE_TTL = 300

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


def _resolve_district_coords(district: str | None) -> tuple[float, float]:
    """Возвращает (lat, lon) центроида района. Fallback: координаты Иркутска."""
    if district and district in DISTRICT_CENTERS:
        return DISTRICT_CENTERS[district]
    return (IRKUTSK_LAT, IRKUTSK_LON)


async def _get_weather_and_events(
    history: list[dict],
    days_ahead: int,
    weather_svc,
    data_svc,
    district: str | None = None,
) -> tuple[dict, list]:
    """Получить погоду и события для прогноза.

    Args:
        district: район для геопривязки погоды (центроид через DISTRICT_CENTERS)
                  и фильтрации событий через CITY_TO_DISTRICT (Phase 3).
    """
    weather_data: dict = {}
    events_data: list = []

    if not history:
        return weather_data, events_data

    lat, lon = _resolve_district_coords(district)

    try:
        all_dates = [h["date"] for h in history]
        last_date = max(all_dates) if all_dates else date.today()
        for i in range(days_ahead):
            all_dates.append(last_date + timedelta(days=i + 1))
        weather_data = await weather_svc.get_weather_for_dates(all_dates, lat=lat, lon=lon)
        logger.info(
            "Weather for district=%r resolved to lat=%.4f lon=%.4f (%d dates)",
            district or "<default>", lat, lon, len(all_dates),
        )
    except Exception as e:
        logger.warning(f"Weather error: {e}")

    try:
        # Phase 3: фильтруем по району если он задан (CITY_TO_DISTRICT substring-match)
        if district and hasattr(data_svc, "get_events_by_district"):
            events_raw = await data_svc.get_events_by_district(district)
            district_matched = sum(1 for e in events_raw if e.get("geo_inferred") is True)
            without_geo = sum(1 for e in events_raw if e.get("geo_inferred") is False)
            logger.info(
                "Events for district=%r: %d total (%d district-matched, %d without geo passed-through)",
                district, len(events_raw), district_matched, without_geo,
            )
        else:
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
        history, request.days_ahead, weather_svc, data_svc, district=request.district
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
    days_ahead: int = Query(14, ge=1, le=MAX_FORECAST_HORIZON_DAYS),
    method: str = "weighted_average",
):
    """
    Ensemble прогноз: Prophet + XGBoost.

    Методы объединения:
    - simple_average: Простое среднее
    - weighted_average: Взвешенное по качеству
    - best_model: Лучшая модель
    """
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

    weather_data, events_data = await _get_weather_and_events(
        history, days_ahead, weather_svc, data_svc, district=district
    )

    expected_models = ensemble_svc.model_names
    cache_key = build_ensemble_cache_key(
        district=district,
        days=days_ahead,
        data_hash=compute_ensemble_data_hash(history, weather_data, events_data),
        models=expected_models,
        method=method,
    )
    cached = await cache_svc.get(cache_key)
    if cached:
        logger.info(f"Ensemble forecast cache hit: {district}")
        return cached

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

    models_ran = sorted(name for name, points in result.get("models", {}).items() if points)
    if models_ran == expected_models:
        ttl = FORECAST_CACHE_TTL
    else:
        ttl = FORECAST_DEGRADED_CACHE_TTL
        logger.warning(
            "Ensemble вырожден: отработали %s из %s, кэш на %s с",
            models_ran or "нет моделей", expected_models, ttl,
        )

    await cache_svc.set(cache_key, response, ttl=ttl)
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

    Возвращает метрики качества (RMSE, MAE) для Prophet, XGBoost и ансамбля —
    взвешенного среднего этих двух моделей.
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

        # Phase 2+3: district-aware weather (центроид) + events (CITY_TO_DISTRICT match)
        weather_data, events_data = await _get_weather_and_events(
            history, days_ahead=0, weather_svc=weather_svc, data_svc=data_svc, district=district
        )

        metrics = await run_sync(
            ensemble_svc.compare_models,
            history=history,
            weather_data=weather_data,
            events_data=events_data,
            test_days=test_days,
            district=district,
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
            "best_model": metrics.get("best_model", "") if isinstance(metrics, dict) else "",
            "metrics": metrics,
            "feature_importance": feature_importance,
        }

        _evict_compare_cache()
        _compare_results[lock_key] = (time.time(), response)
        await cache_svc.set(cache_key, response, ttl=FORECAST_CACHE_TTL)
        return response


LLM_EXPLAIN_TIMEOUT_S = 30.0


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
                # Агентские factors несут {name, impact, description, direction} —
                # ровно контракт фронта (бейджи ↑/↓). _extract даёт лишь {name, importance}
                # без направления, поэтому предпочитаем агентские, а importance — fallback.
                "factors": result.get("factors") or factors,
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
    days_ahead: int = Query(14, ge=1, le=MAX_FORECAST_HORIZON_DAYS),
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
        # Phase 8: with_ci версия — отдаёт lower/upper для расчёта ci_coverage
        saved_with_ci = await data.get_saved_forecasts_with_ci(district=district, dates=target_dates)
    except Exception:
        logger.warning("forecast_validation: get_saved_forecasts_with_ci failed", exc_info=True)
        saved_with_ci = {}

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
    ci_lower_list: list[float] = []
    ci_upper_list: list[float] = []
    ci_hits = 0  # Сколько раз actual попал в [lower, upper]
    ci_total = 0  # Сколько раз lower/upper были доступны
    for d in target_dates:
        rec = saved_with_ci.get(d) or {}
        f = rec.get("occupancy")
        a = actual_map.get(d)
        if f is None or a is None:
            continue
        pairs.append((f, a))
        forecasted.append(ValidationPoint(date=d.isoformat(), occupancy=f))
        actual.append(ValidationPoint(date=d.isoformat(), occupancy=a))
        lb, ub = rec.get("lower"), rec.get("upper")
        if lb is not None and ub is not None:
            ci_lower_list.append(round(float(lb), 1))
            ci_upper_list.append(round(float(ub), 1))
            ci_total += 1
            if lb <= a <= ub:
                ci_hits += 1
        else:
            ci_lower_list.append(round(f - 8.0, 1))
            ci_upper_list.append(round(f + 8.0, 1))

    if not pairs:
        return ForecastValidationResponse(
            district=district, days_back=days_back, samples=0,
            rmse=None, mae=None, mae_per_day=[], forecasted=[], actual=[],
            ci_coverage=None,
        )

    rmse = math.sqrt(sum((f - a) ** 2 for f, a in pairs) / len(pairs))
    mae = sum(abs(f - a) for f, a in pairs) / len(pairs)
    ci_coverage = round(ci_hits / ci_total, 3) if ci_total >= 3 else None  # min 3 для статистической значимости
    return ForecastValidationResponse(
        district=district,
        days_back=days_back,
        samples=len(pairs),
        rmse=round(rmse, 2),
        mae=round(mae, 2),
        mae_per_day=[round(abs(f - a), 2) for f, a in pairs],
        forecasted=forecasted,
        actual=actual,
        ci_coverage=ci_coverage,
        ci_lower=ci_lower_list,
        ci_upper=ci_upper_list,
    )


# ---------------------------------------------------------------------------
# Per-hotel backtest validation (preferred for честность защиты ВКР)
# ---------------------------------------------------------------------------

HOTEL_VALIDATION_CACHE_TTL = 1800  # 30 минут


def _backtest_metrics(forecasted: list[float], actual: list[float]) -> dict[str, float | None]:
    """RMSE/MAE/R²/MAPE из пары списков (одинаковая длина).

    R² не определён, когда факт на тестовом окне постоянен (дисперсии нет),
    MAPE — когда объект всё окно стоял пустым (делить не на что). В обоих
    случаях возвращается None: ноль на их месте читался бы как идеальная
    точность.

    Args:
        forecasted: Прогнозные значения загрузки.
        actual: Фактические значения загрузки за те же даты.

    Returns:
        Словарь rmse/mae/r2/mape; None у метрик, которые не определены.
    """
    import math

    n = len(forecasted)
    if n == 0:
        return {"rmse": None, "mae": None, "r2": None, "mape": None}
    rmse = math.sqrt(sum((f - a) ** 2 for f, a in zip(forecasted, actual)) / n)
    mae = sum(abs(f - a) for f, a in zip(forecasted, actual)) / n
    mean_actual = sum(actual) / n
    ss_tot = sum((a - mean_actual) ** 2 for a in actual)
    ss_res = sum((a - f) ** 2 for f, a in zip(forecasted, actual))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot > 0 else None
    mape_pairs = [(f, a) for f, a in zip(forecasted, actual) if a >= 1.0]
    mape = (
        sum(abs(f - a) / a for f, a in mape_pairs) / len(mape_pairs) * 100.0
        if mape_pairs else None
    )
    return {"rmse": rmse, "mae": mae, "r2": r2, "mape": mape}


async def _hotel_backtest_validation(
    *,
    hotel_id: str,
    data_svc,
    prophet_svc,
    weather_svc,
    test_days: int = 14,
    min_history: int = 30,
) -> HotelValidationResponse | None:
    """Backtest для одного отеля. Возвращает None если истории недостаточно.

    Алгоритм: тянем `get_hotel_statistics(hotel_id)`, считаем occupancy = 100 - available%,
    отрезаем последние test_days как hold-out, обучаем Prophet на остатке (with weather),
    прогнозируем test_days, сравниваем с фактом.
    """
    try:
        stats = await data_svc.get_hotel_statistics(hotel_id=hotel_id)
    except Exception as e:
        logger.warning(f"hotel_backtest: get_hotel_statistics failed for {hotel_id}: {e}")
        return None

    history = [
        {"date": s.date, "occupancy": 100.0 - (s.available_rooms_percent or 0)}
        for s in stats
        if s.available_rooms_percent is not None
    ]
    if len(history) < min_history + test_days:
        return HotelValidationResponse(
            hotel_id=hotel_id,
            history_points=len(history),
            test_days=test_days,
            samples=0,
            error=f"Недостаточно истории: {len(history)} точек, требуется минимум {min_history + test_days}",
        )

    # Hold-out: последние test_days точек = test, остальное = train
    train = history[:-test_days]
    test = history[-test_days:]

    # Получаем погоду на все даты (history + test_period)
    all_dates = [h["date"] for h in history]
    weather_data: dict = {}
    try:
        weather_data = await weather_svc.get_weather_for_dates(all_dates)
    except Exception as e:
        logger.warning(f"hotel_backtest: weather fetch failed for {hotel_id}: {e}")

    # Запускаем Prophet через executor (синхронный fit)
    try:
        forecast_points = await prophet_svc.forecast_occupancy_async(
            history=train, days_ahead=test_days,
            weather_data=weather_data, events_data=[],
        )
    except Exception as e:
        logger.warning(f"hotel_backtest: prophet failed for {hotel_id}: {e}")
        return HotelValidationResponse(
            hotel_id=hotel_id,
            history_points=len(history),
            test_days=test_days,
            samples=0,
            error=f"Ошибка прогноза: {e}",
        )

    # Сопоставление по дате
    from datetime import date as date_type
    def _to_date(v) -> date_type | None:
        if isinstance(v, date_type):
            return v
        if isinstance(v, str):
            try:
                return date_type.fromisoformat(v[:10])
            except ValueError:
                return None
        return None

    forecast_map = {_to_date(fp.date): fp.occupancy for fp in forecast_points}
    actual_map = {_to_date(t["date"]): t["occupancy"] for t in test}

    paired_dates = sorted(d for d in forecast_map.keys() & actual_map.keys() if d)
    if not paired_dates:
        return HotelValidationResponse(
            hotel_id=hotel_id,
            history_points=len(history),
            test_days=test_days,
            samples=0,
            error="Прогноз и факт не пересекаются по датам",
        )

    forecasted_vals = [forecast_map[d] for d in paired_dates]
    actual_vals = [actual_map[d] for d in paired_dates]
    metrics = _backtest_metrics(forecasted_vals, actual_vals)

    def _round(name: str, digits: int) -> float | None:
        value = metrics[name]
        return round(value, digits) if value is not None else None

    return HotelValidationResponse(
        hotel_id=hotel_id,
        history_points=len(history),
        test_days=test_days,
        samples=len(paired_dates),
        rmse=_round("rmse", 2),
        mae=_round("mae", 2),
        r2=_round("r2", 3),
        mape=_round("mape", 1),
        forecasted=[ValidationPoint(date=d.isoformat(), occupancy=round(v, 1)) for d, v in zip(paired_dates, forecasted_vals)],
        actual=[ValidationPoint(date=d.isoformat(), occupancy=round(v, 1)) for d, v in zip(paired_dates, actual_vals)],
    )


@router.get("/hotel/{hotel_id}/validation", response_model=HotelValidationResponse)
async def hotel_forecast_validation(
    hotel_id: str,
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    weather_svc: WeatherServiceDep,
    cache_svc: CacheServiceDep,
    test_days: int = Query(14, ge=3, le=30),
) -> HotelValidationResponse:
    """Backtest validation для конкретного отеля (Prophet single-model).

    Преподаватель на ВКР подсказал: «прогнозирование для конкретных средств размещения —
    точность лучше проверять per-hotel, чем на районном агрегате». Этот endpoint
    делает это без зависимости от сохранённых прогнозов: отрезаем последние test_days
    как hold-out, обучаем модель на остатке, сравниваем прогноз с фактом.
    """
    cache_key = cache_svc.cache_key("hotel_validation", hotel_id, test_days)
    cached = await cache_svc.get(cache_key)
    if cached:
        logger.info(f"hotel_validation cache hit: {hotel_id}")
        return HotelValidationResponse(**cached)

    result = await _hotel_backtest_validation(
        hotel_id=hotel_id, data_svc=data_svc, prophet_svc=prophet_svc,
        weather_svc=weather_svc, test_days=test_days,
    )
    if result is None:
        raise HTTPException(404, f"Отель {hotel_id} не найден или ошибка получения данных")

    # Подтянем hotel_name из БД
    try:
        hotels, _ = await data_svc.get_hotels(limit=1, offset=0)
        from sqlalchemy import select  # noqa
        # упрощённый поиск имени через get_hotel_latest_stats или через separate query
        latest = await data_svc.get_hotel_latest_stats(hotel_id)
        if latest:
            result.hotel_name = latest.get("hotel_name") or latest.get("name")
    except Exception:
        pass

    await cache_svc.set(cache_key, result.model_dump(), ttl=HOTEL_VALIDATION_CACHE_TTL)
    return result


@router.get("/hotels/validation-summary", response_model=HotelValidationSummaryResponse)
async def hotels_validation_summary(
    data_svc: DataServiceDep,
    prophet_svc: ProphetServiceDep,
    weather_svc: WeatherServiceDep,
    cache_svc: CacheServiceDep,
    top_n: int = Query(10, ge=3, le=30),
    test_days: int = Query(14, ge=7, le=21),
) -> HotelValidationSummaryResponse:
    """Batch backtest для топ-N самых крупных отелей с достаточной историей.

    Используется на странице About / Analytics как доказательство точности
    per-hotel прогнозов. Возвращает median/p25/p75 RMSE — robust к outliers.
    """
    cache_key = cache_svc.cache_key("hotels_validation_summary", top_n, test_days)
    cached = await cache_svc.get(cache_key)
    if cached:
        return HotelValidationSummaryResponse(**cached)

    # Берём топ-N отелей с наибольшим средним rooms_num по статистике (proxy «крупности»).
    # rooms_num — колонка hot.hotel_statistics (не hotels), берём MAX за всю историю.
    candidates: list[dict] = []
    try:
        from sqlalchemy import text as sql_text
        from app.db.session import async_session
        async with async_session() as s:
            rows = (await s.execute(sql_text(
                """
                SELECT h.id, h.name, h.district,
                       MAX(hs.rooms_num) AS rooms_num,
                       COUNT(hs.date) AS history_points
                FROM hotels h
                JOIN hotel_statistics hs ON hs.id = h.id
                WHERE hs.rooms_num >= 20
                GROUP BY h.id, h.name, h.district
                HAVING COUNT(hs.date) >= 60
                ORDER BY MAX(hs.rooms_num) DESC, COUNT(hs.date) DESC
                LIMIT :n
                """
            ), {"n": top_n})).all()
            for r in rows:
                candidates.append({
                    "hotel_id": r.id, "name": r.name, "district": r.district,
                    "rooms_num": r.rooms_num, "history_points": r.history_points,
                })
    except Exception as e:
        logger.error(f"hotels_validation_summary: candidate query failed: {e}")
        raise HTTPException(500, "Не удалось получить список отелей для validation")

    if not candidates:
        return HotelValidationSummaryResponse(n_evaluated=0)

    # Запускаем backtest для каждого (sequential — Prophet single-threaded; параллельно через asyncio.gather)
    results: list[HotelValidationResponse] = []
    for cand in candidates:
        res = await _hotel_backtest_validation(
            hotel_id=cand["hotel_id"], data_svc=data_svc, prophet_svc=prophet_svc,
            weather_svc=weather_svc, test_days=test_days,
        )
        if res and res.samples > 0 and res.rmse is not None:
            res.hotel_name = cand["name"]
            results.append(res)

    if not results:
        return HotelValidationSummaryResponse(n_evaluated=0)

    rmses = sorted(r.rmse for r in results if r.rmse is not None)
    maes = sorted(r.mae for r in results if r.mae is not None)
    r2s = sorted(r.r2 for r in results if r.r2 is not None)

    def _percentile(sorted_vals: list[float], p: float) -> float | None:
        if not sorted_vals:
            return None
        idx = max(0, min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1)))))
        return round(sorted_vals[idx], 2)

    items = [
        HotelValidationSummaryItem(
            hotel_id=r.hotel_id,
            hotel_name=r.hotel_name,
            district=next((c["district"] for c in candidates if c["hotel_id"] == r.hotel_id), None),
            rooms_num=next((c["rooms_num"] for c in candidates if c["hotel_id"] == r.hotel_id), None),
            history_points=r.history_points,
            rmse=r.rmse, mae=r.mae, r2=r.r2,
        )
        for r in results
    ]

    response = HotelValidationSummaryResponse(
        n_evaluated=len(results),
        median_rmse=_percentile(rmses, 0.5),
        p25_rmse=_percentile(rmses, 0.25),
        p75_rmse=_percentile(rmses, 0.75),
        median_mae=_percentile(maes, 0.5),
        median_r2=_percentile(r2s, 0.5),
        hotels=items,
    )
    await cache_svc.set(cache_key, response.model_dump(), ttl=HOTEL_VALIDATION_CACHE_TTL)
    return response
