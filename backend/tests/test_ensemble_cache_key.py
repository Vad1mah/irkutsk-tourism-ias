"""Cache key для ensemble должен содержать model_version."""
import pytest


def test_ensemble_cache_key_includes_model_version():
    from app.services.cache_service import build_ensemble_cache_key

    key1 = build_ensemble_cache_key(district="Иркутский", days=14, model_version="v1")
    key2 = build_ensemble_cache_key(district="Иркутский", days=14, model_version="v2")
    assert key1 != key2, "Different model_version must yield different cache keys"
    assert "v1" in key1 and "v2" in key2


def test_ensemble_cache_key_default_model_version():
    """Default version constant from settings/cache module."""
    from app.services.cache_service import build_ensemble_cache_key, ENSEMBLE_MODEL_VERSION

    key = build_ensemble_cache_key(district="Иркутский", days=14)
    assert ENSEMBLE_MODEL_VERSION in key
    assert "Иркутский" in key
    assert "14" in key


def test_ensemble_cache_key_includes_method():
    """Different methods yield different cache keys."""
    from app.services.cache_service import build_ensemble_cache_key

    k_weighted = build_ensemble_cache_key(district="Иркутский", days=14, method="weighted_average")
    k_best = build_ensemble_cache_key(district="Иркутский", days=14, method="best_model")
    assert k_weighted != k_best
    assert "weighted_average" in k_weighted
    assert "best_model" in k_best
