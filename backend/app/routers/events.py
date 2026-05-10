from fastapi import APIRouter, Query, HTTPException, Depends
import hashlib
import logging
import re
from datetime import date
from typing import Any

from app.models.schemas import Event
from app.dependencies import DataServiceDep, CacheServiceDep
from app.dependencies.auth import verify_api_key

logger = logging.getLogger(__name__)
from app.parsers import fetch_events_irk, fetch_events_culture38
from app.parsers.events_major import get_major_events_2025_2026, get_school_holidays_2025_2026

router = APIRouter(prefix="/api/events", tags=["events"])

# I-4: Спам-маркеры для фильтрации рекламного/юридического мусора из событий
_SPAM_MARKERS = [
    "сертификац", "рекламн", "подлежат обязательн", "реклам",
    "скидка на всё", "промокод", "подарочный сертификат",
    "условия акции", "правила акции", "условия использования",
]

# B2B-фокус: Иркутская область как whitelist локаций. События без location
# не отбрасываем (многие источники не отдают location). Если же location указан —
# проверяем, что он содержит одно из этих ключевых слов.
_REGION_WHITELIST = [
    "иркут", "ольхон", "байкал", "листвянк", "слюдянк", "ангарс", "усть-",
    "хужир", "култук", "тулун", "братск", "усолье", "шелехов", "черемхов",
    "саянск", "зима", "тайшет", "кропотк", "белореч", "большое голоустн",
]

# Чёрный список: однозначно НЕ Иркутская область (популярные «утечки» из парсеров).
_OUT_OF_REGION = [
    "москва", "санкт-петербург", "спб", "новосибирск", "красноярск",
    "екатеринбург", "казань", "омск", "челябинск", "уфа", "владивосток",
    "хабаровск", "сочи", "краснодар", "пермь", "тюмень", "томск", "кемерово",
    "улан-удэ", "чита", "якутск",
]


def _is_outside_region(location) -> bool:
    """Возвращает True, если location явно указывает на другой регион."""
    if not location or not isinstance(location, str):
        return False
    low = location.lower()
    if any(marker in low for marker in _OUT_OF_REGION):
        # Whitelist может «спасти» событие: «Москва — Иркутск выезд»
        if any(marker in low for marker in _REGION_WHITELIST):
            return False
        return True
    return False


_TITLE_NORMALIZE_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _normalize_title_for_dedup(title: str) -> str:
    """Ключ дедупа: lowercase, без пунктуации, схлопнутые пробелы, до 60 симв."""
    if not title:
        return ""
    cleaned = _TITLE_NORMALIZE_RE.sub(" ", title.lower())
    return " ".join(cleaned.split())[:60]


def _completeness_score(row: dict) -> int:
    """Чем больше непустых полей — тем «полнее» запись. Используем для выбора best-of-group."""
    score = 0
    for key in ("description", "image_url", "address", "time_start", "price_min", "url"):
        v = row.get(key)
        if v not in (None, "", 0):
            score += 1
    return score


def _dedup_events(rows: list[dict]) -> list[dict]:
    """Cross-source дедуп на чтении. Группирует по (нормализованный title, date_start),
    в каждой группе берёт самую полную запись и склеивает source_id остальных в also_at."""
    groups: dict[tuple[str, Any], list[dict]] = {}
    for row in rows:
        key = (_normalize_title_for_dedup(row.get("title", "")), row.get("date_start"))
        if not key[0]:
            groups.setdefault(("__no_key__", row.get("event_id")), []).append(row)
            continue
        groups.setdefault(key, []).append(row)

    merged: list[dict] = []
    for group in groups.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        primary = max(group, key=_completeness_score)
        primary_source = primary.get("source_id")
        also = sorted({
            r.get("source_id") for r in group
            if r.get("source_id") and r.get("source_id") != primary_source
        })
        primary = {**primary, "also_at": list(also)}
        merged.append(primary)
    return merged


