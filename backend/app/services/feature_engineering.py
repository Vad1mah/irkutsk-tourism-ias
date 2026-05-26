"""Feature Engineering для ML прогнозирования загрузки отелей.

Фичи: календарные, праздничные, лаговые, скользящие, погодные, событийные, трендовые.
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
import logging

from app.constants import (
    SEASON_MONTHS,
    AVG_MONTHLY_TEMP_IRKUTSK,
    WARM_TEMP_THRESHOLD,
    LOW_PRECIPITATION_THRESHOLD,
    HOLIDAY_SEARCH_RANGE_DAYS,
    EVENT_SEARCH_RANGE_DAYS,
    MAJOR_EVENT_TYPES,
    LAG_DAYS,
    DIFF_DAYS,
    ROLLING_WINDOWS,
)
from app.services.holidays_service import holidays_service

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """Feature Engineering: 25+ фичей для прогнозирования."""

    def __init__(self):
        self._feature_names: list[str] = []

    def create_features(
        self,
        history: list[dict],
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        target_dates: list[date] | None = None,
        include_lags: bool = True,
        price_data: list[dict] | None = None,
    ) -> pd.DataFrame:
        """Создаёт полный набор фичей."""
        df = pd.DataFrame(history)
        df = df.rename(columns={"date": "ds", "occupancy": "y"})
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").reset_index(drop=True)

        if target_dates:
            existing_dates = set(df["ds"].dt.date)
            future_rows = []
            for d in target_dates:
                d_date = d if isinstance(d, date) else pd.Timestamp(d).date()
                if d_date not in existing_dates:
                    future_rows.append({"ds": pd.Timestamp(d_date), "y": np.nan})
            if future_rows:
                df = pd.concat([df, pd.DataFrame(future_rows)], ignore_index=True)
                df = df.sort_values("ds").reset_index(drop=True)

        df = self._add_calendar_features(df)
        df = self._add_holiday_features(df)

        if include_lags:
            df = self._add_lag_features(df)

        df = self._add_rolling_features(df)

        df = self._add_weather_features(df, weather_data or {})
        df = self._add_event_features(df, events_data or [])

        df = self._add_trend_features(df)

        # Добавляем фичи цен
        df = self._add_price_features(df, price_data)

        self._feature_names = [c for c in df.columns if c not in ("ds", "y")]
        logger.info(f"Создано {len(self._feature_names)} фичей")
        return df

    def get_feature_names(self) -> list[str]:
        return self._feature_names.copy()

    # ------------------------------------------------------------------
    # Calendar (8 features)
    # ------------------------------------------------------------------

    def _add_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["day_of_week"] = df["ds"].dt.dayofweek
        df["day_of_month"] = df["ds"].dt.day
        df["month"] = df["ds"].dt.month
        df["quarter"] = df["ds"].dt.quarter
        df["week_of_year"] = df["ds"].dt.isocalendar().week.astype(int)
        df["is_weekend"] = (df["ds"].dt.dayofweek >= 5).astype(int)
        df["is_month_start"] = df["ds"].dt.is_month_start.astype(int)
        df["is_month_end"] = df["ds"].dt.is_month_end.astype(int)
        return df

    # ------------------------------------------------------------------
    # Holidays (5 features)
    # ------------------------------------------------------------------

    def _add_holiday_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        is_hol_list = []
        days_to_list = []
        days_from_list = []
        # Phase 8: Байкало-специфичные сезонные признаки
        is_ice_list = []
        is_rasputitsa_list = []
        is_sagaalgan_list = []
        is_baikal_day_list = []

        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            is_hol = 1 if holidays_service.is_holiday(d) else 0
            days_to = holidays_service.days_to_nearest_holiday(d, max_days=HOLIDAY_SEARCH_RANGE_DAYS)

            # Дней после ближайшего прошлого праздника
            days_from = HOLIDAY_SEARCH_RANGE_DAYS
            for back in range(1, HOLIDAY_SEARCH_RANGE_DAYS + 1):
                check = d - timedelta(days=back)
                if holidays_service.is_holiday(check):
                    days_from = back
                    break

            is_hol_list.append(is_hol)
            days_to_list.append(days_to)
            days_from_list.append(days_from)
            is_ice_list.append(1 if holidays_service.is_ice_season(d) else 0)
            is_rasputitsa_list.append(1 if holidays_service.is_rasputitsa(d) else 0)
            is_sagaalgan_list.append(1 if holidays_service.is_sagaalgan(d) else 0)
            is_baikal_day_list.append(1 if holidays_service.is_baikal_day(d) else 0)

        df["is_holiday"] = is_hol_list
        df["days_to_holiday"] = days_to_list
        df["days_from_holiday"] = days_from_list
        df["is_ice_season"] = is_ice_list
        df["is_rasputitsa"] = is_rasputitsa_list
        df["is_sagaalgan"] = is_sagaalgan_list
        df["is_baikal_day"] = is_baikal_day_list

        df["is_long_weekend"] = (
            (df["is_weekend"] == 1)
            | ((df["day_of_week"].isin([0, 4])) & (df["days_to_holiday"] <= 1))
        ).astype(int)

        def _season(month: int) -> int:
            if month in SEASON_MONTHS["winter"]:
                return 1
            if month in SEASON_MONTHS["spring"]:
                return 2
            if month in SEASON_MONTHS["summer"]:
                return 3
            return 4

        df["season"] = df["month"].apply(_season)
        return df

    # ------------------------------------------------------------------
    # Lags (dynamic: skip lags > data length)
    # ------------------------------------------------------------------

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        data_len = df["y"].notna().sum()

        for lag in LAG_DAYS:
            if lag < data_len:
                df[f"lag_{lag}"] = df["y"].shift(lag)
            else:
                logger.debug(f"Skipping lag_{lag}: only {data_len} data points")

        # shift(1) prevents target leakage: diff uses y[i-1] - y[i-1-d], not y[i]
        y_shifted = df["y"].shift(1)
        for d in DIFF_DAYS:
            df[f"diff_{d}"] = y_shifted.diff(d)

        return df

    # ------------------------------------------------------------------
    # Rolling stats (5 features)
    # ------------------------------------------------------------------

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        w_short = ROLLING_WINDOWS[0]  # 7
        w_long = ROLLING_WINDOWS[1] if len(ROLLING_WINDOWS) > 1 else 30

        # shift(1) prevents target leakage: rolling stats exclude current y[i]
        y_past = df["y"].shift(1)
        df[f"rolling_mean_{w_short}"] = y_past.rolling(w_short, min_periods=1).mean()
        df[f"rolling_mean_{w_long}"] = y_past.rolling(w_long, min_periods=1).mean()
        df[f"rolling_std_{w_short}"] = y_past.rolling(w_short, min_periods=2).std().bfill().fillna(0)
        df[f"rolling_min_{w_short}"] = y_past.rolling(w_short, min_periods=1).min()
        df[f"rolling_max_{w_short}"] = y_past.rolling(w_short, min_periods=1).max()
        return df

    # ------------------------------------------------------------------
    # Weather (4 features) — monthly avg fallback
    # ------------------------------------------------------------------

    def _add_weather_features(
        self,
        df: pd.DataFrame,
        weather_data: dict[date, dict],
    ) -> pd.DataFrame:
        df = df.copy()

        temps = []
        precips = []
        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            weather = weather_data.get(d, {})
            temp = weather.get("temperature")
            if temp is None:
                month = d.month if hasattr(d, "month") else 1
                temp = AVG_MONTHLY_TEMP_IRKUTSK.get(month, 0.0)
            precip = weather.get("precipitation", 0.0)
            temps.append(float(temp))
            precips.append(float(precip))

        df["temperature"] = temps
        df["precipitation"] = precips

        df["temp_deviation"] = df.apply(
            lambda row: row["temperature"] - AVG_MONTHLY_TEMP_IRKUTSK.get(int(row["month"]), 0),
            axis=1,
        )

        df["is_good_weather"] = (
            (df["temperature"] > WARM_TEMP_THRESHOLD)
            & (df["precipitation"] < LOW_PRECIPITATION_THRESHOLD)
        ).astype(int)

        return df

    # ------------------------------------------------------------------
    # Events (3 features)
    # ------------------------------------------------------------------

    def _add_event_features(
        self,
        df: pd.DataFrame,
        events_data: list[dict],
    ) -> pd.DataFrame:
        df = df.copy()

        events_by_date: dict[date, list[dict]] = {}
        for event in events_data:
            ed = event.get("date_start")
            if ed:
                if isinstance(ed, str):
                    ed = pd.to_datetime(ed).date()
                elif hasattr(ed, "date"):
                    ed = ed.date()
                events_by_date.setdefault(ed, []).append(event)

        counts, weeks, majors = [], [], []
        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            day_events = events_by_date.get(d, [])
            counts.append(len(day_events))

            wk = 0
            for i in range(EVENT_SEARCH_RANGE_DAYS[0], EVENT_SEARCH_RANGE_DAYS[1] + 1):
                wk += len(events_by_date.get(d + timedelta(days=i), []))
            weeks.append(wk)

            has_major = 0
            for evt in day_events:
                et = (evt.get("event_type") or "").lower()
                if any(t in et for t in MAJOR_EVENT_TYPES):
                    has_major = 1
                    break
            majors.append(has_major)

        df["events_count"] = counts
        df["events_week"] = weeks
        df["has_major_event"] = majors
        return df

    # ------------------------------------------------------------------
    # Trend (2 features)
    # ------------------------------------------------------------------

    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["time_index"] = range(len(df))
        df["trend"] = df["time_index"] / max(len(df), 1)
        return df

    # ------------------------------------------------------------------
    # Price features (4 features) — динамика цен
    # ------------------------------------------------------------------

    def _add_price_features(
        self,
        df: pd.DataFrame,
        price_data: list[dict] | None = None,
    ) -> pd.DataFrame:
        """
        Добавить фичи на основе цен.

        Args:
            df: DataFrame с колонкой 'ds'
            price_data: Список {'date': date, 'price': float}

        Добавляет:
            - price: Цена на дату
            - price_lag_7: Цена 7 дней назад
            - price_trend_7: Изменение цены за 7 дней (%)
            - price_rolling_mean_7: Скользящая средняя цены
        """
        df = df.copy()

        if not price_data:
            df["price"] = np.nan
            df["price_lag_7"] = np.nan
            df["price_trend_7"] = np.nan
            df["price_rolling_mean_7"] = np.nan
            return df

        # Создаём словарь цен по датам
        price_map = {}
        for row in price_data:
            d = row.get("date")
            p = row.get("price") or row.get("min_price") or row.get("avg_price")
            if d and p:
                if hasattr(d, "date"):
                    d = d.date()
                price_map[d] = float(p)

        # Заполняем цены
        prices = []
        for ds in df["ds"]:
            d = ds.date() if hasattr(ds, "date") else ds
            prices.append(price_map.get(d, 0))

        df["price"] = prices

        # Если нет цен — возвращаем нули
        if not any(prices):
            df["price_lag_7"] = 0
            df["price_trend_7"] = 0
            df["price_rolling_mean_7"] = 0
            return df

        # Lag цены
        df["price_lag_7"] = df["price"].shift(7).fillna(0)

        # Тренд цены (процентное изменение за 7 дней)
        df["price_trend_7"] = df["price"].pct_change(7).fillna(0) * 100

        # Скользящая средняя цены
        df["price_rolling_mean_7"] = df["price"].rolling(7, min_periods=1).mean().fillna(0)

        return df

    # ------------------------------------------------------------------
    # Train / Test / Future
    # ------------------------------------------------------------------

    def prepare_train_test(
        self,
        df: pd.DataFrame,
        test_days: int = 14,
    ) -> tuple:
        """Разделяет на train/test по времени без data leakage.

        Lag/rolling/diff фичи для test пересчитываются так, чтобы
        не использовать будущие (тестовые) значения y.
        """
        df_valid = df.dropna(subset=["y"]).copy()
        feature_cols = [c for c in df.columns if c not in ("ds", "y")]
        leaked_cols = [c for c in feature_cols if c.startswith(("lag_", "rolling_", "diff_"))]

        split_idx = len(df_valid) - test_days
        train_df = df_valid.iloc[:split_idx].copy()
        test_df = df_valid.iloc[split_idx:].copy()

        if leaked_cols and len(train_df) > 0:
            for i in range(len(test_df)):
                row_idx = test_df.index[i]
                for col in leaked_cols:
                    if col.startswith("lag_"):
                        lag_n = int(col.rsplit("_", 1)[1])
                        src = split_idx + i - lag_n
                        if src >= split_idx:
                            test_df.loc[row_idx, col] = train_df["y"].iloc[-1]
                    elif col.startswith("diff_"):
                        test_df.loc[row_idx, col] = 0.0
                    elif col.startswith("rolling_"):
                        test_df.loc[row_idx, col] = train_df[col].iloc[-1]

        price_cols = {"price", "price_lag_7", "price_trend_7", "price_rolling_mean_7"}
        for col in feature_cols:
            if col in price_cols:
                continue
            train_df[col] = train_df[col].ffill().bfill().fillna(0)
            test_df[col] = test_df[col].ffill().bfill().fillna(0)

        X_train = train_df[feature_cols].values
        y_train = train_df["y"].values
        X_test = test_df[feature_cols].values
        y_test = test_df["y"].values
        test_dates = test_df["ds"].dt.date.tolist()

        return X_train, y_train, X_test, y_test, test_dates

    def prepare_future(
        self,
        df: pd.DataFrame,
        future_dates: list[date],
    ) -> tuple:
        """Подготавливает фичи для будущих дат."""
        feature_cols = [c for c in df.columns if c not in ("ds", "y")]
        future_set = {d if isinstance(d, date) else pd.Timestamp(d).date() for d in future_dates}
        future_df = df[df["ds"].dt.date.isin(future_set)].copy()

        if future_df.empty:
            nan_rows = df[df["y"].isna()]
            if not nan_rows.empty:
                future_df = nan_rows.tail(len(future_dates)).copy()

        price_cols = {"price", "price_lag_7", "price_trend_7", "price_rolling_mean_7"}
        for col in feature_cols:
            if col in price_cols:
                continue
            future_df[col] = future_df[col].ffill().bfill().fillna(0)

        X = future_df[feature_cols].values
        dates = future_df["ds"].dt.date.tolist()
        return X, dates


feature_engineering_service = FeatureEngineeringService()
