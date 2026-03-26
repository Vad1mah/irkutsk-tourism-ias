"""Общий ThreadPoolExecutor для CPU-тяжёлых операций (ML-модели)."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ml_")


async def run_sync(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Запустить синхронную CPU-тяжёлую функцию в ThreadPoolExecutor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))


def shutdown_executor() -> None:
    """Корректно остановить executor."""
    _executor.shutdown(wait=False)