@router.get("", response_model=list[Event])
async def get_events(
    data_svc: DataServiceDep,
    cache: CacheServiceDep,
    date_from: date | None = Query(None, description="Дата начала периода (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Дата конца периода (YYYY-MM-DD)"),
    source: str | None = Query(None, description="Источник данных (irk.ru, culture38.ru)"),
    limit: int = Query(100, ge=1, le=500, description="Максимум записей"),
    skip: int = Query(0, ge=0, description="Пропустить записей"),
):
    """Получить список событий из БД."""
    cache_key = f"events:{date_from}:{date_to}:{source}:{limit}:{skip}"
    cached = await cache.get(cache_key)
    if cached:
        return [Event(**e) for e in cached]

    try:
        # I-9: По умолчанию показываем только будущие события
        effective_date_from = date_from if date_from is not None else date.today()

        events_data = await data_svc.get_events(
            date_from=effective_date_from, date_to=date_to, source=source,
            limit=limit, skip=skip,
        )

        # I-4: Спам-фильтрация
        def _is_spam(title: str, description: str | None) -> bool:
            text = (title + " " + (description or "")).lower()
            return any(marker in text for marker in _SPAM_MARKERS)

        clean_rows = [
            row for row in events_data
            if not _is_spam(row.get("title", ""), row.get("description"))
            and not _is_outside_region(row.get("location"))
        ]
        deduped_rows = _dedup_events(clean_rows)
        result = [
            Event(
                event_id=row["event_id"],
                title=row["title"],
                description=row.get("description"),
                date_start=_parse_date(row.get("date_start")),
                date_end=_parse_date(row.get("date_end")),
                event_type=row.get("event_type"),
                location=row.get("location"),
                source_id=row.get("source_id", "unknown"),
                url=row.get("url"),
                time_start=row.get("time_start"),
                price_min=row.get("price_min"),
                price_max=row.get("price_max"),
                image_url=row.get("image_url"),
                address=row.get("address"),
                age_restriction=row.get("age_restriction"),
                also_at=row.get("also_at", []),
            )
            for row in deduped_rows
        ]
        await cache.set(cache_key, [e.model_dump() for e in result], ttl=120)
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении событий: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении событий")


def _parse_date(value) -> date | None:
    """Преобразовать значение даты в Python date."""
    from datetime import datetime, timedelta

    if value is None:
        return None

    if isinstance(value, int):
        return (datetime(1970, 1, 1) + timedelta(days=value)).date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    return None


@router.post("/refresh", dependencies=[Depends(verify_api_key)])
async def refresh_events(data_svc: DataServiceDep, days_ahead: int = Query(7, description="Количество дней для поиска событий")) -> dict[str, Any]:
    """Обновить данные о событиях из источников."""
    total_added = 0
    sources = []
    errors = []

    await data_svc.create_events_table()

    try:
        raw_irk = await fetch_events_irk(days_ahead=days_ahead)
        events_irk = _parse_irk_events(raw_irk)
        inserted = await data_svc.upsert_events_batch(events_irk)
        total_added += inserted
        if inserted > 0:
            sources.append(f"irk.ru ({inserted})")
    except Exception as e:
        errors.append(f"irk.ru: {str(e)}")
        logger.error(f"Ошибка при обновлении событий с irk.ru: {e}")

    try:
        raw_culture38 = await fetch_events_culture38(days_ahead=days_ahead)
        events_culture38 = _parse_culture38_events(raw_culture38)
        inserted = await data_svc.upsert_events_batch(events_culture38)
        total_added += inserted
        if inserted > 0:
            sources.append(f"culture38.ru ({inserted})")
    except Exception as e:
        errors.append(f"culture38.ru: {str(e)}")
        logger.error(f"Ошибка при обновлении событий с culture38.ru: {e}")

    return {
        "total_added": total_added,
        "sources": sources,
        "errors": errors,
        "days_ahead": days_ahead,
    }


