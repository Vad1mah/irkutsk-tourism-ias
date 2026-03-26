"""Dependency Injection для FastAPI.

Все сервисы и сессии БД должны внедряться через Depends().
"""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.dependencies.auth import verify_api_key, optional_api_key
from app.services.protocols import DataServiceProtocol, ForecastServiceProtocol


# --- Services (singleton via lru_cache) ---

@lru_cache(maxsize=1)
def get_data_service_dep() -> DataServiceProtocol:
    """Singleton Data service."""
    from app.services.data_service import data_service
    return data_service


@lru_cache(maxsize=1)
def get_cache_service_dep() -> "CacheService":
    """Singleton Cache service."""
    from app.services.cache_service import CacheService, cache_service
    return cache_service


@lru_cache(maxsize=1)
def get_chroma_service_dep() -> "ChromaService":
    """Singleton ChromaDB service."""
    from app.services.chroma_service import ChromaService, chroma_service
    return chroma_service


@lru_cache(maxsize=1)
def get_prophet_service_dep() -> ForecastServiceProtocol:
    """Singleton Prophet service."""
    from app.services.prophet_service import prophet_service
    return prophet_service


@lru_cache(maxsize=1)
def get_neuralprophet_service_dep() -> ForecastServiceProtocol:
    """Singleton NeuralProphet service."""
    from app.services.neuralprophet_service import neuralprophet_service
    return neuralprophet_service


@lru_cache(maxsize=1)
def get_xgboost_service_dep() -> "XGBoostService":
    """Singleton XGBoost service."""
    from app.services.xgboost_service import XGBoostService, xgboost_service
    return xgboost_service


@lru_cache(maxsize=1)
def get_ensemble_service_dep() -> "EnsembleService":
    """Singleton Ensemble service."""
    from app.services.ensemble_service import EnsembleService, ensemble_service
    return ensemble_service


@lru_cache(maxsize=1)
def get_weather_service_dep() -> "WeatherService":
    """Singleton Weather service."""
    from app.services.weather_service import WeatherService, weather_service
    return weather_service


@lru_cache(maxsize=1)
def get_holidays_service_dep() -> "HolidaysService":
    """Singleton Holidays service."""
    from app.services.holidays_service import HolidaysService, holidays_service
    return holidays_service


@lru_cache(maxsize=1)
def get_llm_service_dep() -> "LLMService":
    """Singleton LLM service."""
    from app.services.llm_service import LLMService, llm_service
    return llm_service


# Type annotations для инъекции в endpoints
DataServiceDep = Annotated[DataServiceProtocol, Depends(get_data_service_dep)]
CacheServiceDep = Annotated["CacheService", Depends(get_cache_service_dep)]
ChromaServiceDep = Annotated["ChromaService", Depends(get_chroma_service_dep)]
ProphetServiceDep = Annotated[ForecastServiceProtocol, Depends(get_prophet_service_dep)]
NeuralProphetServiceDep = Annotated[ForecastServiceProtocol, Depends(get_neuralprophet_service_dep)]
XGBoostServiceDep = Annotated["XGBoostService", Depends(get_xgboost_service_dep)]
EnsembleServiceDep = Annotated["EnsembleService", Depends(get_ensemble_service_dep)]
WeatherServiceDep = Annotated["WeatherService", Depends(get_weather_service_dep)]
HolidaysServiceDep = Annotated["HolidaysService", Depends(get_holidays_service_dep)]
LLMServiceDep = Annotated["LLMService", Depends(get_llm_service_dep)]


__all__ = [
    "verify_api_key",
    "optional_api_key",
    "DataServiceDep",
    "CacheServiceDep",
    "ChromaServiceDep",
    "ProphetServiceDep",
    "NeuralProphetServiceDep",
    "XGBoostServiceDep",
    "EnsembleServiceDep",
    "WeatherServiceDep",
    "HolidaysServiceDep",
    "LLMServiceDep",
]
