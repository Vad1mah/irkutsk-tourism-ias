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
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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

    def setup_jobs(self):
        """Настроить расписание задач."""
        from app.constants import (
            SCHEDULER_EVENTS_HOURS,
            SCHEDULER_HOTELS_HOURS,
            SCHEDULER_WEATHER_HOURS,
            SCHEDULER_TELEGRAM_HOURS,
        )

        self.scheduler.add_job(
            self.collect_events,
            IntervalTrigger(hours=SCHEDULER_EVENTS_HOURS),
            id="collect_events",
            name="Сбор событий",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.collect_hotels,
            IntervalTrigger(hours=SCHEDULER_HOTELS_HOURS),
            id="collect_hotels",
            name="Сбор отелей",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.collect_weather,
            IntervalTrigger(hours=SCHEDULER_WEATHER_HOURS),
            id="collect_weather",
            name="Сбор погоды",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.collect_telegram,
            IntervalTrigger(hours=SCHEDULER_TELEGRAM_HOURS),
            id="collect_telegram",
            name="Сбор Telegram",
            replace_existing=True,
        )

        logger.info("Расписание задач настроено")

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
