"""Unit тесты для новых B2B tools (A1-A6).

Запуск:
    cd backend
    pytest tests/test_agent_new_tools.py -v
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status: int, json_data):
    """Создать мок httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = json_data
    return mock_resp


# ---------------------------------------------------------------------------
# Fixtures — образцы ответов бэкенда
# ---------------------------------------------------------------------------

# Ключи соответствуют реальному контракту /api/analytics/events-impact
# (methodology_service.corrected_impact → baseline_mean, n_samples). Раньше здесь
# стояли baseline_occupancy/n — те же неверные ключи, что читал код агента, из-за
# чего baseline/n печатались как 0.0/— на проде, а тест этого не замечал.
EVENTS_IMPACT_PAYLOAD = [
    {
        "event": "Фестиваль Байкал",
        "date": "2026-07-15",
        "district": "Иркутский",
        "delta_pct": 22.5,
        "baseline_mean": 55.0,
        "n_samples": 8,
        "confidence": "high",
    },
    {
        "event": "Новый год",
        "date": "2025-12-31",
        "district": "Ольхонский",
        "delta_pct": -5.3,
        "baseline_mean": 40.0,
        "n_samples": 3,
        "confidence": "low",
    },
]

BOOKING_PACE_PAYLOAD = {
    "summary": {
        "avg_proxy_pickup_pct": 12.5,
        "trend": "growing",
        "min_proxy_pickup_pct": 3.0,
        "max_proxy_pickup_pct": 28.0,
    },
    "points": [{"date": "2026-05-04", "proxy_pickup_pct": 12.5}] * 14,
    "method": "rolling_7d",
}

COMPARE_DISTRICTS_PAYLOAD = [
    {
        "district": "Иркутский",
        "occupancy": 63.2,
        "adr_proxy": 3500.0,
        "revpar_proxy": 2212.0,
        "samples": 45,
    },
    {
        "district": "Ольхонский",
        "occupancy": 48.7,
        "adr_proxy": 2800.0,
        "revpar_proxy": 1363.6,
        "samples": 20,
    },
]

COMPARE_MODELS_PAYLOAD = {
    "district": "Иркутский",
    "history_points": 365,
    "test_days": 14,
    "metrics": {
        "prophet": {"rmse": 8.5, "mae": 6.1, "r2": 0.72},
        "xgboost": {"rmse": 7.8, "mae": 5.9, "r2": 0.76},
    },
    "feature_importance": {},
}

OCCUPANCY_TIMESERIES_PAYLOAD = {
    "data": [{"date": f"2026-04-{d:02d}", "occupancy": 55.0 + d * 0.5} for d in range(1, 31)],
    "summary": {
        "avg": 62.3,
        "min": 55.0,
        "max": 69.5,
        "samples": 30,
    },
}

PRICE_DISTRIBUTION_PAYLOAD = {
    "distribution": {
        "p10": 1500.0,
        "p25": 2200.0,
        "p50": 3100.0,
        "p75": 4500.0,
        "p90": 6800.0,
    },
    "samples": 120,
}


# ---------------------------------------------------------------------------
# A1: get_top_events_by_impact
# ---------------------------------------------------------------------------