def _parse_irk_events(raw_events: list[dict]) -> list[dict]:
    """Преобразовать сырые данные irk.ru в формат для БД."""
    import hashlib

    events = []
    for raw in raw_events:
        try:
            title = raw.get("title", "")
            if not title:
                continue

            event_date = raw.get("date_parsed", str(date.today()))
            event_type = raw.get("event_type", "event")
            url = raw.get("url", "")

            content = f"irk_{event_date}_{title}"
            event_id = f"irk_{hashlib.md5(content.encode()).hexdigest()[:12]}"

            events.append({
                "id": event_id,
                "title": title,
                "description": raw.get("date", ""),
                "date_start": event_date,
                "date_end": None,
                "event_type": event_type,
                "location": raw.get("location", ""),
                "source": "irk.ru",
                "url": url,
            })
        except Exception as e:
            logger.warning(f"Ошибка парсинга события irk.ru: {e}")
    return events


def _parse_culture38_events(raw_events: list[dict]) -> list[dict]:
    """Преобразовать сырые данные culture38.ru в формат для БД."""
    from datetime import datetime
    events = []
    for raw in raw_events:
        try:
            date_str = raw.get("date", "")
            event_date = datetime.strptime(date_str, "%d.%m.%Y").date() if date_str else date.today()
            title = raw.get("title", "")
            id_hash = hashlib.md5(f"{date_str}_{title}".encode()).hexdigest()[:12]

            events.append({
                "id": f"culture38_{id_hash}",
                "title": title,
                "description": raw.get("description", ""),
                "date_start": str(event_date),
                "date_end": None,
                "event_type": raw.get("event_type", "culture"),
                "location": raw.get("location", ""),
                "source": "culture38",
                "url": raw.get("url", ""),
            })
        except Exception as e:
            logger.warning(f"Ошибка парсинга события culture38.ru: {e}")
    return events


@router.post("/fetch/major", dependencies=[Depends(verify_api_key)])
async def fetch_major_events(data_svc: DataServiceDep) -> dict[str, Any]:
    """Загрузить крупные события Прибайкалья (вручную собранные).

    Включает: Olkhon Ice Fest, Ёрдынские игры, Звёзды на Байкале,
    выставки СибЭкспоЦентр и другие значимые события 2025-2026.
    """
    await data_svc.create_events_table()

    try:
        major_events = get_major_events_2025_2026()
        school_holidays = get_school_holidays_2025_2026()
        all_events = major_events + school_holidays

        events_batch = []
        for e in all_events:
            events_batch.append({
                "id": e["id"],
                "title": e["title"],
                "description": e.get("description", ""),
                "date_start": e["date_start"],
                "date_end": e.get("date_end"),
                "event_type": e.get("event_type", "event"),
                "location": e.get("location", ""),
                "source": e.get("source", "manual"),
                "url": e.get("url", ""),
            })

        inserted = await data_svc.upsert_events_batch(events_batch)

        return {
            "status": "ok",
            "major_events": len(major_events),
            "school_holidays": len(school_holidays),
            "total_found": len(all_events),
            "events_inserted": inserted,
            "events_by_type": _count_by_type(all_events),
            "events_sample": [
                {
                    "date": e["date_start"],
                    "title": e["title"][:60],
                    "type": e.get("event_type", "event"),
                    "impact": e.get("impact", "medium"),
                }
                for e in all_events[:10]
            ],
        }
    except Exception as e:
        logger.error(f"Ошибка загрузки major событий: {e}")
        raise HTTPException(500, "Ошибка загрузки событий. Проверьте логи.")


def _count_by_type(events: list) -> dict[str, int]:
    """Подсчитать события по типам."""
    counts: dict[str, int] = {}
    for e in events:
        t = e.get("event_type", "event")
        counts[t] = counts.get(t, 0) + 1
    return counts
