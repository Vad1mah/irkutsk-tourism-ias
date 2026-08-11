"""Сервис кэширования через Redis."""
import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Асинхронный сервис кэширования через Redis."""
    
    def __init__(self):
        self._client: redis.Redis | None = None
        self._connected: bool = False
    
    async def connect(self):
        """Подключение к Redis."""
        try:
            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
            )
            # Проверяем подключение
            await self._client.ping()
            self._connected = True
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._connected = False
    
    async def close(self):
        """Закрытие соединения."""
        if self._client:
            await self._client.close()
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def client(self) -> redis.Redis | None:
        """Получить Redis client для direct access."""
        return self._client
    
    async def get(self, key: str) -> Any | None:
        """Получить значение из кэша."""
        if not self._connected:
            return None
        
        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int | None = None
    ) -> bool:
        """Сохранить значение в кэш."""
        if not self._connected:
            return False
        
        try:
            ttl = ttl or settings.redis_default_ttl
            await self._client.set(
                key, 
                json.dumps(value, default=str), 
                ex=ttl
            )
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Удалить значение из кэша."""
        if not self._connected:
            return False
        
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Удалить все ключи по паттерну."""
        if not self._connected:
            return 0
        
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self._client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Redis clear_pattern error: {e}")
            return 0
    
    def cache_key(self, prefix: str, *args) -> str:
        """Генерация ключа кэша."""
        parts = [prefix] + [str(a) for a in args if a is not None]
        return ":".join(parts)


cache_service = CacheService()

# Версия схемы ключа и семантики ответа ансамбля.
ENSEMBLE_MODEL_VERSION = "ens-v3-2026-08"


def compute_ensemble_data_hash(
    history: list[dict],
    weather_data: dict | None = None,
    events_data: list[dict] | None = None,
    model_version: str = ENSEMBLE_MODEL_VERSION,
) -> str:
    """Хэш входных данных ансамбля.

    Устроен по образцу ``xgboost_service._compute_data_hash``: берёт длину истории и её
    края, календарные ключи погоды и сводку событий — то есть всё, от чего зависит
    результат, и ничего, что меняется от одной лишь перестановки элементов.

    Args:
        history: Ряд наблюдений загрузки.
        weather_data: Погода по датам прогноза.
        events_data: События, поданные моделям как регрессор.
        model_version: Версия семантики ансамбля.

    Returns:
        Первые 16 hex-символов sha256.
    """
    weather_keys: list[str] = []
    if weather_data:
        sorted_keys = sorted(str(k) for k in weather_data)
        weather_keys = sorted_keys[:3] + sorted_keys[-3:] if len(sorted_keys) >= 6 else sorted_keys

    events_summary: dict = {}
    if events_data:
        dates = sorted(
            (e.get("date_start") for e in events_data if e.get("date_start")),
            key=str,
        )
        events_summary = {
            "count": len(events_data),
            "first_date": str(dates[0]) if dates else None,
            "last_date": str(dates[-1]) if dates else None,
        }

    payload = json.dumps(
        {
            "len": len(history),
            "first_3": history[:3],
            "last_5": history[-5:],
            "weather_keys": weather_keys,
            "events": events_summary,
            "version": model_version,
        },
        default=str,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_ensemble_cache_key(
    district: str,
    days: int,
    data_hash: str,
    models: Sequence[str],
    method: str = "weighted_average",
    model_version: str = ENSEMBLE_MODEL_VERSION,
) -> str:
    """Cache key для ensemble forecast.

    Ключ зависит от данных (``data_hash``) и от состава ансамбля (``models``), поэтому
    свежий импорт статистики, новый прогон парсеров событий или изменение набора моделей
    дают другой ключ, а не подмешивают старый ответ к новым условиям.

    Args:
        district: Название района.
        days: Горизонт прогноза в днях.
        data_hash: Результат :func:`compute_ensemble_data_hash` по тем же входам,
            на которых будет считаться прогноз.
        models: Имена моделей, которые ансамбль пытается запускать.
        method: Метод объединения моделей.
        model_version: Версия семантики ансамбля.

    Returns:
        Строка вида ``forecast:ensemble:<version>:<модели>:<район>:<дней>:<метод>:<хэш>``.
    """
    roster = "-".join(sorted(models)) or "none"
    return f"forecast:ensemble:{model_version}:{roster}:{district}:{days}:{method}:{data_hash}"