class TestGetTopEventsByImpact:
    @pytest.mark.asyncio
    async def test_returns_top_events(self):
        from app.services.main_agent import get_top_events_by_impact

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, EVENTS_IMPACT_PAYLOAD)
            result = await get_top_events_by_impact.ainvoke({"n": 5, "min_impact": 0.0, "district": None})

        assert "Топ-" in result
        assert "Фестиваль Байкал" in result
        assert "22.5%" in result or "+22.5%" in result
        assert "high" in result
        # Регрессия: baseline и n должны браться из baseline_mean/n_samples,
        # а не печататься как 0.0/— из-за рассинхрона ключей.
        assert "baseline 55.0%" in result
        assert "n=8" in result

    @pytest.mark.asyncio
    async def test_filters_by_district(self):
        from app.services.main_agent import get_top_events_by_impact

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, EVENTS_IMPACT_PAYLOAD)
            result = await get_top_events_by_impact.ainvoke(
                {"n": 5, "min_impact": 0.0, "district": "Ольхонский"}
            )

        assert "Новый год" in result
        assert "Фестиваль Байкал" not in result

    @pytest.mark.asyncio
    async def test_filters_by_min_impact(self):
        from app.services.main_agent import get_top_events_by_impact

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, EVENTS_IMPACT_PAYLOAD)
            result = await get_top_events_by_impact.ainvoke(
                {"n": 5, "min_impact": 10.0, "district": None}
            )

        # Только Фестиваль (22.5%), Новый год (5.3%) не проходит порог
        assert "Фестиваль Байкал" in result
        assert "Новый год" not in result

    @pytest.mark.asyncio
    async def test_network_error_returns_text(self):
        from app.services.main_agent import get_top_events_by_impact

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (0, None)
            result = await get_top_events_by_impact.ainvoke({"n": 5, "min_impact": 0.0, "district": None})

        assert "недоступен" in result.lower() or "ошибка" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_data_returns_text(self):
        from app.services.main_agent import get_top_events_by_impact

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, [])
            result = await get_top_events_by_impact.ainvoke({"n": 5, "min_impact": 0.0, "district": None})

        assert "не накоплены" in result.lower() or "нет данных" in result.lower() or "пока" in result.lower()


# ---------------------------------------------------------------------------
# A2: get_booking_pace
# ---------------------------------------------------------------------------

class TestGetBookingPace:
    @pytest.mark.asyncio
    async def test_returns_pace_summary(self):
        from app.services.main_agent import get_booking_pace

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, BOOKING_PACE_PAYLOAD)
            result = await get_booking_pace.ainvoke({"district": "Иркутский", "days_ahead": 14})

        assert "Иркутский" in result
        assert "12.5%" in result
        assert "growing" in result or "Тренд" in result
        assert "14" in result
        assert "rolling_7d" in result

    @pytest.mark.asyncio
    async def test_shows_point_count(self):
        from app.services.main_agent import get_booking_pace

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, BOOKING_PACE_PAYLOAD)
            result = await get_booking_pace.ainvoke({"district": "Иркутский", "days_ahead": 14})

        assert "14" in result  # 14 points

    @pytest.mark.asyncio
    async def test_network_error(self):
        from app.services.main_agent import get_booking_pace

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (0, None)
            result = await get_booking_pace.ainvoke({"district": "Иркутский", "days_ahead": 14})

        assert "недоступен" in result.lower()

    @pytest.mark.asyncio
    async def test_http_error_returns_text(self):
        from app.services.main_agent import get_booking_pace

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (404, None)
            result = await get_booking_pace.ainvoke({"district": "Иркутский", "days_ahead": 14})

        assert "404" in result or "не удалось" in result.lower()


# ---------------------------------------------------------------------------
# A3: compare_districts
# ---------------------------------------------------------------------------

class TestCompareDistricts:
    @pytest.mark.asyncio
    async def test_returns_table(self):
        from app.services.main_agent import compare_districts

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, COMPARE_DISTRICTS_PAYLOAD)
            result = await compare_districts.ainvoke(
                {"districts": ["Иркутский", "Ольхонский"], "days": 30}
            )

        assert "Сравнение районов" in result
        assert "Иркутский" in result
        assert "Ольхонский" in result
        assert "63.2%" in result or "63.2" in result
        assert "30" in result

    @pytest.mark.asyncio
    async def test_default_districts_used(self):
        from app.services.main_agent import compare_districts

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, [])
            result = await compare_districts.ainvoke({"districts": None, "days": 30})
            # default districts should be passed as params
            call_kwargs = mock_get.call_args
            params = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("params", {})
            assert "Иркутский" in params.get("districts", "")

    @pytest.mark.asyncio
    async def test_network_error(self):
        from app.services.main_agent import compare_districts

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (0, None)
            result = await compare_districts.ainvoke(
                {"districts": ["Иркутский"], "days": 30}
            )

        assert "недоступен" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_rows(self):
        from app.services.main_agent import compare_districts

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, [])
            result = await compare_districts.ainvoke(
                {"districts": ["Иркутский"], "days": 30}
            )

        assert "нет данных" in result.lower()


