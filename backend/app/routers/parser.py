"""Роутер для запуска парсеров данных."""
from fastapi import APIRouter, HTTPException, Depends, Query
import logging
from typing import Any

from app.parsers import (
    fetch_events_irk,
    fetch_events_culture38,
    fetch_events_zeroevent,
    fetch_events_yandex,
    fetch_events_kassir,
    fetch_events_telegram,
    fetch_all_events,
)
from app.parsers.events_culture_rf import fetch_events_culture_rf
from app.parsers.hotels_101hotels import parse_and_save_hotels
from app.parsers.hotels_xotelo import fetch_hotels_xotelo, parse_and_save_xotelo
from app.dependencies import DataServiceDep, verify_api_key
from app.scheduler import get_scheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parser", tags=["parser"])


@router.post("/hotels", dependencies=[Depends(verify_api_key)])
async def parse_hotels(days_ahead: int = Query(1, ge=1, le=30), use_regions: bool = True) -> dict[str, Any]:
    """Запустить парсинг отелей 101Hotels (региональный режим). Требует API ключ."""
    try:
        result = await parse_and_save_hotels(
            days_ahead=days_ahead, use_regions=use_regions
        )
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"101Hotels parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга 101Hotels. Проверьте логи сервера.")


@router.post("/hotels/xotelo", dependencies=[Depends(verify_api_key)])
async def parse_hotels_xotelo(
    location_key: str | None = None,
    save: bool = False,
):
    """Парсинг метаданных отелей через Xotelo API (TripAdvisor). Требует API ключ.

    Args:
        location_key: TripAdvisor geo key (по умолчанию Иркутская область)
        save: Сохранить cross-reference в БД
    """
    try:
        if save:
            result = await parse_and_save_xotelo(location_key, save_to_db=True)
        else:
            hotels = await fetch_hotels_xotelo(location_key, max_hotels=50)
            result = {
                "hotels_fetched": len(hotels),
                "hotels": hotels[:10],
            }
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Xotelo parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/irk", dependencies=[Depends(verify_api_key)])
async def parse_events_irk_endpoint(
    data: DataServiceDep,
    days_ahead: int = Query(7, ge=1, le=90),
    save_to_db: bool = True,
):
    """Запустить парсинг событий с irk.ru. Требует API ключ."""
    try:
        events = await fetch_events_irk(days_ahead=days_ahead)
        events_added = 0

        if save_to_db and events and data.is_connected:
            events_added = await data.upsert_events_batch(events)
            logger.info(f"IRK parser: {len(events)} found, {events_added} saved")

        return {
            "status": "ok",
            "events_found": len(events),
            "events_added": events_added,
            "events": events[:10],
        }
    except Exception as e:
        logger.error(f"IRK parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/culture38", dependencies=[Depends(verify_api_key)])
async def parse_events_culture38_endpoint(
    data: DataServiceDep,
    days_ahead: int = Query(7, ge=1, le=90),
    save_to_db: bool = True,
):
    """Запустить парсинг событий с culture38.ru. Требует API ключ."""
    try:
        events = await fetch_events_culture38(days_ahead=days_ahead)
        events_added = 0

        if save_to_db and events and data.is_connected:
            events_added = await data.upsert_events_batch(events)
            logger.info(f"Culture38 parser: {len(events)} found, {events_added} saved")

        return {
            "status": "ok",
            "events_found": len(events),
            "events_added": events_added,
            "events": events[:10],
        }
    except Exception as e:
        logger.error(f"Culture38 parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/zeroevent", dependencies=[Depends(verify_api_key)])
async def parse_events_zeroevent_endpoint(data: DataServiceDep, save: bool = True):
    """Парсинг событий с irk.zeroevent.ru. Требует API ключ."""
    try:
        events = await fetch_events_zeroevent()
        added = 0
        if save and events and data.is_connected:
            added = await data.upsert_events_batch(events)
        return {"status": "ok", "events_found": len(events), "events_added": added, "events": events[:5]}
    except Exception as e:
        logger.error(f"ZeroEvent parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/yandex", dependencies=[Depends(verify_api_key)])
async def parse_events_yandex_endpoint(
    data: DataServiceDep,
    use_ai: bool = True,
    save: bool = True,
):
    """Парсинг событий с Яндекс Афиши. Требует API ключ."""
    try:
        events = await fetch_events_yandex(use_ai=use_ai)
        added = 0
        if save and events and data.is_connected:
            added = await _save_parsed_events(events, "yandex", data)
        return {"status": "ok", "events_found": len(events), "events_added": added}
    except Exception as e:
        logger.error(f"Yandex parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/kassir", dependencies=[Depends(verify_api_key)])
