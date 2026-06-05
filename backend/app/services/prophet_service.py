"""Prophet сервис для прогнозирования загрузки отелей.

Использует погоду как future regressor и события как holidays.
"""
import asyncio
import logging
from datetime import date, timedelta

import pandas as pd
from prophet import Prophet

from app.models.schemas import ForecastPoint
from app.constants import AVG_MONTHLY_TEMP_IRKUTSK
from app.services.holidays_service import holidays_service

logger = logging.getLogger(__name__)


class ProphetService:
    """Сервис прогнозирования на основе Prophet с weather regressors."""

    def forecast_occupancy(
        self,
        history: list[dict],
        days_ahead: int = 30,
        events: list[dict] | None = None,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
    ) -> list[ForecastPoint]:
        """
        Прогноз заполняемости с учётом погоды и событий.

        Args:
            history: [{date, occupancy}, ...]
            days_ahead: Количество дней прогноза
            events: Список событий для holidays (legacy)
            weather_data: {date: {temperature, precipitation}}
            events_data: Список событий [{date_start, title}, ...]
        """
        if len(history) < 7:
            return []

        df = pd.DataFrame(history)
        df = df.rename(columns={"date": "ds", "occupancy": "y"})
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.dropna().sort_values("ds").reset_index(drop=True)

        holidays_df = self._build_holidays(events, events_data, history)
        use_weather = weather_data and len(weather_data) > 0

        if use_weather:
            df = self._add_weather_column(df, weather_data)

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.8,
            holidays=holidays_df,
        )

        if use_weather:
            model.add_regressor("temperature")
            model.add_regressor("precipitation")

        model.fit(df)

        future = model.make_future_dataframe(periods=days_ahead)

        if use_weather:
            future = self._add_weather_column(future, weather_data)

        forecast = model.predict(future)

        result = []
        for _, row in forecast.tail(days_ahead).iterrows():
            occ = float(row["yhat"]) if not pd.isna(row["yhat"]) else 50.0
            lb = float(row["yhat_lower"]) if not pd.isna(row["yhat_lower"]) else occ - 10
            ub = float(row["yhat_upper"]) if not pd.isna(row["yhat_upper"]) else occ + 10
            result.append(ForecastPoint(
                date=row["ds"].date(),
                occupancy=round(max(0.0, min(100.0, occ)), 1),
                lower_bound=round(max(0.0, min(100.0, lb)), 1),
                upper_bound=round(max(0.0, min(100.0, ub)), 1),
            ))

        return result

    def _build_holidays(
        self,
        events: list[dict] | None,
        events_data: list[dict] | None,
        history: list[dict] | None = None,
    ) -> pd.DataFrame | None:
        rows = []

        # Russian national holidays from holidays_service
        if history and len(history) > 0:
            try:
                dates = [h["date"] for h in history if h.get("date")]
                if dates:
                    min_d = min(d if isinstance(d, date) else date.fromisoformat(str(d)) for d in dates)
                    max_d = max(d if isinstance(d, date) else date.fromisoformat(str(d)) for d in dates)
                    end_d = max_d + timedelta(days=90)
                    for h in holidays_service.get_holidays_in_range(min_d, end_d):
                        rows.append({
                            "ds": pd.to_datetime(h["date"]),
                            "holiday": h["name"][:30],
                            "lower_window": -2,
                            "upper_window": 2,
                        })
            except Exception as e:
                logger.warning(f"Failed to add national holidays: {e}")

        if events:
            for e in events:
                d = e.get("date")
                n = e.get("name", "event")
                if d:
                    rows.append({"ds": pd.to_datetime(d), "holiday": n,
                                 "lower_window": 0, "upper_window": 0})

        if events_data:
            for e in events_data:
                d = e.get("date_start")
                n = e.get("title", e.get("name", "event"))
                if d:
                    rows.append({"ds": pd.to_datetime(d), "holiday": n[:30],
                                 "lower_window": 0, "upper_window": 0})

        if not rows:
            return None
        return pd.DataFrame(rows).drop_duplicates(subset=["ds"])

    def _add_weather_column(
        self, df: pd.DataFrame, weather_data: dict[date, dict]
    ) -> pd.DataFrame:
        df = df.copy()
        temps = []
        precs = []
        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            w = weather_data.get(d, {})
            temp = w.get("temperature")
            if temp is None:
                temp = AVG_MONTHLY_TEMP_IRKUTSK.get(d.month, 0.0) if hasattr(d, "month") else 0.0
            temps.append(float(temp))
            prec = w.get("precipitation")
            precs.append(float(prec) if prec is not None else 0.0)
        df["temperature"] = temps
        df["precipitation"] = precs
        return df

    async def forecast_occupancy_async(
        self,
        history: list[dict],
        days_ahead: int = 30,
        events: list[dict] | None = None,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
    ) -> list[ForecastPoint]:
        """Async обёртка для forecast_occupancy."""
        return await asyncio.to_thread(
            self.forecast_occupancy,
            history,
            days_ahead,
            events,
            weather_data,
            events_data,
        )


prophet_service = ProphetService()
