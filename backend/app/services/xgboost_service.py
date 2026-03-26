"""Сервис прогнозирования на основе XGBoost/LightGBM.

Confidence intervals: XGBoost quantile regression (reg:quantileerror)
  per context7 /dmlc/xgboost — quantile_alpha=[0.1, 0.9], tree_method=hist.
"""
import asyncio
import hashlib
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta
import logging
import pickle
import threading
from pathlib import Path

from app.models.schemas import ForecastPoint
from app.services.feature_engineering import feature_engineering_service

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost не установлен")

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("LightGBM не установлен")


class XGBoostService:
    """Прогнозирование загрузки на XGBoost + LightGBM."""

    def __init__(self):
        self._xgb_model = None
        self._lgb_model = None
        self._quantile_booster = None  # low-level xgb for quantile CI
        self._feature_names: list[str] = []
        self._is_trained: bool = False
        self._data_hash: str = ""
        self._metrics: dict[str, float] = {}
        self._model_dir = Path("models")
        self._model_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()  # Thread safety для train/predict
        self._try_load_cached()

    def _try_load_cached(self):
        if self.load_models():
            logger.info("XGBoost/LightGBM: загружены кэшированные модели")

    def _compute_data_hash(self, history: list[dict]) -> str:
        key = json.dumps(
            {
                "len": len(history),
                "first_3": history[:3] if len(history) >= 3 else history,
                "last_5": history[-5:] if len(history) >= 5 else history,
            },
            default=str, sort_keys=True,
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _needs_retrain(self, history: list[dict]) -> bool:
        new_hash = self._compute_data_hash(history)
        return new_hash != self._data_hash or not self._is_trained

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        history: list[dict],
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        test_size: int = 14,
    ) -> dict[str, float]:
        """Обучает XGBoost (mean + quantile), LightGBM."""
        with self._lock:  # Thread safety для concurrent training
            return self._train_impl(history, weather_data, events_data, test_size)

    def _train_impl(
        self,
        history: list[dict],
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        test_size: int = 14,
    ) -> dict[str, float]:
        """Internal training implementation (requires lock held)."""
        logger.info(f"Обучение XGBoost/LightGBM на {len(history)} записях...")

        df = feature_engineering_service.create_features(
            history=history,
            weather_data=weather_data,
            events_data=events_data,
            include_lags=True,
        )

        X_train, y_train, X_test, y_test, test_dates = \
            feature_engineering_service.prepare_train_test(df, test_days=test_size)

        self._feature_names = feature_engineering_service.get_feature_names()
        logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}, Features: {len(self._feature_names)}")

        metrics = {}

        # --- XGBoost (point prediction, squared error) ---
        if XGBOOST_AVAILABLE:
            self._xgb_model = xgb.XGBRegressor(
                n_estimators=300,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=5,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                early_stopping_rounds=20,
            )
            self._xgb_model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False,
            )

            xgb_pred = self._xgb_model.predict(X_test)
            metrics["xgb_rmse"] = float(np.sqrt(np.mean((xgb_pred - y_test) ** 2)))
            metrics["xgb_mae"] = float(np.mean(np.abs(xgb_pred - y_test)))
            ss_res = np.sum((y_test - xgb_pred) ** 2)
            ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
            metrics["xgb_r2"] = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
            logger.info(
                f"XGBoost RMSE: {metrics['xgb_rmse']:.2f}, "
                f"MAE: {metrics['xgb_mae']:.2f}, R2: {metrics['xgb_r2']:.3f}"
            )

            # --- XGBoost quantile model for CI (context7: reg:quantileerror) ---
            try:
                self._train_quantile_model(X_train, y_train, X_test, y_test)
            except Exception as e:
                logger.warning(f"Quantile model failed: {e}")
                self._quantile_booster = None

        # --- LightGBM ---
        if LIGHTGBM_AVAILABLE:
            self._lgb_model = lgb.LGBMRegressor(
                n_estimators=300,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_samples=10,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
            self._lgb_model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
            )

            lgb_pred = self._lgb_model.predict(X_test)
            metrics["lgb_rmse"] = float(np.sqrt(np.mean((lgb_pred - y_test) ** 2)))
            metrics["lgb_mae"] = float(np.mean(np.abs(lgb_pred - y_test)))
            logger.info(f"LightGBM RMSE: {metrics['lgb_rmse']:.2f}, MAE: {metrics['lgb_mae']:.2f}")

        # Ensemble
        if XGBOOST_AVAILABLE and LIGHTGBM_AVAILABLE:
            ens = (xgb_pred + lgb_pred) / 2
            metrics["ensemble_rmse"] = float(np.sqrt(np.mean((ens - y_test) ** 2)))
            metrics["ensemble_mae"] = float(np.mean(np.abs(ens - y_test)))

        self._is_trained = True
        self._data_hash = self._compute_data_hash(history)
        self._metrics = metrics
        self.save_models()
        return metrics

    def _train_quantile_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> None:
        """Обучает quantile XGBoost для CI (context7: QuantileDMatrix + reg:quantileerror)."""
        alpha = np.array([0.1, 0.9])
        Xy = xgb.QuantileDMatrix(X_train, y_train)
        Xy_test = xgb.QuantileDMatrix(X_test, y_test, ref=Xy)

        self._quantile_booster = xgb.train(
            {
                "objective": "reg:quantileerror",
                "tree_method": "hist",
                "quantile_alpha": alpha,
                "learning_rate": 0.05,
                "max_depth": 5,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_weight": 5,
            },
            Xy,
            num_boost_round=300,
            early_stopping_rounds=20,
            evals=[(Xy, "Train"), (Xy_test, "Test")],
            verbose_eval=False,
        )
        logger.info("XGBoost quantile model trained (alpha=[0.1, 0.9])")

    # ------------------------------------------------------------------
    # Forecasting
    # ------------------------------------------------------------------

    def forecast_occupancy(
        self,
        history: list[dict],
        days_ahead: int = 14,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        model: str = "ensemble",
    ) -> list[ForecastPoint]:
        """Прогноз с quantile-based confidence intervals."""
        if self._needs_retrain(history):
            self.train(history, weather_data, events_data)
        else:
            logger.info("XGBoost: используются кэшированные модели")

        last_date = max(h["date"] for h in history)
        if isinstance(last_date, str):
            last_date = pd.to_datetime(last_date).date()

        future_dates = [last_date + timedelta(days=i + 1) for i in range(days_ahead)]

        df = feature_engineering_service.create_features(
            history=history,
            weather_data=weather_data,
            events_data=events_data,
            target_dates=future_dates,
            include_lags=True,
        )

        X_future, dates = feature_engineering_service.prepare_future(df, future_dates)
        if len(X_future) == 0:
            logger.warning("Нет данных для прогноза")
            return []

        predictions = self._predict(X_future, model)

        # Quantile CI
        lower_bounds, upper_bounds = self._predict_quantiles(X_future)

        result = []
        for i, (d, pred) in enumerate(zip(dates, predictions)):
            occ = max(0.0, min(100.0, float(pred)))
            lb = lower_bounds[i] if i < len(lower_bounds) else occ - 8
            ub = upper_bounds[i] if i < len(upper_bounds) else occ + 8

            result.append(ForecastPoint(
                date=d,
                occupancy=round(occ, 1),
                lower_bound=round(max(0.0, lb), 1),
                upper_bound=round(min(100.0, ub), 1),
            ))

        return result

    def _predict(self, X: np.ndarray, model: str = "ensemble") -> np.ndarray:
        if model == "xgboost" and self._xgb_model:
            return self._xgb_model.predict(X)
        if model == "lightgbm" and self._lgb_model:
            return self._lgb_model.predict(X)
        if self._xgb_model and self._lgb_model:
            return (self._xgb_model.predict(X) + self._lgb_model.predict(X)) / 2
        if self._xgb_model:
            return self._xgb_model.predict(X)
        if self._lgb_model:
            return self._lgb_model.predict(X)
        raise ValueError("Нет обученных моделей")

    def _predict_quantiles(self, X: np.ndarray) -> tuple:
        """Предсказывает CI через quantile booster (context7)."""
        if self._quantile_booster is not None:
            try:
                scores = self._quantile_booster.inplace_predict(X)
                if scores.ndim == 2 and scores.shape[1] >= 2:
                    return scores[:, 0].tolist(), scores[:, 1].tolist()
            except Exception as e:
                logger.warning(f"Quantile predict error: {e}")

        # Fallback: residual-based CI
        pred = self._predict(X)
        if self._metrics:
            rmse = self._metrics.get("xgb_rmse", self._metrics.get("lgb_rmse", 8.0))
        else:
            rmse = 8.0
        lower = (pred - 1.28 * rmse).tolist()
        upper = (pred + 1.28 * rmse).tolist()
        return lower, upper

    # ------------------------------------------------------------------
    # Feature importance
    # ------------------------------------------------------------------

    def get_feature_importance(self) -> dict[str, dict[str, float]]:
        importance = {}
        if self._xgb_model and self._feature_names:
            imp = self._xgb_model.feature_importances_
            importance["xgboost"] = dict(
                sorted(
                    {n: float(v) for n, v in zip(self._feature_names, imp)}.items(),
                    key=lambda x: x[1], reverse=True,
                )
            )
        if self._lgb_model and self._feature_names:
            imp = self._lgb_model.feature_importances_
            importance["lightgbm"] = dict(
                sorted(
                    {n: float(v) for n, v in zip(self._feature_names, imp)}.items(),
                    key=lambda x: x[1], reverse=True,
                )
            )
        return importance

    def get_metrics(self) -> dict[str, float]:
        return self._metrics.copy()

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save_models(self, prefix: str = "forecast") -> list[str]:
        saved = []
        if self._xgb_model:
            path = self._model_dir / f"{prefix}_xgboost.json"
            self._xgb_model.save_model(str(path))
            saved.append(str(path))

        if self._quantile_booster:
            path = self._model_dir / f"{prefix}_xgb_quantile.json"
            self._quantile_booster.save_model(str(path))
            saved.append(str(path))

        # Сохраняем LightGBM в JSON (безопаснее pickle)
        if self._lgb_model:
            path = self._model_dir / f"{prefix}_lightgbm.json"
            try:
                self._lgb_model.booster_.save_model(str(path))
                saved.append(str(path))
            except Exception:
                # Fallback: pickle если JSON не доступен
                path = self._model_dir / f"{prefix}_lightgbm.pkl"
                with open(path, "wb") as f:
                    pickle.dump(self._lgb_model, f)
                saved.append(str(path))

        # Сохраняем features в JSON (безопаснее pickle)
        if self._feature_names:
            path = self._model_dir / f"{prefix}_features.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._feature_names, f)
            saved.append(str(path))

        meta_path = self._model_dir / f"{prefix}_meta.json"
        with open(meta_path, "w") as f:
            json.dump({"data_hash": self._data_hash, "metrics": self._metrics}, f)

        logger.info(f"Модели сохранены: {saved}")
        return saved

    def load_models(self, prefix: str = "forecast") -> bool:
        try:
            xgb_path = self._model_dir / f"{prefix}_xgboost.json"
            if xgb_path.exists() and XGBOOST_AVAILABLE:
                self._xgb_model = xgb.XGBRegressor()
                self._xgb_model.load_model(str(xgb_path))

            q_path = self._model_dir / f"{prefix}_xgb_quantile.json"
            if q_path.exists() and XGBOOST_AVAILABLE:
                self._quantile_booster = xgb.Booster()
                self._quantile_booster.load_model(str(q_path))

            # Безопасная загрузка LightGBM через JSON вместо pickle
            lgb_json_path = self._model_dir / f"{prefix}_lightgbm.json"
            if lgb_json_path.exists() and LIGHTGBM_AVAILABLE:
                self._lgb_model = lgb.LGBMRegressor()
                self._lgb_model.booster_ = lgb.Booster(model_file=str(lgb_json_path))
            else:
                # Fallback: pickle с предупреждением
                lgb_path = self._model_dir / f"{prefix}_lightgbm.pkl"
                if lgb_path.exists() and LIGHTGBM_AVAILABLE:
                    logger.warning(
                        "Loading LightGBM from pickle. Consider re-saving models to JSON format. "
                        f"Path: {lgb_path}"
                    )
                    with open(lgb_path, "rb") as f:
                        self._lgb_model = pickle.load(f)

            # Безопасная загрузка feature_names через JSON вместо pickle
            feat_json_path = self._model_dir / f"{prefix}_features.json"
            if feat_json_path.exists():
                with open(feat_json_path, encoding="utf-8") as f:
                    self._feature_names = json.load(f)
            else:
                # Fallback: pickle с предупреждением
                feat_path = self._model_dir / f"{prefix}_features.pkl"
                if feat_path.exists():
                    logger.warning(
                        "Loading features from pickle. Consider re-saving to JSON format. "
                        f"Path: {feat_path}"
                    )
                    with open(feat_path, "rb") as f:
                        self._feature_names = pickle.load(f)

            meta_path = self._model_dir / f"{prefix}_meta.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                self._data_hash = meta.get("data_hash", "")
                self._metrics = meta.get("metrics", {})

            self._is_trained = bool(self._xgb_model or self._lgb_model)
            return self._is_trained
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
            return False

    async def forecast_occupancy_async(
        self,
        history: list[dict],
        days_ahead: int = 30,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
    ) -> list[ForecastPoint]:
        """Async обёртка для forecast_occupancy."""
        return await asyncio.to_thread(
            self.forecast_occupancy,
            history,
            days_ahead,
            weather_data,
            events_data,
        )


xgboost_service = XGBoostService()
