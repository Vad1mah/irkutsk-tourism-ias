"""Ensemble сервис — объединение Prophet + NeuralProphet + XGBoost.

Оптимизация (2026-02-28):
- Параллельный запуск моделей через asyncio.gather
- Кэширование на уровне Redis (endpoint /ensemble)
- Graceful fallback при ошибках
"""
import asyncio
import time
from collections import defaultdict
import numpy as np
from datetime import date
import logging
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from app.models.schemas import ForecastPoint
from app.services.prophet_service import prophet_service
from app.services.neuralprophet_service import neuralprophet_service
from app.services.xgboost_service import xgboost_service

logger = logging.getLogger(__name__)

CALIBRATION_TTL = 3600


class EnsembleService:
    """Ensemble из трёх моделей с адаптивными весами."""

    def __init__(self):
        self._weights: dict[str, float] = {
            "prophet": 0.34,
            "neuralprophet": 0.33,
            "xgboost": 0.33,
        }
        self._last_metrics: dict = {}
        self._calibrated_at: float = 0.0
        self._calibrating: bool = False

    async def forecast_ensemble_async(
        self,
        history: list[dict],
        days_ahead: int = 14,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        method: str = "weighted_average",
        district: str = "",
    ) -> dict:
        """Ensemble прогноз с параллельным запуском моделей."""
        results: dict = {
            "models": {},
            "ensemble": [],
            "weights": self._weights.copy(),
            "method": method,
        }

        # Параллельный запуск всех моделей через asyncio.gather
        async def run_prophet():
            try:
                return await prophet_service.forecast_occupancy_async(
                    history=history, days_ahead=days_ahead,
                    weather_data=weather_data, events_data=events_data,
                )
            except Exception as e:
                logger.error(f"Prophet error: {e}")
                return []

        async def run_neuralprophet():
            try:
                return await neuralprophet_service.forecast_occupancy_async(
                    history=history, days_ahead=days_ahead,
                    weather_data=weather_data, events_data=events_data,
                )
            except Exception as e:
                logger.error(f"NeuralProphet error: {e}")
                return []

        async def run_xgboost():
            try:
                return await xgboost_service.forecast_occupancy_async(
                    history=history, days_ahead=days_ahead,
                    weather_data=weather_data, events_data=events_data,
                    district=district,  # Phase 7: per-district model isolation
                )
            except Exception as e:
                logger.error(f"XGBoost error: {e}")
                return []

        # Запуск всех моделей параллельно
        start_time = time.time()
        prophet_result, neural_result, xgboost_result = await asyncio.gather(
            run_prophet(),
            run_neuralprophet(),
            run_xgboost(),
        )
        elapsed = time.time() - start_time
        logger.info(f"Ensemble: все модели выполнены за {elapsed:.2f}s")

        results["models"]["prophet"] = prophet_result
        results["models"]["neuralprophet"] = neural_result
        results["models"]["xgboost"] = xgboost_result

        logger.info(f"Prophet: {len(prophet_result)} точек")
        logger.info(f"NeuralProphet: {len(neural_result)} точек")
        logger.info(f"XGBoost: {len(xgboost_result)} точек")

        if not self._calibrating and self._should_calibrate() and len(history) >= 60:
            try:
                metrics = await asyncio.to_thread(
                    self.compare_models, history, weather_data, events_data, 14,
                )
                if "best_model" in metrics:
                    self._update_weights(metrics)
                    self._calibrated_at = time.time()
                    results["weights"] = self._weights.copy()
                    logger.info(f"Ensemble: веса = {self._weights}")
            except Exception as e:
                logger.warning(f"Автокалибровка: {e}")

        if method == "simple_average":
            results["ensemble"] = self._simple_average(results["models"], days_ahead)
        elif method == "best_model":
            results["ensemble"] = self._best_model(results["models"])
        else:
            results["ensemble"] = self._weighted_average(results["models"], days_ahead)

        active = {k: v for k, v in results["models"].items() if v}
        if active:
            active_w = {k: self._weights.get(k, 0.33) for k in active}
            total = sum(active_w.values())
            if total > 0:
                results["weights"] = {k: round(v / total, 3) for k, v in active_w.items()}

        logger.info(f"Ensemble ({method}): {len(results['ensemble'])} точек")

        return results

    def forecast_ensemble(
        self,
        history: list[dict],
        days_ahead: int = 14,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        price_data: list[dict] | None = None,
        method: str = "weighted_average",
    ) -> dict:
        """Синхронная обёртка для обратной совместимости."""
        # Для синхронного контекста запускаем последовательно
        results: dict = {
            "models": {},
            "ensemble": [],
            "weights": self._weights.copy(),
            "method": method,
        }

        start_time = time.time()

        # Prophet
        try:
            results["models"]["prophet"] = prophet_service.forecast_occupancy(
                history=history, days_ahead=days_ahead,
                weather_data=weather_data, events_data=events_data,
            )
            logger.info(f"Prophet: {len(results['models']['prophet'])} точек")
        except Exception as e:
            logger.error(f"Prophet error: {e}")
            results["models"]["prophet"] = []

        # NeuralProphet
        try:
            results["models"]["neuralprophet"] = neuralprophet_service.forecast_occupancy(
                history=history, days_ahead=days_ahead,
                weather_data=weather_data, events_data=events_data,
            )
            logger.info(f"NeuralProphet: {len(results['models']['neuralprophet'])} точек")
        except Exception as e:
            logger.error(f"NeuralProphet error: {e}")
            results["models"]["neuralprophet"] = []

        # XGBoost
        try:
            results["models"]["xgboost"] = xgboost_service.forecast_occupancy(
                history=history, days_ahead=days_ahead,
                weather_data=weather_data, events_data=events_data,
            )
            logger.info(f"XGBoost: {len(results['models']['xgboost'])} точек")
        except Exception as e:
            logger.error(f"XGBoost error: {e}")
            results["models"]["xgboost"] = []

        elapsed = time.time() - start_time
        logger.info(f"Ensemble (sync): все модели выполнены за {elapsed:.2f}s")

        # Калибровка весов (с TTL)
        if not self._calibrating and self._should_calibrate() and len(history) >= 60:
            try:
                metrics = self.compare_models(history, weather_data, events_data, test_days=14)
                if "best_model" in metrics:
                    self._update_weights(metrics)
                    self._calibrated_at = time.time()
                    results["weights"] = self._weights.copy()
                    logger.info(f"Ensemble: веса = {self._weights}")
            except Exception as e:
                logger.warning(f"Автокалибровка: {e}")

        # Объединение
        if method == "simple_average":
            results["ensemble"] = self._simple_average(results["models"], days_ahead)
        elif method == "best_model":
            results["ensemble"] = self._best_model(results["models"])
        else:
            results["ensemble"] = self._weighted_average(results["models"], days_ahead)

        active = {k: v for k, v in results["models"].items() if v}
        if active:
            active_w = {k: self._weights.get(k, 0.33) for k in active}
            total = sum(active_w.values())
            if total > 0:
                results["weights"] = {k: round(v / total, 3) for k, v in active_w.items()}

        logger.info(f"Ensemble ({method}): {len(results['ensemble'])} точек")
        return results

    def _should_calibrate(self) -> bool:
        return (time.time() - self._calibrated_at) > CALIBRATION_TTL

    # ------------------------------------------------------------------
    # Aggregation methods
    # ------------------------------------------------------------------

    def _simple_average(
        self,
        models: dict[str, list[ForecastPoint]],
        days_ahead: int,
    ) -> list[ForecastPoint]:
        all_dates = sorted({fp.date for fcs in models.values() for fp in fcs})[:days_ahead]
        result = []
        for d in all_dates:
            vals, lbs, ubs = [], [], []
            for forecasts in models.values():
                for fp in forecasts:
                    if fp.date == d:
                        vals.append(fp.occupancy)
                        lbs.append(fp.lower_bound)
                        ubs.append(fp.upper_bound)
                        break
            if vals:
                mean_occ = float(np.mean(vals))
                result.append(ForecastPoint(
                    date=d,
                    occupancy=round(max(0.0, min(100.0, mean_occ)), 1),
                    lower_bound=round(max(0.0, min(100.0, float(np.mean(lbs)))), 1),
                    upper_bound=round(max(0.0, min(100.0, float(np.mean(ubs)))), 1),
                ))
        return result

    def _weighted_average(
        self,
        models: dict[str, list[ForecastPoint]],
        days_ahead: int,
    ) -> list[ForecastPoint]:
        """Взвешенное среднее с CI = avg_model_CI + model_disagreement.

        CI = weighted average of individual model half-widths + inter-model disagreement.
        Not a calibrated statistical interval; treated as an uncertainty band.
        Individual sources: Prophet (80% PI), NeuralProphet (residual-based), XGBoost (1.28*RMSE ~ 80%).
        """
        all_dates = sorted({fp.date for fcs in models.values() for fp in fcs})[:days_ahead]
        result = []
        for d in all_dates:
            values, lbs, ubs, ws = [], [], [], []
            for name, forecasts in models.items():
                w = self._weights.get(name, 0.33)
                for fp in forecasts:
                    if fp.date == d:
                        values.append(fp.occupancy)
                        lbs.append(fp.lower_bound)
                        ubs.append(fp.upper_bound)
                        ws.append(w)
                        break
            if not ws:
                continue
            w_total = sum(ws)
            mean_occ = sum(v * w for v, w in zip(values, ws)) / w_total

            disagreement = (sum(w * (v - mean_occ) ** 2 for v, w in zip(values, ws)) / w_total) ** 0.5
            avg_half_ci = sum(w * (u - l) / 2 for w, l, u in zip(ws, lbs, ubs)) / w_total
            total_half_ci = avg_half_ci + disagreement

            result.append(ForecastPoint(
                date=d,
                occupancy=round(max(0.0, min(100.0, mean_occ)), 1),
                lower_bound=round(max(0.0, mean_occ - total_half_ci), 1),
                upper_bound=round(min(100.0, mean_occ + total_half_ci), 1),
            ))
        return result

    def _best_model(
        self,
        models: dict[str, list[ForecastPoint]],
    ) -> list[ForecastPoint]:
        """Выбирает лучшую модель по реальным метрикам."""
        if self._last_metrics and "best_model" in self._last_metrics:
            best = self._last_metrics["best_model"]
            if best in models and models[best]:
                return models[best]

        # Fallback: модель с наибольшим весом
        best_name = max(self._weights, key=self._weights.get)
        if best_name in models and models[best_name]:
            return models[best_name]

        for forecasts in models.values():
            if forecasts:
                return forecasts
        return []

    # ------------------------------------------------------------------
    # Model comparison
    # ------------------------------------------------------------------

    # Phase 6: walk-forward CV параметры
    CV_FOLDS: int = 5
    CV_STEP_DAYS: int = 14  # шаг сдвига между fold'ами

    def compare_models(
        self,
        history: list[dict],
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        test_days: int = 14,
    ) -> dict:
        """Сравнение моделей через walk-forward CV (5 fold'ов, step=14d).

        Phase 6: вместо одной фиксированной hold-out оценки (last 14 days) — катящееся окно:
        fold 0 берёт train=[:N-5*14], test=[N-5*14 : N-4*14], ..., fold 4 = последние 14 дней.
        Это даёт честную картину стабильности модели: помимо mean RMSE возвращаем `rmse_std`.

        Возвращает dict:
            {
              "prophet":   {"rmse": ..., "mae": ..., "r2": ..., "rmse_std": ..., "fold_count": N, "points": ...},
              "neuralprophet": {...},
              "xgboost":   {...},
              "ensemble":  {...},
              "best_model": "prophet" | "neuralprophet" | "xgboost",
              "cv_strategy": "walk_forward_5fold",
            }

        Fallback: если данных мало для 5 fold (< test_days + 30 + 4*CV_STEP_DAYS = ~116) —
        автоматически снижается на меньшее число fold'ов или одиночный hold-out.
        """
        # Минимально требуется test_days + 30 (для XGBoost warm-up) + (folds-1)*step для смещения
        min_for_full_cv = test_days + 30 + (self.CV_FOLDS - 1) * self.CV_STEP_DAYS
        if len(history) < test_days + 30:
            return {"error": "Недостаточно данных"}

        # Адаптивно: сколько fold реально влезает
        if len(history) >= min_for_full_cv:
            cv_folds = self.CV_FOLDS
        else:
            cv_folds = max(1, (len(history) - test_days - 30) // self.CV_STEP_DAYS + 1)
            logger.info(
                "compare_models: данных %d точек, walk-forward сокращён до %d fold'ов "
                "(полный CV требует ≥%d)",
                len(history), cv_folds, min_for_full_cv,
            )

        # Per-model per-fold метрики
        rmse_per_model: dict[str, list[float]] = defaultdict(list)
        mae_per_model: dict[str, list[float]] = defaultdict(list)
        r2_per_model: dict[str, list[float]] = defaultdict(list)
        points_per_model: dict[str, int] = defaultdict(int)

        self._calibrating = True
        try:
            for fold_idx in range(cv_folds):
                # Сдвиг тестового окна: fold 0 — самый старый, последний — самые свежие 14 дней
                folds_from_end = cv_folds - fold_idx  # 5, 4, 3, 2, 1 для cv_folds=5
                end_train_idx = len(history) - folds_from_end * self.CV_STEP_DAYS
                if end_train_idx < 30:
                    logger.warning(
                        "compare_models fold %d: train slice %d < 30, пропуск",
                        fold_idx, end_train_idx,
                    )
                    continue
                train_slice = history[:end_train_idx]
                test_slice = history[end_train_idx:end_train_idx + test_days]
                if len(test_slice) < 3:
                    continue
                actuals = {h["date"]: h["occupancy"] for h in test_slice}

                fold_forecasts = self.forecast_ensemble(
                    history=train_slice, days_ahead=test_days,
                    weather_data=weather_data, events_data=events_data,
                    method="weighted_average",
                )
                # Per-model метрики
                for name, fcs in fold_forecasts["models"].items():
                    m = self._compute_metrics(fcs, actuals)
                    if m:
                        rmse_per_model[name].append(m["rmse"])
                        mae_per_model[name].append(m["mae"])
                        r2_per_model[name].append(m["r2"])
                        points_per_model[name] += m["points"]
                # Ensemble
                m_ens = self._compute_metrics(fold_forecasts["ensemble"], actuals)
                if m_ens:
                    rmse_per_model["ensemble"].append(m_ens["rmse"])
                    mae_per_model["ensemble"].append(m_ens["mae"])
                    r2_per_model["ensemble"].append(m_ens["r2"])
                    points_per_model["ensemble"] += m_ens["points"]

                logger.info(
                    "compare_models fold %d/%d: train[0:%d], test[%d:%d], rmse=%s",
                    fold_idx + 1, cv_folds, end_train_idx, end_train_idx, end_train_idx + test_days,
                    {n: round(rmse_per_model[n][-1], 2) for n in rmse_per_model if rmse_per_model[n]},
                )
        finally:
            self._calibrating = False

        # Агрегация: mean + std по fold'ам
        results: dict = {"cv_strategy": f"walk_forward_{cv_folds}fold"}
        for name, rmses in rmse_per_model.items():
            if not rmses:
                continue
            results[name] = {
                "rmse": round(float(np.mean(rmses)), 2),
                "rmse_std": round(float(np.std(rmses)), 2),
                "mae": round(float(np.mean(mae_per_model[name])), 2),
                "r2": round(float(np.mean(r2_per_model[name])), 3),
                "fold_count": len(rmses),
                "points": points_per_model[name],
            }

        if results:
            model_names = [k for k in results if k not in ("ensemble", "cv_strategy", "best_model")]
            if model_names:
                results["best_model"] = min(
                    model_names,
                    key=lambda k: results[k].get("rmse", 999.0) if isinstance(results.get(k), dict) else 999.0,
                )

        self._last_metrics = results
        return results

    def _compute_metrics(
        self,
        forecasts: list[ForecastPoint],
        actuals: dict,
    ) -> dict | None:
        actuals_str = {str(k): v for k, v in actuals.items()}
        y_true, y_pred = [], []
        for fp in forecasts:
            key = str(fp.date)
            if key in actuals_str:
                y_true.append(actuals_str[key])
                y_pred.append(fp.occupancy)
        if not y_true:
            return None
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        mae = float(mean_absolute_error(y_true, y_pred))
        r2 = float(r2_score(y_true, y_pred)) if len(y_true) > 1 else 0.0
        return {"rmse": round(rmse, 2), "mae": round(mae, 2), "r2": round(r2, 3), "points": len(y_true)}

    # ------------------------------------------------------------------
    # Weight calibration
    # ------------------------------------------------------------------

    def _update_weights(self, metrics: dict) -> None:
        """Обновляет веса по inverse-RMSE."""
        rmses = {}
        for name in ["prophet", "neuralprophet", "xgboost"]:
            if name in metrics and "rmse" in metrics[name]:
                rmses[name] = metrics[name]["rmse"]

        if not rmses:
            return

        inv = {k: 1.0 / (v + 0.1) for k, v in rmses.items()}
        total = sum(inv.values())
        self._weights = {k: round(v / total, 3) for k, v in inv.items()}
        logger.info(f"Веса обновлены: {self._weights}")


ensemble_service = EnsembleService()
