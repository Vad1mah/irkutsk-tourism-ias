"""Ключ кэша ансамбля обязан зависеть от данных и от состава моделей."""
from datetime import date

BASE_HISTORY = [{"date": date(2026, 8, i), "occupancy": 60.0 + i} for i in range(1, 11)]
MODELS = ["prophet", "xgboost"]


def _key(**overrides):
    from app.services.cache_service import build_ensemble_cache_key, compute_ensemble_data_hash

    params = {
        "district": "Иркутский",
        "days": 14,
        "data_hash": compute_ensemble_data_hash(BASE_HISTORY),
        "models": MODELS,
    }
    params.update(overrides)
    return build_ensemble_cache_key(**params)


def test_key_carries_district_days_and_version():
    from app.services.cache_service import ENSEMBLE_MODEL_VERSION

    key = _key()
    assert ENSEMBLE_MODEL_VERSION in key
    assert "Иркутский" in key
    assert "14" in key


def test_different_model_version_yields_different_key():
    assert _key(model_version="v1") != _key(model_version="v2")


def test_different_method_yields_different_key():
    k_weighted = _key(method="weighted_average")
    k_best = _key(method="best_model")
    assert k_weighted != k_best
    assert "weighted_average" in k_weighted
    assert "best_model" in k_best


def test_new_observation_changes_key():
    """Свежий день статистики обязан дать другой ключ — иначе отдаётся вчерашний прогноз."""
    from app.services.cache_service import compute_ensemble_data_hash

    extended = BASE_HISTORY + [{"date": date(2026, 8, 11), "occupancy": 71.0}]
    assert _key() != _key(data_hash=compute_ensemble_data_hash(extended))


def test_changed_events_change_hash():
    """Прогон парсеров событий меняет вход моделей, значит и ключ."""
    from app.services.cache_service import compute_ensemble_data_hash

    events = [{"date_start": date(2026, 8, 15), "title": "Фестиваль"}]
    assert compute_ensemble_data_hash(BASE_HISTORY) != compute_ensemble_data_hash(
        BASE_HISTORY, events_data=events
    )


def test_changed_weather_dates_change_hash():
    from app.services.cache_service import compute_ensemble_data_hash

    weather = {date(2026, 8, 12): {"temp": 20}}
    assert compute_ensemble_data_hash(BASE_HISTORY) != compute_ensemble_data_hash(
        BASE_HISTORY, weather_data=weather
    )


def test_model_roster_is_part_of_key():
    """Выпадение модели из ансамбля не должно попадать в чужой ключ."""
    assert _key(models=["prophet"]) != _key(models=["prophet", "xgboost"])


def test_roster_order_does_not_matter():
    assert _key(models=["xgboost", "prophet"]) == _key(models=["prophet", "xgboost"])


def test_hash_is_order_stable_for_events():
    """Перестановка списка событий не должна выглядеть как новые данные."""
    from app.services.cache_service import compute_ensemble_data_hash

    a = [{"date_start": date(2026, 8, 15)}, {"date_start": date(2026, 8, 20)}]
    b = list(reversed(a))
    assert compute_ensemble_data_hash(BASE_HISTORY, events_data=a) == compute_ensemble_data_hash(
        BASE_HISTORY, events_data=b
    )


def test_ensemble_model_names_matches_configured_weights():
    """Состав, попадающий в ключ, берётся из самого сервиса, а не из литерала в роутере."""
    from app.services.ensemble_service import ensemble_service

    assert ensemble_service.model_names == sorted(ensemble_service._weights)
    assert "neuralprophet" not in ensemble_service.model_names
