"""Сервис кэширования через Redis."""
import json
import logging
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

# Версия модели ensemble — бампать при изменении весов или признаков.
ENSEMBLE_MODEL_VERSION = "ens-v2-2026-05"


def build_ensemble_cache_key(
    district: str,
    days: int,
    method: str = "weighted_average",
    model_version: str = ENSEMBLE_MODEL_VERSION,
) -> str:
    """Cache key для ensemble forecast.

    Включает model_version (для invalidation на retrain) и method (для разделения weighted_average / best_model / simple_average).
    Старые ключи без model_version естественно истекут по TTL.

    Args:
        district: Название района.
        days: Горизонт прогноза в днях.
        method: Метод объединения моделей.
        model_version: Версия модели; отличная версия → отдельный ключ,
            что исключает возврат устаревших данных после переобучения.

    Returns:
        Строка вида ``forecast:ensemble:<version>:<district>:<days>:<method>``.
    """
    return f"forecast:ensemble:{model_version}:{district}:{days}:{method}"
