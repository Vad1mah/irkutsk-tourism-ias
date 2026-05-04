"""Async SQLAlchemy session и engine."""
import logging

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

logger = logging.getLogger(__name__)

_engine = None
_async_session = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url.get_secret_value(),
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=10,
            connect_args={"command_timeout": 30},
        )
    return _engine


def _get_session_factory():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _async_session


def __getattr__(name: str):
    """Ленивый доступ к engine и async_session для обратной совместимости."""
    if name == "engine":
        return _get_engine()
    if name == "async_session":
        return _get_session_factory()
    raise AttributeError(f"module 'app.db.session' has no attribute {name}")