# ---------------------------------------------------------------------------
# A4: compare_forecast_models
# ---------------------------------------------------------------------------

class TestCompareForecastModels:
    @pytest.mark.asyncio
    async def test_returns_model_metrics(self):
        from app.services.main_agent import compare_forecast_models

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, COMPARE_MODELS_PAYLOAD)
            result = await compare_forecast_models.ainvoke(
                {"district": "Иркутский", "days": 14}
            )

        assert "Иркутский" in result
        assert "Prophet" in result
        assert "XGBoost" in result
        assert "Лучшая модель" in result
        assert "NeuralProphet" not in result

    @pytest.mark.asyncio
    async def test_shows_rmse_mae_r2(self):
        from app.services.main_agent import compare_forecast_models

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, COMPARE_MODELS_PAYLOAD)
            result = await compare_forecast_models.ainvoke(
                {"district": "Иркутский", "days": 14}
            )

        assert "RMSE" in result
        assert "MAE" in result
        assert "R²" in result
        assert "8.50" in result or "8.5" in result

    @pytest.mark.asyncio
    async def test_network_error(self):
        from app.services.main_agent import compare_forecast_models

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (0, None)
            result = await compare_forecast_models.ainvoke(
                {"district": "Иркутский", "days": 14}
            )

        assert "недоступен" in result.lower()


# ---------------------------------------------------------------------------
# A5: get_occupancy_timeseries
# ---------------------------------------------------------------------------

class TestGetOccupancyTimeseries:
    @pytest.mark.asyncio
    async def test_returns_summary(self):
        from app.services.main_agent import get_occupancy_timeseries

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, OCCUPANCY_TIMESERIES_PAYLOAD)
            result = await get_occupancy_timeseries.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "Иркутский" in result
        assert "62.3" in result or "Среднее" in result
        assert "30" in result
        assert "Точек данных" in result

    @pytest.mark.asyncio
    async def test_shows_last_7_days(self):
        from app.services.main_agent import get_occupancy_timeseries

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, OCCUPANCY_TIMESERIES_PAYLOAD)
            result = await get_occupancy_timeseries.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "Последние 7 дней" in result
        assert "2026-04-30" in result or "2026-04" in result

    @pytest.mark.asyncio
    async def test_computes_stats_without_summary(self):
        """Должен посчитать среднее/мин/макс сам, если summary отсутствует."""
        from app.services.main_agent import get_occupancy_timeseries

        payload_no_summary = {
            "data": [{"date": f"2026-04-{d:02d}", "occupancy": float(50 + d)} for d in range(1, 8)]
        }
        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, payload_no_summary)
            result = await get_occupancy_timeseries.ainvoke(
                {"district": "Иркутский", "days": 7}
            )

        assert "Среднее" in result
        assert "%" in result

    @pytest.mark.asyncio
    async def test_empty_data(self):
        from app.services.main_agent import get_occupancy_timeseries

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, {"data": [], "summary": {}})
            result = await get_occupancy_timeseries.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "нет данных" in result.lower()

    @pytest.mark.asyncio
    async def test_network_error(self):
        from app.services.main_agent import get_occupancy_timeseries

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (0, None)
            result = await get_occupancy_timeseries.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "недоступен" in result.lower()


# ---------------------------------------------------------------------------
# A6: get_price_distribution
# ---------------------------------------------------------------------------