async def parse_events_kassir_endpoint(
    data: DataServiceDep,
    use_ai: bool = True,
    save: bool = True,
):
    """Парсинг событий с kassir.ru. Требует API ключ."""
    try:
        events = await fetch_events_kassir(use_ai=use_ai)
        added = 0
        if save and events and data.is_connected:
            added = await _save_parsed_events(events, "kassir", data)
        return {"status": "ok", "events_found": len(events), "events_added": added}
    except Exception as e:
        logger.error(f"Kassir parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/culture-rf", dependencies=[Depends(verify_api_key)])
async def parse_events_culture_rf_endpoint(
    data: DataServiceDep,
    save: bool = True,
):
    """Парсинг событий с culture.ru. Требует API ключ."""
    try:
        events = await fetch_events_culture_rf()
        added = 0
        if save and events and data.is_connected:
            added = await _save_parsed_events(events, "culture_rf", data)
        return {"status": "ok", "events_found": len(events), "events_added": added}
    except Exception as e:
        logger.error(f"Culture.RF parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/telegram", dependencies=[Depends(verify_api_key)])
async def parse_events_telegram_endpoint(data: DataServiceDep, save: bool = True):
    """Парсинг событий из Telegram каналов (web preview). Требует API ключ."""
    try:
        events = await fetch_events_telegram(use_telethon=False)
        added = 0
        if save and events and data.is_connected:
            added = await _save_parsed_events(events, "telegram", data)
        return {"status": "ok", "events_found": len(events), "events_added": added}
    except Exception as e:
        logger.error(f"Telegram parser error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


@router.post("/events/all", dependencies=[Depends(verify_api_key)])
async def parse_all_events_endpoint(data: DataServiceDep, save: bool = True):
    """Запустить все парсеры событий параллельно. Требует API ключ."""
    try:
        all_events = await fetch_all_events()
        added = 0
        if save and all_events and data.is_connected:
            added = await _save_parsed_events(all_events, "all", data)
            await _trigger_reindex(data)
        return {
            "status": "ok",
            "total_events_found": len(all_events),
            "total_events_added": added,
        }
    except Exception as e:
        logger.error(f"All parsers error: {e}")
        raise HTTPException(500, "Ошибка парсинга. Проверьте логи сервера.")


async def _trigger_reindex(data: DataServiceDep):
    """Фоновая переиндексация ChromaDB после сохранения данных."""
    try:
        from app.services.chroma_service import chroma_service
        from app.routers.documents import reindex_chroma
        result = await reindex_chroma(chroma_service, data)
        logger.info(f"ChromaDB reindex: {result.get('indexed_count', 0)} docs")
    except Exception as e:
        logger.warning(f"ChromaDB reindex failed (non-critical): {e}")


async def _save_parsed_events(events: list, source: str, data: DataServiceDep) -> int:
    """Сохранить ParsedEvent или dict в БД (batch upsert)."""
    from app.parsers.base import ParsedEvent
    rows: list[dict] = []
    for ev in events:
        try:
            if isinstance(ev, ParsedEvent):
                rows.append({
                    "id": ev.id, "title": ev.title,
                    "description": ev.description,
                    "date_start": ev.date_start, "date_end": ev.date_end,
                    "location": ev.location, "source": ev.source or source,
                    "url": ev.url, "event_type": ev.event_type,
                })
            elif isinstance(ev, dict):
                rows.append(ev)
        except Exception as e:
            logger.error(f"Event conversion error: {e}")
    if not rows:
        return 0
    return await data.upsert_events_batch(rows)


# ── Scheduler endpoints ──────────────────────────────────────


@router.get("/scheduler/status", dependencies=[Depends(verify_api_key)])
async def scheduler_status():
    """Статус планировщика и расписание задач."""
    sched = get_scheduler()
    return sched.get_stats()


@router.post("/scheduler/run/{task}", dependencies=[Depends(verify_api_key)])
async def scheduler_run_task(task: str):
    """Ручной запуск задачи сбора данных. Требует API ключ.

    task: events | hotels | weather | telegram | all
    """
    sched = get_scheduler()
    if task == "events":
        count = await sched.collect_events()
    elif task == "hotels":
        count = await sched.collect_hotels()
    elif task == "weather":
        count = await sched.collect_weather()
    elif task == "telegram":
        count = await sched.collect_telegram()
    elif task == "all":
        await sched.run_initial_collection()
        return {"status": "ok", "message": "Полный сбор запущен"}
    else:
        raise HTTPException(400, f"Неизвестная задача: {task}")
    return {"status": "ok", "task": task, "collected": count}
