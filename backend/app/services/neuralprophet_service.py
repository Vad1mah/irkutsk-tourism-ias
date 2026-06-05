"""NeuralProphet сервис для прогнозирования загрузки отелей.

API usage verified via context7 (/ourownstory/neural_prophet):
- add_lagged_regressor("temperature", n_lags=N) — прошлая погода как фактор прогноза
- add_future_regressor("temperature") — будущая погода (требует заполненных значений)
- create_df_with_events -> merge events в df -> fit -> merge в future -> predict
- n_lags > 0 + n_forecasts > 1 -> yhat1..yhatN для multi-step
- make_future_dataframe -> periods=N, n_historic_predictions -> predict(future)
"""

import asyncio
import logging
import threading
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from neuralprophet import NeuralProphet

from app.constants import AVG_MONTHLY_TEMP_IRKUTSK
from app.models.schemas import ForecastPoint

logger = logging.getLogger(__name__)


class NeuralProphetService:
    """Сервис прогнозирования на NeuralProphet."""

    def __init__(self):
        self._model: NeuralProphet | None = None
        self._metrics: dict | None = None
        self._lock = threading.Lock()  # Thread safety для state mutation

    def forecast_occupancy(
        self,
        history: list[dict],
        days_ahead: int = 14,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        n_lags: int = 14,
    ) -> list[ForecastPoint]:
        """Прогнозирует загрузку с использованием NeuralProphet.

        Args:
            history: [{date, occupancy}, ...]
            days_ahead: горизонт прогноза
            weather_data: {date: {temperature, precipitation}}
            events_data: [{date_start, event_type}, ...]
            n_lags: лаги авторегрессии
        """
        if len(history) < 14:
            logger.warning(f"Недостаточно данных: {len(history)} < 14")
            return self._fallback_forecast(history, days_ahead)

        try:
            df = self._prepare_dataframe(history)
            if len(df) < 14:
                return self._fallback_forecast(history, days_ahead)

            # Phase 8: cap n_forecasts чтобы не получить катастрофический underfit
            # для длинных горизонтов (n_forecasts=365 на 280 точках → 55 train примеров).
            # Для days_ahead > MAX_NP_HORIZON используем cap и далее recursive-extend.
            MAX_NP_HORIZON = 30
            effective_horizon = min(days_ahead, MAX_NP_HORIZON)
            if days_ahead > MAX_NP_HORIZON:
                logger.warning(
                    "NeuralProphet: days_ahead=%d > %d, cap n_forecasts=%d. "
                    "Для длинных горизонтов рекомендуется использовать Prophet или XGBoost.",
                    days_ahead, MAX_NP_HORIZON, MAX_NP_HORIZON,
                )

            effective_lags = max(n_lags, effective_horizon)
            model = NeuralProphet(
                n_forecasts=effective_horizon,
                n_lags=effective_lags,
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                learning_rate=0.01,
                epochs=50,
                batch_size=64,
                drop_missing=True,
                quantiles=[0.1, 0.9],
                trainer_config={
                    "accelerator": "cpu",
                },
            )

            model = model.add_country_holidays(country_name="RU")

            # --- Weather: lagged regressor (context7: прошлые значения, не нужны future) ---
            use_weather = False
            if weather_data:
                df = self._fill_temperature(df, weather_data)
                coverage = (df["temperature"] != 0).mean()
                if coverage > 0.3:
                    model = model.add_lagged_regressor("temperature", n_lags=min(7, effective_lags))
                    use_weather = True
                    logger.info(f"NeuralProphet: temperature lagged regressor ({coverage:.0%} real data)")
                else:
                    df = df.drop(columns=["temperature"], errors="ignore")
                    logger.info("NeuralProphet: мало данных о погоде, temperature не добавлена")

            # --- Events (context7: add_events -> create_df_with_events -> fit) ---
            events_df = None
            if events_data:
                try:
                    events_df = self._create_events_df(events_data)
                    if events_df is not None and not events_df.empty:
                        for event_type in events_df["event"].unique():
                            model = model.add_events(event_type)
                        df = model.create_df_with_events(df, events_df)
                        logger.info(f"NeuralProphet: {events_df['event'].nunique()} event types")
                    else:
                        events_df = None
                except Exception as e:
                    logger.warning(f"NeuralProphet: события пропущены: {e}")
                    events_df = None

            logger.info(f"Обучение NeuralProphet на {len(df)} точках, columns={list(df.columns)}")
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

            def _fit_model():
                return model.fit(df, freq="D", progress=None)

            with ThreadPoolExecutor(max_workers=1) as pool:
                try:
                    future = pool.submit(_fit_model)
                    metrics = future.result(timeout=45)
                except FuturesTimeout:
                    logger.warning("NeuralProphet: таймаут обучения (45s), используем fallback")
                    return self._fallback_forecast(history, days_ahead)

            with self._lock:
                self._metrics = metrics
                self._model = model

            # --- Future dataframe (context7: make_future -> predict(future)) ---
            # periods согласован с n_forecasts (effective_horizon): при days_ahead>30
            # модель физически имеет только step0..step{effective_horizon-1}, поэтому
            # строить future на полный days_ahead бессмысленно — вернётся ≤30 точек,
            # а хвост горизонта в ensemble закрывают Prophet/XGBoost.
            future = model.make_future_dataframe(
                df, periods=effective_horizon, n_historic_predictions=len(df),
            )

            if events_df is not None:
                try:
                    future = model.create_df_with_events(future, events_df)
                except Exception as e:
                    logger.warning(f"Events not added to NeuralProphet forecast: {e}")

            last_history_date = df["ds"].max()
            if hasattr(last_history_date, "date"):
                last_history_date = last_history_date.date()

            _rolling = df["y"].rolling(7, min_periods=1).mean()
            train_residuals = float(np.nanstd(df["y"].values[-30:] - _rolling.values[-30:])) if len(df) > 30 else 10.0

            forecast_raw = model.predict(future, raw=True, decompose=False)
            logger.info(f"NeuralProphet raw shape: {forecast_raw.shape}")
            result = self._extract_forecast_raw(forecast_raw, days_ahead, last_history_date, train_residuals)

            if not result:
                forecast_target = model.predict(future)
                logger.info(f"NeuralProphet target shape: {forecast_target.shape}")
                result = self._extract_forecast(forecast_target, days_ahead, last_history_date, train_residuals)

            logger.info(f"NeuralProphet: извлечено {len(result)} точек прогноза")
            return result

        except Exception as e:
            logger.error(f"Ошибка NeuralProphet: {e}", exc_info=True)
            return self._fallback_forecast(history, days_ahead)

    # ------------------------------------------------------------------
    # Подготовка данных
    # ------------------------------------------------------------------

    def _prepare_dataframe(self, history: list[dict]) -> pd.DataFrame:
        """Создаёт непрерывный ежедневный DataFrame с осторожной интерполяцией.

        Phase 8: вместо unrestricted linear interpolate (которая создавала
        синтетический «плавный» тренд через 4-месячный gap 24.06–25.10.2025
        и стирала летний пик) применяем гибридную стратегию:
          - короткие пропуски (≤ GAP_INTERPOLATE_LIMIT=7 дней) — linear interpolation
          - длинные пропуски (> 7 дней) — оставляем NaN, NeuralProphet с drop_missing=True
            обработает их как настоящие пропуски, а не как синтетический ряд.
        Затем bfill/ffill заполняет границы (хвосты ряда без known точек).
        """
        GAP_INTERPOLATE_LIMIT = 7
        df = pd.DataFrame({
            "ds": pd.to_datetime([h["date"] for h in history]),
            "y": pd.to_numeric([h["occupancy"] for h in history], errors="coerce"),
        })
        df = df.dropna().sort_values("ds").reset_index(drop=True)

        full_range = pd.date_range(df["ds"].min(), df["ds"].max(), freq="D")
        df = df.set_index("ds").reindex(full_range).rename_axis("ds").reset_index()

        # Интерполяция только для коротких пропусков (limit=7)
        y_interp = df["y"].interpolate(method="linear", limit=GAP_INTERPOLATE_LIMIT, limit_area="inside")
        # Длинные пропуски остаются NaN — отбрасываем их явно вместо синтетики
        df["y"] = y_interp

        # Подсчёт пропусков для логирования
        gap_count = int(df["y"].isna().sum())
        if gap_count > 0:
            logger.info(
                f"NeuralProphet: {len(df)} календарных дней, {gap_count} с NaN "
                f"(длинные gap'ы >7 дней оставлены как пропуски — модель их пропустит при drop_missing=True)"
            )
        else:
            logger.info(f"NeuralProphet: {len(df)} непрерывных дней")
        return df

    def _fill_temperature(
        self,
        df: pd.DataFrame,
        weather_data: dict[date, dict],
    ) -> pd.DataFrame:
        """Добавляет/заполняет колонку temperature.

        Для дат без данных использует среднемесячную температуру Иркутска.
        """
        df = df.copy()
        temps = []
        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            weather = weather_data.get(d, {})
            temp = weather.get("temperature")
            if temp is None:
                month = d.month if hasattr(d, "month") else 1
                temp = AVG_MONTHLY_TEMP_IRKUTSK.get(month, 0.0)
            temps.append(float(temp))
        df["temperature"] = temps
        return df

    def _create_events_df(self, events_data: list[dict]) -> pd.DataFrame | None:
        """Создаёт DataFrame событий {event, ds} для NeuralProphet."""
        if not events_data:
            return None

        rows = []
        for evt in events_data:
            d = evt.get("date_start")
            if not d:
                continue
            etype = evt.get("event_type", "general_event") or "general_event"
            if etype == "unknown":
                etype = "general_event"
            etype = etype.replace(" ", "_").replace("-", "_").lower()
            rows.append({"event": etype, "ds": pd.to_datetime(d)})

        return pd.DataFrame(rows) if rows else None

    # ------------------------------------------------------------------
    # Извлечение прогноза
    # ------------------------------------------------------------------

    def _extract_forecast_raw(
        self,
        forecast_raw: pd.DataFrame,
        days_ahead: int,
        origin_override: date | None = None,
        train_residuals: float = 10.0,
    ) -> list[ForecastPoint]:
        """Извлекает прогноз из raw=True predict output.

        raw=True: step<i> = i-step-ahead от ds текущей строки.
        Берём последнюю строку с данными (origin = последний день истории).
        """
        result = []
        cols = list(forecast_raw.columns)
        step_cols = sorted(
            [c for c in cols if c.startswith("step") and c[4:].isdigit()],
            key=lambda c: int(c[4:]),
        )

        if not step_cols:
            return result

        has_y = forecast_raw[forecast_raw["y"].notna()] if "y" in cols else forecast_raw
        if has_y.empty:
            has_y = forecast_raw

        source_row = has_y.iloc[-1]
        origin_date = origin_override
        if origin_date is None:
            origin_date = source_row["ds"]
            if hasattr(origin_date, "date"):
                origin_date = origin_date.date()

        for i, col in enumerate(step_cols[:days_ahead]):
            val = source_row.get(col)
            if val is None or pd.isna(val):
                next_vals = [
                    source_row.get(step_cols[j])
                    for j in range(i + 1, min(i + 3, len(step_cols)))
                    if source_row.get(step_cols[j]) is not None
                    and not pd.isna(source_row.get(step_cols[j]))
                ]
                if next_vals:
                    val = next_vals[0]
                else:
                    continue

            forecast_date = origin_date + timedelta(days=i + 1)
            occupancy = max(0.0, min(100.0, float(val)))

            ci = 1.28 * max(train_residuals, 3.0) * (1 + 0.15 * (i ** 0.5))
            result.append(ForecastPoint(
                date=forecast_date.strftime("%Y-%m-%d"),
                occupancy=round(occupancy, 1),
                lower_bound=round(max(0.0, occupancy - ci), 1),
                upper_bound=round(min(100.0, occupancy + ci), 1),
            ))

        return result

    def _extract_forecast(
        self,
        forecast: pd.DataFrame,
        days_ahead: int,
        origin_override: date | None = None,
        train_residuals: float = 10.0,
    ) -> list[ForecastPoint]:
        """Извлекает прогноз из target-mode predict(future).

        target-mode: yhat<i> = i-step-ahead prediction targeting ds строки.
        Для out-of-sample (y=NaN) yhat1 = одношаговый прогноз целевой даты.
        Если y=NaN строк нет — fallback на multi-step из последней строки с данными.
        """
        result = []
        cols = list(forecast.columns)
        yhat_cols = sorted(
            [c for c in cols if c.startswith("yhat") and c[4:].isdigit()],
            key=lambda c: int(c[4:]),
        )

        if not yhat_cols:
            return self._extract_fallback_rows(forecast, days_ahead, train_residuals)

        # Out-of-sample строки (будущие даты, y=NaN)
        future_rows = forecast[forecast["y"].isna()]
        if not future_rows.empty and "yhat1" in cols:
            for _, row in future_rows.head(days_ahead).iterrows():
                yhat = row.get("yhat1")
                if yhat is None or pd.isna(yhat):
                    continue
                ds = row["ds"]
                date_str = ds.strftime("%Y-%m-%d") if hasattr(ds, "strftime") else str(ds)[:10]
                occupancy = max(0.0, min(100.0, float(yhat)))

                lower_col = "yhat1 10.0%"
                upper_col = "yhat1 90.0%"
                fallback_ci = 1.28 * max(train_residuals, 3.0) * (1 + 0.15 * (len(result) ** 0.5))
                lower = float(row[lower_col]) if lower_col in cols and not pd.isna(row.get(lower_col)) else occupancy - fallback_ci
                upper = float(row[upper_col]) if upper_col in cols and not pd.isna(row.get(upper_col)) else occupancy + fallback_ci

                result.append(ForecastPoint(
                    date=date_str,
                    occupancy=round(occupancy, 1),
                    lower_bound=round(max(0.0, lower), 1),
                    upper_bound=round(min(100.0, upper), 1),
                ))
            if result:
                return result

        has_y = forecast[forecast["y"].notna()]
        if has_y.empty:
            return result

        last_data_date = origin_override
        if last_data_date is None:
            last_data_date = has_y["ds"].max()
            if hasattr(last_data_date, "date"):
                last_data_date = last_data_date.date()

        source_row = None
        for idx in range(len(has_y) - 1, -1, -1):
            row = has_y.iloc[idx]
            if not pd.isna(row.get("yhat1", float("nan"))):
                source_row = row
                break

        if source_row is None:
            return result

        for i, col in enumerate(yhat_cols[:days_ahead]):
            yhat = source_row.get(col)
            if yhat is None or pd.isna(yhat):
                continue

            forecast_date = last_data_date + timedelta(days=i + 1)
            occupancy = max(0.0, min(100.0, float(yhat)))

            lower_col = f"{col} 10.0%"
            upper_col = f"{col} 90.0%"
            fallback_ci = 1.28 * max(train_residuals, 3.0) * (1 + 0.15 * (i ** 0.5))
            lower = float(source_row[lower_col]) if lower_col in cols and not pd.isna(source_row.get(lower_col)) else occupancy - fallback_ci
            upper = float(source_row[upper_col]) if upper_col in cols and not pd.isna(source_row.get(upper_col)) else occupancy + fallback_ci

            result.append(ForecastPoint(
                date=forecast_date.strftime("%Y-%m-%d"),
                occupancy=round(occupancy, 1),
                lower_bound=round(max(0.0, lower), 1),
                upper_bound=round(min(100.0, upper), 1),
            ))

        return result

    def _extract_fallback_rows(
        self,
        forecast: pd.DataFrame,
        days_ahead: int,
        train_residuals: float = 10.0,
    ) -> list[ForecastPoint]:
        """Fallback: извлечение из строк с y=NaN (без n_lags)."""
        result = []
        future_rows = forecast[forecast["y"].isna()]
        if future_rows.empty:
            future_rows = forecast.tail(days_ahead)
        for _, row in future_rows.iterrows():
            yhat = row.get("yhat1", row.get("yhat"))
            if yhat is None or pd.isna(yhat):
                continue
            ds = row["ds"]
            date_str = ds.strftime("%Y-%m-%d") if hasattr(ds, "strftime") else str(ds)[:10]
            occupancy = max(0.0, min(100.0, float(yhat)))
            ci = 1.28 * max(train_residuals, 3.0) * (1 + 0.15 * (len(result) ** 0.5))
            result.append(ForecastPoint(
                date=date_str,
                occupancy=round(occupancy, 1),
                lower_bound=round(max(0.0, occupancy - ci), 1),
                upper_bound=round(min(100.0, occupancy + ci), 1),
            ))
        return result

    # ------------------------------------------------------------------
    # Fallback прогноз
    # ------------------------------------------------------------------

    def _fallback_forecast(
        self,
        history: list[dict],
        days_ahead: int,
    ) -> list[ForecastPoint]:
        """Простой прогноз на среднем при ошибке модели."""
        logger.warning("NeuralProphet using fallback linear extrapolation")
        base = sum(h["occupancy"] for h in history) / len(history) if history else 45.0

        last_date = date.today()
        if history:
            last_str = history[-1]["date"]
            if isinstance(last_str, str):
                last_date = pd.to_datetime(last_str).date()

        result = []
        for i in range(1, days_ahead + 1):
            d = last_date + timedelta(days=i)
            occ = max(0.0, min(100.0, base + (i % 7 - 3) * 2))
            result.append(ForecastPoint(
                date=d.strftime("%Y-%m-%d"),
                occupancy=round(occ, 1),
                lower_bound=round(max(0.0, occ - 15), 1),
                upper_bound=round(min(100.0, occ + 15), 1),
            ))
        return result

    def get_components(self) -> dict[str, Any] | None:
        """Компоненты модели для визуализации."""
        if self._model is None:
            return None
        return {"has_model": True, "metrics": self._metrics}

    async def forecast_occupancy_async(
        self,
        history: list[dict],
        days_ahead: int = 30,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        **kwargs,
    ) -> list[ForecastPoint]:
        """Async обёртка для forecast_occupancy."""
        return await asyncio.to_thread(
            self.forecast_occupancy,
            history,
            days_ahead,
            weather_data,
            events_data,
        )


neuralprophet_service = NeuralProphetService()
