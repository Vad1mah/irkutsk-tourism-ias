"""Планировщик задач для автоматического сбора данных.

Использует APScheduler для периодического запуска парсеров.

Расписание:
- События (все источники): каждые 6 часов
- Отели (101hotels): каждые 2 часа
- Погода (OpenMeteo): каждые 3 часа
- Telegram каналы: каждый час

Запуск:
    python -m app.scheduler
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

T = TypeVar("T")


async def _run_with_timeout(
    coro_factory: Callable[[], Awaitable[T]],
    *,
    timeout_s: int,
    task_label: str,
    logger_: logging.Logger,
) -> T | None:
    """Запустить корутину с таймаутом. При срабатывании — лог + traceback, без re-raise.

    Возвращает результат корутины или None при timeout/exception.
    Все сценарии: corо завершилась → результат; timeout → None + WARNING; exception → None + ERROR.
    """
    try:
        return await asyncio.wait_for(coro_factory(), timeout=timeout_s)
    except asyncio.TimeoutError:
        logger_.error(
            f"[{task_label}] таймаут {timeout_s}s превышен — задача прервана. "
            f"Это блокировало бы расписание до следующего интервала. "
            f"Проверьте сетевые таймауты в парсере / медленные внешние API."
        )
        return None
    except Exception:
        logger_.error(
            f"[{task_label}] неожиданная ошибка:\n{traceback.format_exc()}"
        )
        return None

# scripts/ — не пакет (нет __init__.py), но в нём лежит reclassify_events
# с async main(). Делаем директорию backend/ доступной для импорта пакета scripts.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
from scripts.reclassify_events import main as reclassify_main  # noqa: E402

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


class DataCollectorScheduler:
    """Планировщик сбора данных."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.stats = {
            "events_collected": 0,
            "hotels_collected": 0,
            "weather_collected": 0,
            "last_run": {},
            "errors": [],
        }

    async def _reindex_chroma(self):
        """Переиндексировать ChromaDB после обновления данных."""
        try:
            from app.services.chroma_service import chroma_service
            from app.services.data_service import data_service
            from app.routers.documents import reindex_chroma

            result = await reindex_chroma(chroma_service, data_service)
            count = result.get("indexed_count", 0)
            logger.info(f"ChromaDB переиндексирована: {count} документов")
        except Exception as e:
            logger.warning(f"Ошибка переиндексации ChromaDB: {e}")

    async def collect_events(self) -> int:
        """Собрать события из всех источников и сохранить в БД."""
        logger.info("Запуск сбора событий...")
        try:
            from app.parsers import fetch_all_events
            from app.services.data_service import data_service

            events = await fetch_all_events(use_ai=True)
            count = len(events)

            if events:
                saved = await data_service.upsert_events_batch(events)
                logger.info(f"Собрано {count} событий, сохранено {saved}")
                await self._reindex_chroma()
            else:
                saved = 0
                logger.info("Нет новых событий")

            self.stats["events_collected"] += count
            self.stats["last_run"]["events"] = datetime.now().isoformat()
            return count
        except Exception as e:
            logger.error(f"Ошибка сбора событий: {e}")
            self.stats["errors"].append(
                {"task": "events", "error": str(e), "time": datetime.now().isoformat()}
            )
            self.stats["errors"] = self.stats["errors"][-50:]
            return 0

    async def collect_hotels(self) -> int:
        """Собрать данные об отелях."""
        logger.info("Запуск сбора отелей...")
        try:
            from app.parsers.hotels_101hotels import parse_and_save_hotels

            result = await parse_and_save_hotels(use_regions=True)
            count = result.get("hotels_count", 0)
            self.stats["hotels_collected"] += count
            self.stats["last_run"]["hotels"] = datetime.now().isoformat()
            logger.info(
                f"Собрано {count} отелей, "
                f"сохранено {result.get('hotels_saved', 0)}"
            )
            if count > 0:
                await self._reindex_chroma()
            return count
        except Exception as e:
            logger.error(f"Ошибка сбора отелей: {e}")
            self.stats["errors"].append(
                {"task": "hotels", "error": str(e), "time": datetime.now().isoformat()}
            )
            self.stats["errors"] = self.stats["errors"][-50:]
            return 0

    async def collect_hotels_full(self) -> int:
        """Суточный обход всех городов из CITY_SLUG_TO_NAME.

        Двухчасовой job ходит только по двум региональным слагам 101hotels и
        упирается в потолок ~290 объектов: мелких населённых пунктов в этих
        категориях нет. Полный обход городов даёт широту реестра, но он
        тяжелее, поэтому запускается раз в сутки, а не каждые два часа.
        """
        logger.info("Запуск полного сбора отелей по городам...")
        try:
            from app.parsers.hotels_101hotels import parse_and_save_hotels

            result = await parse_and_save_hotels(use_regions=False)
            count = result.get("hotels_count", 0)
            self.stats["hotels_collected"] += count
            self.stats["last_run"]["hotels_full"] = datetime.now().isoformat()
            logger.info(
                f"Полный обход: собрано {count} отелей, "
                f"сохранено {result.get('hotels_saved', 0)}"
            )
            return count
        except Exception as e:
            logger.error(f"Ошибка полного сбора отелей: {e}")
            self.stats["errors"].append(
                {"task": "hotels_full", "error": str(e), "time": datetime.now().isoformat()}
            )
            self.stats["errors"] = self.stats["errors"][-50:]
            return 0

    async def collect_weather(self) -> int:
        """Собрать прогноз погоды (кэш weather_service обновляется автоматически)."""
        logger.info("Запуск сбора погоды...")
        try:
            from app.services.weather_service import weather_service

            forecasts = await weather_service.get_forecast_weather(days_ahead=16)
            count = len(forecasts)
            self.stats["weather_collected"] += count
            self.stats["last_run"]["weather"] = datetime.now().isoformat()
            logger.info(f"Собрано {count} записей погоды (кэш обновлён)")
            return count
        except Exception as e:
            logger.error(f"Ошибка сбора погоды: {e}")
            self.stats["errors"].append(
                {"task": "weather", "error": str(e), "time": datetime.now().isoformat()}
            )
            self.stats["errors"] = self.stats["errors"][-50:]
            return 0

    async def collect_telegram(self) -> int:
        """Собрать события из Telegram каналов."""
        logger.info("Запуск сбора из Telegram...")
        try:
            from app.parsers import fetch_events_telegram
            from app.parsers import _run_standalone_with_health
            from app.services.data_service import data_service

            events = await _run_standalone_with_health(
                "telegram", fetch_events_telegram, use_telethon=False, days_back=1
            )
            count = len(events)

            if events:
                saved = await data_service.upsert_events_batch(events)
                logger.info(f"Собрано {count} событий из Telegram, сохранено {saved}")
                await self._reindex_chroma()
            else:
                logger.info("Нет новых событий из Telegram")

            self.stats["last_run"]["telegram"] = datetime.now().isoformat()
            return count
        except Exception as e:
            logger.error(f"Ошибка сбора Telegram: {e}")
            self.stats["errors"].append(
                {"task": "telegram", "error": str(e), "time": datetime.now().isoformat()}
            )
            self.stats["errors"] = self.stats["errors"][-50:]
            return 0

    async def _reclassify_events(self):
        """Cron-обёртка: переклассифицирует события с event_type='event' через Mistral."""
        try:
            logger.info("Cron: запуск реклассификации событий")
            await reclassify_main(limit=None, dry_run=False, concurrency=5)
            logger.info("Cron: реклассификация завершена")
        except Exception as e:
            logger.error(f"Cron reclassify_events failed: {e}")
            self.stats["errors"].append(
                {
                    "task": "reclassify_events",
                    "error": str(e),
                    "time": datetime.now().isoformat(),
                }
            )
            self.stats["errors"] = self.stats["errors"][-50:]

    def _wrap_with_timeout(
        self,
        fn: Callable[[], Awaitable[T]],
        *,
        task_label: str,
        timeout_s: int,
    ) -> Callable[[], Awaitable[T | None]]:
        """Создаёт безопасную обёртку для APScheduler.

        Если job зависнет — корутина прервётся через timeout_s, scheduler не блокирует
        следующие интервалы. Ошибка логируется, но не сваливается наружу.
        """
        async def wrapper() -> T | None:
            return await _run_with_timeout(
                fn, timeout_s=timeout_s, task_label=task_label, logger_=logger
            )
        wrapper.__name__ = f"timeout_wrapper_{task_label}"
        return wrapper

    def setup_jobs(self):
        """Настроить расписание задач."""
        from app.constants import (
            SCHEDULER_EVENTS_HOURS,
            SCHEDULER_HOTELS_HOURS,
            SCHEDULER_WEATHER_HOURS,
            SCHEDULER_TELEGRAM_HOURS,
            SCHEDULER_EVENTS_TIMEOUT_S,
            SCHEDULER_HOTELS_TIMEOUT_S,
            SCHEDULER_HOTELS_FULL_TIMEOUT_S,
            SCHEDULER_WEATHER_TIMEOUT_S,
            SCHEDULER_TELEGRAM_TIMEOUT_S,
            SCHEDULER_RECLASSIFY_TIMEOUT_S,
        )

        self.scheduler.add_job(
            self._wrap_with_timeout(
                self.collect_events, task_label="events", timeout_s=SCHEDULER_EVENTS_TIMEOUT_S
            ),
            IntervalTrigger(hours=SCHEDULER_EVENTS_HOURS),
            id="collect_events",
            name="Сбор событий",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.scheduler.add_job(
            self._wrap_with_timeout(
                self.collect_hotels, task_label="hotels", timeout_s=SCHEDULER_HOTELS_TIMEOUT_S
            ),
            IntervalTrigger(hours=SCHEDULER_HOTELS_HOURS),
            id="collect_hotels",
            name="Сбор отелей",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.scheduler.add_job(
            self._wrap_with_timeout(
                self.collect_hotels_full,
                task_label="hotels_full",
                timeout_s=SCHEDULER_HOTELS_FULL_TIMEOUT_S,
            ),
            CronTrigger(hour=4, minute=30),
            id="collect_hotels_full",
            name="Полный сбор отелей по городам",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.scheduler.add_job(
            self._wrap_with_timeout(
                self.collect_weather, task_label="weather", timeout_s=SCHEDULER_WEATHER_TIMEOUT_S
            ),
            IntervalTrigger(hours=SCHEDULER_WEATHER_HOURS),
            id="collect_weather",
            name="Сбор погоды",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.scheduler.add_job(
            self._wrap_with_timeout(
                self.collect_telegram, task_label="telegram", timeout_s=SCHEDULER_TELEGRAM_TIMEOUT_S
            ),
            IntervalTrigger(hours=SCHEDULER_TELEGRAM_HOURS),
            id="collect_telegram",
            name="Сбор Telegram",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.scheduler.add_job(
            self._wrap_with_timeout(
                self._reclassify_events,
                task_label="reclassify_events",
                timeout_s=SCHEDULER_RECLASSIFY_TIMEOUT_S,
            ),
            CronTrigger(hour='*/6', minute=15),  # 0:15, 6:15, 12:15, 18:15
            id="reclassify_events",
            name="Реклассификация событий event_type='event' через Mistral",
            replace_existing=True,
            max_instances=1,
        )

        logger.info(
            "Расписание задач настроено (job timeouts: events=%ds, hotels=%ds, weather=%ds, telegram=%ds)",
            SCHEDULER_EVENTS_TIMEOUT_S,
            SCHEDULER_HOTELS_TIMEOUT_S,
            SCHEDULER_WEATHER_TIMEOUT_S,
            SCHEDULER_TELEGRAM_TIMEOUT_S,
        )

    async def run_initial_collection(self):
        """Запустить начальный сбор данных."""
        logger.info("Запуск начального сбора данных...")

        # Запускаем параллельно
        results = await asyncio.gather(
            self.collect_events(),
            self.collect_hotels(),
            self.collect_weather(),
            self.collect_telegram(),
            return_exceptions=True,
        )

        logger.info(f"Начальный сбор завершён: {results}")

    async def start(self, run_initial: bool = True):
        """Запустить планировщик."""
        self.setup_jobs()
        self.scheduler.start()
        logger.info("Планировщик запущен")

        if run_initial:
            asyncio.get_running_loop().create_task(self.run_initial_collection())

    def stop(self):
        """Остановить планировщик."""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")

    def get_stats(self) -> dict:
        """Получить статистику."""
        jobs = []
        for job in self.scheduler.get_jobs():
            # APScheduler 3.x: next_run_time, APScheduler 4.x: scheduled_run_time
            next_run = getattr(job, 'next_run_time', None) or getattr(job, 'scheduled_run_time', None)
            jobs.append(
                {
                    "id": job.id,
                    "name": getattr(job, 'name', job.id),
                    "next_run": next_run.isoformat() if next_run else None,
                }
            )

        return {
            **self.stats,
            "jobs": jobs,
            "running": self.scheduler.running,
        }


# Глобальный экземпляр
scheduler: DataCollectorScheduler | None = None


def get_scheduler() -> DataCollectorScheduler:
    """Получить экземпляр планировщика."""
    global scheduler
    if scheduler is None:
        scheduler = DataCollectorScheduler()
    return scheduler


async def main():
    """Точка входа для запуска планировщика."""
    import signal
    import sys

    sched = get_scheduler()

    # Обработка сигналов завершения
    def shutdown(signum, frame):
        logger.info("Получен сигнал завершения")
        sched.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    # SIGTERM не существует на Windows
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, shutdown)

    await sched.start(run_initial=True)

    # Держим event loop активным
    try:
        while True:
            await asyncio.sleep(60)
            # Логируем статус каждую минуту
            stats = sched.get_stats()
            logger.debug(f"Статус: {stats}")
    except asyncio.CancelledError:
        sched.stop()


if __name__ == "__main__":
    print("=" * 50)
    print("Планировщик сбора данных для BaikalAnalytics")
    print("=" * 50)
    print("\nРасписание:")
    print("  - События: каждые 6 часов")
    print("  - Отели: каждые 2 часа")
    print("  - Погода: каждые 3 часа")
    print("  - Telegram: каждый час")
    print("\nНажмите Ctrl+C для остановки\n")

    asyncio.run(main())