class TestGetPriceDistribution:
    @pytest.mark.asyncio
    async def test_returns_percentiles(self):
        from app.services.main_agent import get_price_distribution

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, PRICE_DISTRIBUTION_PAYLOAD)
            result = await get_price_distribution.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "Иркутский" in result
        assert "p10" in result
        assert "p50" in result
        assert "p90" in result
        assert "1500" in result
        assert "3100" in result
        assert "6800" in result
        assert "₽" in result

    @pytest.mark.asyncio
    async def test_shows_samples(self):
        from app.services.main_agent import get_price_distribution

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (200, PRICE_DISTRIBUTION_PAYLOAD)
            result = await get_price_distribution.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "120" in result or "samples" in result.lower()

    @pytest.mark.asyncio
    async def test_network_error(self):
        from app.services.main_agent import get_price_distribution

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (0, None)
            result = await get_price_distribution.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "недоступен" in result.lower()

    @pytest.mark.asyncio
    async def test_http_500_returns_text(self):
        from app.services.main_agent import get_price_distribution

        with patch("app.services.main_agent._agent_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (500, None)
            result = await get_price_distribution.ainvoke(
                {"district": "Иркутский", "days": 30}
            )

        assert "500" in result or "не удалось" in result.lower()


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestNewToolsRegistration:
    def test_all_new_tools_registered(self):
        from app.services.main_agent import ALL_TOOLS

        names = [t.name for t in ALL_TOOLS]
        for expected in [
            "get_top_events_by_impact",
            "get_booking_pace",
            "compare_districts",
            "compare_forecast_models",
            "get_occupancy_timeseries",
            "get_price_distribution",
        ]:
            assert expected in names, f"{expected} не зарегистрирован в ALL_TOOLS"

    def test_all_tools_count_12(self):
        from app.services.main_agent import ALL_TOOLS

        assert len(ALL_TOOLS) == 12

    def test_tools_by_name_has_all_new(self):
        from app.services.main_agent import TOOLS_BY_NAME

        for expected in [
            "get_top_events_by_impact",
            "get_booking_pace",
            "compare_districts",
            "compare_forecast_models",
            "get_occupancy_timeseries",
            "get_price_distribution",
        ]:
            assert expected in TOOLS_BY_NAME

    def test_system_prompt_has_methodology_rules(self):
        """System prompt must include 8 methodological rules for B2B response format."""
        from app.services.main_agent import AGENT_SYSTEM_PROMPT
        prompt = AGENT_SYSTEM_PROMPT.lower()
        # Rule 1 — район
        assert "район" in prompt
        # Rule 2 — период
        assert "период" in prompt
        # Rule 3 — метод / методологию
        assert "методолог" in prompt or "метод" in prompt
        # Rule 4 — база для сравнения / baseline
        assert "baseline" in prompt or "базу" in prompt or "базе" in prompt or "сравнения" in prompt
        # Rule 5 — не выдумывай при нехватке данных
        assert "не хватает" in prompt or "не выдумыва" in prompt or "нехватк" in prompt
        # Rule 6 — сегментный benchmark
        assert "сегмент" in prompt
        # Rule 7 — прокси
        assert "прокси" in prompt
        # Rule 8 — gap / июль-сентябрь 2025
        assert "gap" in prompt or "июль" in prompt or "пробел" in prompt

    def test_new_tools_are_async(self):
        from app.services.main_agent import (
            get_top_events_by_impact,
            get_booking_pace,
            compare_districts,
            compare_forecast_models,
            get_occupancy_timeseries,
            get_price_distribution,
        )
        for t in [
            get_top_events_by_impact,
            get_booking_pace,
            compare_districts,
            compare_forecast_models,
            get_occupancy_timeseries,
            get_price_distribution,
        ]:
            assert hasattr(t, "coroutine") and t.coroutine is not None, (
                f"{t.name} должен быть async StructuredTool"
            )
