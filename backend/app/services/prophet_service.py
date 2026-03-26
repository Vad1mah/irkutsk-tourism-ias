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

        holidays_df = self._build_holidays(events, events_data)
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

        model.fit(df)

        future = model.make_future_dataframe(periods=days_ahead)

        if use_weather:
            future = self._add_weather_column(future, weather_data)

        forecast = model.predict(future)

        result = []
        for _, row in forecast.tail(days_ahead).iterrows():
            result.append(ForecastPoint(
                date=row["ds"].date(),
                occupancy=round(max(0, min(100, row["yhat"])), 1),
                lower_bound=round(max(0, row["yhat_lower"]), 1),
                upper_bound=round(min(100, row["yhat_upper"]), 1),
            ))

        return result

    def _build_holidays(
        self,
        events: list[dict] | None,
        events_data: list[dict] | None,
    ) -> pd.DataFrame | None:
        rows = []
        if events:
            for e in events:
                d = e.get("date")
                n = e.get("name", "event")
                if d:
                    rows.append({"ds": pd.to_datetime(d), "holiday": n})

        if events_data:
            for e in events_data:
                d = e.get("date_start")
                n = e.get("title", e.get("name", "event"))
                if d:
                    rows.append({"ds": pd.to_datetime(d), "holiday": n[:30]})

        if not rows:
            return None
        return pd.DataFrame(rows).drop_duplicates(subset=["ds"])

    def _add_weather_column(
        self, df: pd.DataFrame, weather_data: dict[date, dict]
    ) -> pd.DataFrame:
        df = df.copy()
        temps = []
        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            w = weather_data.get(d, {})
            temp = w.get("temperature")
            if temp is None:
                temp = AVG_MONTHLY_TEMP_IRKUTSK.get(d.month, 0.0) if hasattr(d, "month") else 0.0
            temps.append(float(temp))
        df["temperature"] = temps
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
