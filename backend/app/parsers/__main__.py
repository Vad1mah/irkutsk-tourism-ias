"""CLI для запуска парсеров.

Usage:
    python -m app.parsers --parser hotels
    python -m app.parsers --parser events
    python -m app.parsers --parser weather
    python -m app.parsers --scheduler
    python -m app.parsers --all
"""
import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import settings
from app.parsers import (
    fetch_all_events,
    parse_and_save_hotels,
    get_major_events_2025_2026,
    get_school_holidays_2025_2026,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("parsers")


async def run_hotels_parser():
    """Запуск парсера отелей 101hotels."""
    logger.info("=== Запуск парсера отелей ===")
    try:
        result = await parse_and_save_hotels()
        logger.info(f"Парсинг отелей завершён: {result}")
        return result
    except Exception as e:
        logger.error(f"Ошибка парсера отелей: {e}")
        return {"error": str(e)}


async def run_events_parser():
    """Запуск всех парсеров событий."""
    logger.info("=== Запуск парсеров событий ===")
    try:
        events = await fetch_all_events(use_ai=True)
        logger.info(f"Собрано событий: {len(events)}")

        # Сохраняем в БД
        from app.services.data_service import data_service
        saved = 0
        for event in events:
            try:
                await data_service.save_event(
                    event_id=event.id,
                    title=event.title,
                    description=event.description,
                    date_start=event.date_start,
                    date_end=event.date_end,
                    event_type=event.event_type,
                    location=event.location,
                    source=event.source,
                    url=event.url,
                )
                saved += 1
            except Exception as e:
                logger.debug(f"Ошибка сохранения события {event.id}: {e}")

        logger.info(f"Сохранено событий: {saved}/{len(events)}")
        return {"total": len(events), "saved": saved}
    except Exception as e:
        logger.error(f"Ошибка парсера событий: {e}")
        return {"error": str(e)}


async def run_weather_parser():
    """Запуск парсера погоды OpenMeteo."""
    logger.info("=== Запуск парсера погоды ===")
    try:
        from app.parsers.weather_openmeteo import fetch_weather_forecast
        forecasts = await fetch_weather_forecast(days=16)
        total = sum(len(v) for v in forecasts.values())
        for loc, data in forecasts.items():
            logger.info(f"Погода {loc}: {len(data)} дней")
        result = {"locations": list(forecasts.keys()), "total_days": total}
        logger.info(f"Погода получена: {result}")
        return result
    except Exception as e:
        logger.error(f"Ошибка парсера погоды: {e}")
        return {"error": str(e)}


async def run_scheduler():
    """Запуск планировщика для регулярного сбора данных."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    # Отели: ежедневно в 6:00 UTC
    scheduler.add_job(run_hotels_parser, "cron", hour=6, minute=0, id="hotels")

    # События: ежедневно в 7:00 UTC
    scheduler.add_job(run_events_parser, "cron", hour=7, minute=0, id="events")

    # Погода: каждые 6 часов
    scheduler.add_job(run_weather_parser, "interval", hours=6, id="weather")

    logger.info("Планировщик запущен")
    logger.info("  - Отели: ежедневно в 06:00 UTC")
    logger.info("  - События: ежедневно в 07:00 UTC")
    logger.info("  - Погода: каждые 6 часов")

    scheduler.start()

    # Бесконечный цикл
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Планировщик остановлен")


async def run_all():
    """Запуск всех парсеров последовательно."""
    logger.info("=== Запуск всех парсеров ===")

    results = {}

    # Отели
    results["hotels"] = await run_hotels_parser()

    # События
    results["events"] = await run_events_parser()

    # Погода
    results["weather"] = await run_weather_parser()

    logger.info(f"=== Все парсеры завершены ===")
    for name, result in results.items():
        if isinstance(result, dict) and "error" in result:
            logger.warning(f"  {name}: ОШИБКА - {result['error']}")
        else:
            logger.info(f"  {name}: OK - {result}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Парсеры данных ИАС Туризм")
    parser.add_argument(
        "--parser",
        choices=["hotels", "events", "weather", "all"],
        help="Какой парсер запустить"
    )
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Запустить планировщик (daemon mode)"
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Показать список источников"
    )

    args = parser.parse_args()

    if args.list_sources:
        print("\nИсточники данных:")
        print("\nОтели:")
        print("  - 101hotels.com (загрузка, цены)")
        print("  - Xotelo/TripAdvisor (рейтинги)")
        print("\nСобытия:")
        print("  - zeroevent.ru")
        print("  - culture38.ru")
        print("  - irk.ru/afisha")
        print("  - Яндекс Афиша")
        print("  - Kassir.ru")
        print("  - Культура РФ")
        print("  - Telegram каналы")
        print("\nПогода:")
        print("  - OpenMeteo API")
        print("\nКрупные события:")
        print("  - Вручную собранные (фестивали, праздники)")
        print("  - Школьные каникулы")
        return

    if args.scheduler:
        asyncio.run(run_scheduler())
        return

    if args.parser == "hotels":
        asyncio.run(run_hotels_parser())
    elif args.parser == "events":
        asyncio.run(run_events_parser())
    elif args.parser == "weather":
        asyncio.run(run_weather_parser())
    elif args.parser == "all":
        asyncio.run(run_all())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
