"""LangGraph Agent для объяснимых прогнозов загрузки.

Использует Command pattern для маршрутизации и PydanticOutputParser
для структурированного вывода LLM.
Паттерн вдохновлён executory_formula.ipynb (Pydantic + Command + ChatPromptTemplate).
"""
import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.constants import (
    VALID_DISTRICTS,
    CITY_TO_DISTRICT,
    MIN_HISTORY_DAYS,
    MAX_FORECAST_DAYS,
    IMPACT,
    HIGH_SEASON_MONTHS,
    WINTER_SEASON_MONTHS,
    OFFSEASON_MONTHS,
    WARM_TEMP_THRESHOLD,
    COLD_TEMP_THRESHOLD,
    EVENT_SEARCH_RANGE_DAYS,
)
from app.services.data_service import data_service
from app.services.weather_service import weather_service
from app.services.prophet_service import prophet_service
from app.services.neuralprophet_service import neuralprophet_service
from app.services.xgboost_service import xgboost_service
from app.services.ensemble_service import ensemble_service
from app.services.holidays_service import holidays_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


# --- Pydantic модели для структурированного вывода ---

class ForecastExplanation(BaseModel):
    """Структурированное объяснение прогноза от LLM."""
    summary: str = Field(description="Краткое резюме прогноза (2-3 предложения)")
    main_factors: list[str] = Field(description="Список главных факторов влияния (2-4 пункта)")
    recommendation: str = Field(description="Практическая рекомендация для отельера (тариф, инвентарь, каналы)")
    confidence_note: str = Field(description="Оценка уверенности: высокая/средняя/низкая с пояснением")


# --- Состояние графа ---

class ForecastState(TypedDict):
    # Входные
    district: str
    days_ahead: int
    target_date: str | None

    # Данные
    history: list[dict]
    weather_data: dict
    events_data: list[dict]
    holidays_info: list[dict]

    # Модели
    forecasts: dict[str, list[dict]]
    best_model: str
    metrics: dict[str, dict]
    feature_importance: dict[str, float]

    # Результат
    explanation: str
    factors: list[dict]
    recommendation: str

    # Мета
    error: str | None
    processing_time: float


# --- Агент ---

