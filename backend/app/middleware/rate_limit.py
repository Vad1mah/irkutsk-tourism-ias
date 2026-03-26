"""Rate Limiting Middleware на базе Redis."""
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting с использованием Redis (sliding window).

    Защищает от:
    - DDoS атак
    - Злоупотребления API
    - Чрезмерных запросов к LLM
    """

    # Паттерны URL для rate limiting
    PROTECTED_PATTERNS = [
        "/api/query",
        "/api/parser",
        "/api/forecast",
        "/api/documents",
        "/api/analytics",
    ]

    # Более строгие лимиты для дорогих операций
    STRICT_PATTERNS = {
        "/api/query": 10,  # 10 запросов в минуту (LLM дорогая)
        "/api/parser": 5,  # 5 запросов в минуту (парсинг тяжёлый)
    }

    # Порог предупреждений для fail open
    FAIL_OPEN_WARN_THRESHOLD = 3

    # Доверенные прокси (IP адреса, от которых принимаем X-Forwarded-For)
    TRUSTED_PROXIES = {
        "127.0.0.1",
        "::1",
        "localhost",
    }

    def __init__(self, app, redis_client=None, trusted_proxies: list[str] | None = None):
        super().__init__(app)
        self.redis = redis_client
        self._local_cache: dict[str, list[float]] = {}
        self._enabled = bool(redis_client)
        self._redis_error_count = 0
        if trusted_proxies:
            self.TRUSTED_PROXIES.update(trusted_proxies)

    def _get_redis(self, request: Request):
        """Получить Redis client из app.state (отложенная инициализация)."""
        if self.redis:
            return self.redis
        redis = getattr(request.app.state, "redis_client", None)
        if redis:
            self.redis = redis
            self._enabled = True
        return self.redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Пропускаем OPTIONS и health checks
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Проверяем, нужен ли rate limiting
        if not self._should_rate_limit(path):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        rate_key = f"ratelimit:{client_ip}:{path}"

        limit = self._get_limit(path)
        redis = self._get_redis(request)

        if self._enabled and redis:
            allowed = await self._check_redis(rate_key, limit)
        else:
            allowed = self._check_local(rate_key, limit)

        if not allowed:
            logger.warning(f"Rate limit exceeded: {client_ip} -> {path}")
            return Response(
                content='{"detail":"Too many requests. Please wait."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        return await call_next(request)

    def _should_rate_limit(self, path: str) -> bool:
        """Проверить, нужен ли rate limiting для пути."""
        for pattern in self.PROTECTED_PATTERNS:
            if path.startswith(pattern):
                return True
        return False

    def _get_limit(self, path: str) -> int:
        """Получить лимит для пути."""
        for pattern, limit in self.STRICT_PATTERNS.items():
            if path.startswith(pattern):
                return limit
        return settings.rate_limit_requests

    def _get_client_ip(self, request: Request) -> str:
        """Получить IP клиента с защитой от spoofing.

        X-Forwarded-For используется только если запрос пришёл от доверенного прокси.
        """
        # Сначала проверяем, пришёл ли запрос от доверенного прокси
        remote_host = request.client.host if request.client else "unknown"

        # Используем X-Forwarded-For только от доверенных прокси
        if remote_host in self.TRUSTED_PROXIES:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()

        return remote_host

    async def _check_redis(self, key: str, limit: int) -> bool:
        """Проверка через Redis (sliding window)."""
        try:
            now = time.time()
            window_start = now - settings.rate_limit_period

            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, settings.rate_limit_period)
            results = await pipe.execute()

            current_count = results[1]
            # Сбрасываем счётчик ошибок при успехе
            self._redis_error_count = 0
            return current_count < limit
        except Exception as e:
            self._redis_error_count += 1
            # Логируем warning каждые N ошибок
            if self._redis_error_count >= self.FAIL_OPEN_WARN_THRESHOLD:
                logger.warning(
                    f"Redis rate limit failing open ({self._redis_error_count} errors). "
                    f"Rate limiting DISABLED. Last error: {e}"
                )
            else:
                logger.error(f"Redis rate limit error: {e}")
            return True  # Fail open для availability

    def _check_local(self, key: str, limit: int) -> bool:
        """Fallback rate limiting в памяти с защитой от memory leak."""
        now = time.time()
        window_start = now - settings.rate_limit_period
        MAX_LOCAL_CACHE_SIZE = 10000  # Защита от memory leak

        # Периодическая очистка кэша при достижении лимита
        if len(self._local_cache) >= MAX_LOCAL_CACHE_SIZE:
            # Удаляем все ключи с полностью истёкшими окнами
            expired_keys = [
                k for k, v in self._local_cache.items()
                if not v or all(ts <= window_start for ts in v)
            ]
            for k in expired_keys:
                del self._local_cache[k]
            logger.info(f"Rate limit local cache: cleaned {len(expired_keys)} expired keys")

        if key not in self._local_cache:
            self._local_cache[key] = []

        # Удаляем старые записи
        self._local_cache[key] = [
            ts for ts in self._local_cache[key] if ts > window_start
        ]

        if len(self._local_cache[key]) >= limit:
            return False

        self._local_cache[key].append(now)
        return True
