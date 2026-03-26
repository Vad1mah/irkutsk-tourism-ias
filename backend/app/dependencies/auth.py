"""Аутентификация и авторизация."""
import hmac
import logging
from fastapi import Depends, HTTPException, Header, status

from app.config import settings

logger = logging.getLogger(__name__)

# Флаг для отслеживания предупреждения о production без API_KEY
_production_warning_shown = False


def verify_api_key(
    x_api_key: str | None = Header(None, description="API ключ для защищённых endpoints"),
) -> str:
    """
    Проверить API ключ для административных endpoints.

    Usage:
        @router.post("/admin/action", dependencies=[Depends(verify_api_key)])

    Returns:
        API key если валиден

    Raises:
        HTTPException: 401 если ключ невалиден или отсутствует
    """
    global _production_warning_shown

    api_key = settings.get_api_key()
    is_production = settings.environment == "production"

    if not api_key:
        if is_production:
            if not _production_warning_shown:
                _production_warning_shown = True
                logger.error("CRITICAL: API_KEY not configured in PRODUCTION!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server misconfiguration: authentication not available",
            )
        logger.debug("API_KEY not configured - dev mode enabled")
        return "dev-mode"

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Pass X-API-Key header.",
        )

    if not hmac.compare_digest(x_api_key, api_key):
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key


def optional_api_key(
    x_api_key: str | None = Header(None, description="Опциональный API ключ"),
) -> str | None:
    """Опциональная проверка API ключа."""
    api_key = settings.get_api_key()

    if not api_key:
        return None

    if x_api_key and hmac.compare_digest(x_api_key, api_key):
        return x_api_key

    return None