class ForecastAgent:
    """LangGraph Agent с Command routing и Pydantic structured output."""

    def __init__(self):
        self._compiled = self._build_graph()
        logger.info("ForecastAgent graph compiled (Command pattern)")

    def _build_graph(self):
        graph = StateGraph(ForecastState)

        graph.add_node("collect_data", self._collect_data)
        graph.add_node("run_models", self._run_models)
        graph.add_node("analyze_factors", self._analyze_factors)
        graph.add_node("generate_explanation", self._generate_explanation)

        graph.add_edge(START, "collect_data")

        return graph.compile()

    # --- Node 1: Сбор данных ---

    async def _collect_data(
        self, state: ForecastState
    ) -> Command[Literal["run_models", "__end__"]]:
        logger.info(f"Collecting data for {state['district']}...")

        try:
            history_raw = await data_service.get_occupancy_by_district(state["district"])
            history = [
                {"date": row["date"], "occupancy": row["avg_occupancy"]}
                for row in history_raw
            ]
            logger.info(f"History: {len(history)} points")

            if len(history) < MIN_HISTORY_DAYS:
                return Command(
                    update={
                        "history": history,
                        "error": f"Недостаточно данных ({len(history)}/{MIN_HISTORY_DAYS})",
                        "explanation": f"Для прогноза нужно минимум {MIN_HISTORY_DAYS} дней истории, найдено {len(history)}.",
                        "recommendation": "Подождите накопления данных или выберите район с большей историей.",
                    },
                    goto="__end__",
                )

            weather_data = {}
            if history:
                all_dates = [h["date"] for h in history]
                last_date = max(all_dates) if all_dates else date.today()
                for i in range(state["days_ahead"]):
                    all_dates.append(last_date + timedelta(days=i + 1))
                weather_data = await weather_service.get_weather_for_dates(all_dates)

            events_raw = await data_service.get_events()
            events_data = [
                {
                    "date_start": e.get("date_start"),
                    "title": e.get("title"),
                    "event_type": e.get("event_type", "general"),
                }
                for e in events_raw
                if e.get("date_start")
            ]

            today = date.today()
            end_date = today + timedelta(days=state["days_ahead"] + 14)
            holidays_info = holidays_service.get_holidays_in_range(today, end_date)

            return Command(
                update={
                    "history": history,
                    "weather_data": weather_data,
                    "events_data": events_data,
                    "holidays_info": holidays_info,
                },
                goto="run_models",
            )
        except Exception as e:
            logger.error(f"Data collection error: {e}")
            return Command(
                update={"error": str(e), "explanation": f"Ошибка сбора данных: {e}"},
                goto="__end__",
            )

    # --- Node 2: Запуск моделей через Ensemble ---

    async def _run_models(
        self, state: ForecastState
    ) -> Command[Literal["analyze_factors", "__end__"]]:
        logger.info("Running forecast models via ensemble_service...")

        history = state["history"]
        weather_data = state["weather_data"]
        events_data = state["events_data"]
        days_ahead = state["days_ahead"]

        forecasts: dict[str, list] = {}
        feature_importance: dict[str, float] = {}
        best_model = "prophet"
        metrics: dict[str, dict] = {}

        try:
            ensemble_result = await ensemble_service.forecast_ensemble_async(
                history=history,
                days_ahead=days_ahead,
                weather_data=weather_data,
                events_data=events_data,
                method="weighted_average",
            )

            for model, points in ensemble_result.get("models", {}).items():
                forecasts[model] = [
                    {"date": str(f.date), "occupancy": f.occupancy} for f in points
                ]
                logger.info(f"{model}: {len(forecasts[model])} points")

            ensemble_pts = ensemble_result.get("ensemble", [])
            if ensemble_pts:
                forecasts["ensemble"] = [
                    {"date": str(f.date), "occupancy": f.occupancy,
                     "lower_bound": f.lower_bound, "upper_bound": f.upper_bound}
                    for f in ensemble_pts
                ]

            try:
                feature_importance = xgboost_service.get_feature_importance().get("xgboost", {})
            except Exception:
                pass

            try:
                metrics = await asyncio.to_thread(
                    ensemble_service.compare_models,
                    history=history,
                    weather_data=weather_data,
                    events_data=events_data,
                    test_days=min(7, len(history) // 5),
                )
                best_model = metrics.get("best_model", "prophet")
            except Exception as e:
                logger.warning(f"compare_models error: {e}")

        except Exception as e:
            logger.warning(f"Ensemble error: {e}, falling back to individual models")
            for name, service in [
                ("prophet", prophet_service),
                ("neuralprophet", neuralprophet_service),
                ("xgboost", xgboost_service),
            ]:
                try:
                    result = await asyncio.to_thread(
                        service.forecast_occupancy,
                        history=history, days_ahead=days_ahead,
                        weather_data=weather_data, events_data=events_data,
                    )
                    forecasts[name] = [
                        {"date": str(f.date), "occupancy": f.occupancy} for f in result
                    ]
                except Exception as me:
                    logger.error(f"{name} error: {me}")

        if not forecasts:
            return Command(
                update={
                    "forecasts": {},
                    "error": "Все модели вернули ошибку",
                    "explanation": "Не удалось построить прогноз — все модели завершились с ошибкой.",
                },
                goto="__end__",
            )

        return Command(
            update={
                "forecasts": forecasts,
                "best_model": best_model,
                "feature_importance": feature_importance,
                "metrics": metrics,
            },
            goto="analyze_factors",
        )

    # --- Node 3: Анализ факторов ---

    async def _analyze_factors(
        self, state: ForecastState
    ) -> Command[Literal["generate_explanation"]]:
        logger.info("Analyzing factors...")

        factors = []
        target_date = self._resolve_target_date(state)

        if holidays_service.is_holiday(target_date):
            holiday_name = "праздничный день"
            for h in state.get("holidays_info", []):
                if h["date"] == target_date:
                    holiday_name = h["name"]
                    break
            factors.append({
                "name": "Праздник", "impact": IMPACT.holiday,
                "description": f"{holiday_name} — повышенный спрос",
                "direction": "positive",
            })

        if target_date.weekday() >= 5:
            factors.append({
                "name": "Выходной день", "impact": IMPACT.weekend,
                "description": f"{'Суббота' if target_date.weekday() == 5 else 'Воскресенье'} — выше загрузка",
                "direction": "positive",
            })

        month = target_date.month
        if month in HIGH_SEASON_MONTHS:
            factors.append({"name": "Высокий сезон", "impact": IMPACT.high_season,
                            "description": "Лето — пик туризма на Байкале", "direction": "positive"})
        elif month in WINTER_SEASON_MONTHS:
            factors.append({"name": "Зимний сезон", "impact": IMPACT.winter_season,
                            "description": "Ледовый туризм на Байкале", "direction": "positive"})
        elif month in OFFSEASON_MONTHS:
            factors.append({"name": "Межсезонье", "impact": IMPACT.offseason,
                            "description": "Спад туристической активности", "direction": "negative"})

        events_near = self._find_nearby_events(state.get("events_data", []), target_date)
        if events_near:
            names = [e.get("title", "Событие")[:30] for e in events_near[:3]]
            factors.append({
                "name": "События", "impact": IMPACT.event_nearby * len(events_near),
                "description": f"Ближайшие: {', '.join(names)}", "direction": "positive",
            })

        weather = state.get("weather_data", {}).get(target_date, {})
        temp = weather.get("temperature")
        if temp is not None:
            if temp > WARM_TEMP_THRESHOLD:
                factors.append({"name": "Тёплая погода", "impact": IMPACT.good_weather,
                                "description": f"{temp}°C — комфортно", "direction": "positive"})
            elif temp < COLD_TEMP_THRESHOLD:
                factors.append({"name": "Холодная погода", "impact": IMPACT.cold_weather,
                                "description": f"{temp}°C — снижает поток", "direction": "negative"})

        fi = state.get("feature_importance", {})
        for feat, imp in list(fi.items())[:3]:
            if imp > 0.1:
                factors.append({
                    "name": f"ML: {feat}", "impact": round(imp * 100, 1),
                    "description": f"Важный фактор по XGBoost ({round(imp*100, 1)}%)",
                    "direction": "neutral",
                })

        return Command(update={"factors": factors}, goto="generate_explanation")

    # --- Node 4: LLM объяснение (PydanticOutputParser + ChatPromptTemplate) ---

    async def _generate_explanation(
        self, state: ForecastState
    ) -> Command[Literal["__end__"]]:
        logger.info("Generating structured explanation via LLM + PydanticOutputParser...")

        district = state["district"]
        target_date = state.get("target_date") or str(date.today() + timedelta(days=7))
        best_model = state.get("best_model", "neuralprophet")
        forecasts = state.get("forecasts", {})
        factors = state.get("factors", [])
        metrics = state.get("metrics", {})

        target_occupancy = self._get_target_occupancy(forecasts, best_model, target_date)
        level = "высокая" if (target_occupancy or 0) > 65 else "средняя" if (target_occupancy or 0) > 40 else "низкая"

        factors_text = "\n".join(
            f"- {f['name']}: {f['description']} ({'↑' if f['direction'] == 'positive' else '↓' if f['direction'] == 'negative' else '•'} {f.get('impact', '?')}%)"
            for f in factors
        ) or "нет значимых факторов"

        metrics_text = ""
        for m in ("prophet", "neuralprophet", "xgboost"):
            if m in metrics and isinstance(metrics[m], dict):
                rmse = metrics[m].get('rmse')
                mae = metrics[m].get('mae')
                rmse_str = f"{rmse:.1f}" if isinstance(rmse, (int, float)) else "N/A"
                mae_str = f"{mae:.1f}" if isinstance(mae, (int, float)) else "N/A"
                metrics_text += f"  {m}: RMSE={rmse_str}, MAE={mae_str}\n"

        try:
            parser = PydanticOutputParser(pydantic_object=ForecastExplanation)

            prompt = ChatPromptTemplate.from_template("""### Район
{district} (Иркутская область, Прибайкалье)

### Прогноз
Дата: {target_date}
Ожидаемая загрузка: {occupancy}% ({level})
Лучшая модель: {best_model}

### Метрики моделей
{metrics_text}

### Факторы
{factors_text}

### Задача
Сформируй структурированное объяснение прогноза.

### Формат вывода (обязательно!)
{format_instructions}""")

            formatted = prompt.format(
                district=district,
                target_date=target_date,
                occupancy=f"{target_occupancy:.1f}" if target_occupancy else "N/A",
                level=level,
                best_model=best_model,
                metrics_text=metrics_text or "нет данных",
                factors_text=factors_text,
                format_instructions=parser.get_format_instructions(),
            )

            raw_response = await llm_service.generate_simple(
                formatted,
                system_prompt="Ты — аналитик туризма Иркутской области и Байкала. Отвечай JSON."
            )

            try:
                parsed: ForecastExplanation = parser.parse(raw_response)
                explanation = parsed.summary
                recommendation = parsed.recommendation
                if parsed.main_factors:
                    explanation += "\n\nГлавные факторы:\n" + "\n".join(f"• {f}" for f in parsed.main_factors)
                explanation += f"\n\nУверенность: {parsed.confidence_note}"
            except Exception as parse_err:
                logger.warning(f"Pydantic parse fallback: {parse_err}")
                explanation = raw_response
                recommendation = self._generate_recommendation(target_occupancy, factors)

        except Exception as e:
            logger.error(f"LLM error: {e}")
            explanation = self._fallback_explanation(district, target_date, target_occupancy, factors)
            recommendation = self._generate_recommendation(target_occupancy, factors)

        return Command(
            update={"explanation": explanation, "recommendation": recommendation},
            goto="__end__",
        )

    # --- Вспомогательные методы ---

    def _resolve_target_date(self, state: ForecastState) -> date:
        td = state.get("target_date")
        if td:
            try:
                return date.fromisoformat(td)
            except ValueError:
                pass
        return date.today() + timedelta(days=7)

    def _find_nearby_events(self, events: list[dict], target: date) -> list[dict]:
        result = []
        for event in events:
            ed = event.get("date_start")
            if ed:
                if isinstance(ed, str):
                    try:
                        ed = date.fromisoformat(ed)
                    except ValueError:
                        continue
                diff = (ed - target).days
                if EVENT_SEARCH_RANGE_DAYS[0] <= diff <= EVENT_SEARCH_RANGE_DAYS[1]:
                    result.append(event)
        return result

    def _get_target_occupancy(
        self, forecasts: dict, model: str, target_date: str
    ) -> float | None:
        best = forecasts.get(model, [])
        for f in best:
            if f["date"] == target_date:
                return f["occupancy"]
        return best[0]["occupancy"] if best else None

    def _fallback_explanation(
        self, district: str, target_date: str, occ: float | None, factors: list[dict]
    ) -> str:
        if occ is None:
            return f"Прогноз для {district} на {target_date} недоступен."
        level = "высокая" if occ > 60 else "средняя" if occ > 40 else "низкая"
        text = f"Прогноз загрузки {district} на {target_date}: {occ:.1f}% ({level}).\n\n"
        if factors:
            text += "Факторы:\n"
            for f in factors[:3]:
                d = "↑" if f["direction"] == "positive" else "↓" if f["direction"] == "negative" else "•"
                text += f"{d} {f['name']}: {f['description']}\n"
        return text

    def _generate_recommendation(self, occ: float | None, factors: list[dict]) -> str:
        if occ is None:
            return "Недостаточно данных для рекомендации."
        if occ > 70:
            return "Высокий спрос: повысить тариф на 10-15%, ограничить скидки и раннее бронирование, поднять минимальный срок проживания."
        if occ > 50:
            return "Умеренный спрос: удерживать базовый тариф, точечный yield по дням недели."
        if occ > 30:
            return "Низкий спрос: стимулировать загрузку акциями и спецпредложениями, усилить продвижение в каналах."
        return "Очень низкий спрос: значительные скидки или пакетные предложения, активная работа с OTA-каналами."

    # --- Публичный API ---

    async def run(
        self,
        district: str,
        days_ahead: int = 14,
        target_date: str | None = None,
    ) -> dict[str, Any]:
        start = time.time()

        if days_ahead is None or days_ahead < 1:
            return self._error_result("invalid_days_ahead",
                f"Некорректное значение days_ahead: {days_ahead}.", start)

        if days_ahead > MAX_FORECAST_DAYS:
            days_ahead = MAX_FORECAST_DAYS

        if district:
            district = CITY_TO_DISTRICT.get(district.lower(), district)

        if not district or district not in VALID_DISTRICTS:
            matched = self._fuzzy_match_district(district)
            if not matched:
                return self._error_result("invalid_district",
                    f"Район '{district}' не найден. Доступные: {', '.join(VALID_DISTRICTS)}.", start)
            district = matched

        if target_date:
            validation = self._validate_target_date(target_date, start)
            if validation:
                return validation
            parsed = date.fromisoformat(target_date)
            if parsed < date.today():
                return await self._get_historical_analysis(district, target_date, start)

        initial: ForecastState = {
            "district": district, "days_ahead": days_ahead, "target_date": target_date,
            "history": [], "weather_data": {}, "events_data": [], "holidays_info": [],
            "forecasts": {}, "best_model": "", "metrics": {}, "feature_importance": {},
            "explanation": "", "factors": [], "recommendation": "",
            "error": None, "processing_time": 0.0,
        }

        try:
            result = await self._compiled.ainvoke(initial)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            result = {**initial, "error": str(e), "explanation": f"Ошибка агента: {e}"}

        result["processing_time"] = round(time.time() - start, 2)
        return result

    def _fuzzy_match_district(self, district: str | None) -> str | None:
        if not district:
            return None
        dl = district.lower()
        for vd in VALID_DISTRICTS:
            if vd.lower() in dl or dl in vd.lower():
                return vd
        return None

    def _validate_target_date(self, target_date: str, start: float) -> dict | None:
        try:
            parsed = date.fromisoformat(target_date)
            if parsed.year == 2025 and parsed.month in (7, 8, 9):
                return self._error_result("no_data_for_period",
                    f"Данные за {target_date} недоступны (июль-сентябрь 2025 — gap).", start)
            return None
        except ValueError:
            return self._error_result("invalid_date_format",
                f"Некорректный формат даты: {target_date}. Используйте YYYY-MM-DD.", start)

    def _error_result(self, code: str, msg: str, start: float) -> dict[str, Any]:
        return {
            "forecasts": {}, "best_model": "", "factors": [],
            "explanation": msg, "recommendation": "",
            "processing_time": round(time.time() - start, 2), "error": code,
        }

    async def _get_historical_analysis(
        self, district: str, target_date: str, start: float
    ) -> dict[str, Any]:
        parsed = date.fromisoformat(target_date)
        history = await data_service.get_occupancy_by_district(district)

        actual = None
        for row in history:
            if row.get("date") == parsed:
                actual = row.get("avg_occupancy")
                break

        date_note = ""
        if actual is None:
            closest, closest_occ, min_diff = None, None, float("inf")
            for row in history:
                rd = row.get("date")
                if rd:
                    diff = abs((rd - parsed).days)
                    if diff < min_diff:
                        min_diff, closest, closest_occ = diff, rd, row.get("avg_occupancy")
            if closest and min_diff <= 7:
                actual, date_note = closest_occ, f" (ближайшие данные: {closest})"
            else:
                return self._error_result("no_data_for_date",
                    f"Нет данных за {target_date} и ближайшие дни.", start)

        factors = self._analyze_historical_factors(parsed, history)

        try:
            explanation = await llm_service.generate_simple(
                f"Район: {district}, дата: {target_date}{date_note}, загрузка: {actual:.1f}%.\n"
                f"Факторы: {'; '.join(f['name'] for f in factors)}.\n"
                "Объясни кратко (2-3 предложения) почему загрузка была такой.",
                system_prompt="Ты — аналитик туризма Байкала. Кратко и по делу."
            )
        except Exception as e:
            logger.error(f"LLM historical error: {e}")
            level = "высокая" if actual > 60 else "средняя" if actual > 40 else "низкая"
            explanation = f"Загрузка {district} {target_date} составила {actual:.1f}% ({level})."

        return {
            "forecasts": {}, "best_model": "historical_data",
            "actual_occupancy": actual, "factors": factors,
            "explanation": explanation, "recommendation": f"Исторические данные за {target_date}.",
            "processing_time": round(time.time() - start, 2),
            "error": None, "is_historical": True,
        }

    def _analyze_historical_factors(self, d: date, history: list) -> list[dict]:
        factors = []
        if d.month in HIGH_SEASON_MONTHS:
            factors.append({"name": "Летний сезон", "impact": IMPACT.high_season,
                            "description": "Высокий сезон на Байкале", "direction": "positive"})
        elif d.month in WINTER_SEASON_MONTHS:
            factors.append({"name": "Зимний сезон", "impact": IMPACT.winter_season,
                            "description": "Ледовый туризм", "direction": "positive"})
        if holidays_service.is_holiday(d):
            factors.append({"name": "Праздник", "impact": IMPACT.holiday,
                            "description": holidays_service.get_holiday_name(d) or "Праздник",
                            "direction": "positive"})
        if d.weekday() >= 5:
            factors.append({"name": "Выходной", "impact": IMPACT.weekend,
                            "description": "Суббота" if d.weekday() == 5 else "Воскресенье",
                            "direction": "positive"})
        return factors


forecast_agent = ForecastAgent()
