"""PostgreSQL сервис данных."""
import logging
from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Event, Forecast, Hotel, HotelStatistic
from app.db.session import async_session
from app.models.schemas import Hotel as HotelSchema
from app.models.schemas import HotelStatistics as HotelStatsSchema

logger = logging.getLogger(__name__)


class DBService:
    """PostgreSQL-сервис данных."""

    def __init__(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        from app.db.session import engine
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            self._connected = True
            logger.info("PostgreSQL connected successfully")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            self._connected = False

    async def close(self) -> None:
        from app.db.session import engine
        await engine.dispose()
        self._connected = False

    async def get_hotel_by_id(self, hotel_id: str) -> HotelSchema | None:
        """Получить один отель по ID."""
        async with async_session() as s:
            row = (await s.execute(select(Hotel).where(Hotel.id == hotel_id))).scalar_one_or_none()
            if not row:
                return None
            return HotelSchema(
                id=row.id, name=row.name, city=row.city,
                district=row.district, lat=row.lat, lon=row.lon,
                rating=row.rating, min_price=getattr(row, "min_price", None),
                accommodation_type=row.accommodation_type,
                tripadvisor_rating=row.tripadvisor_rating,
                tripadvisor_reviews=row.tripadvisor_reviews,
                tripadvisor_url=row.tripadvisor_url,
                image_url=row.image_url,
            )

    async def get_hotels(
        self, city: str | None = None, district: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> tuple[list[HotelSchema], int]:
        """Возвращает (список отелей, общее количество)."""
        async with async_session() as s:
            q = select(Hotel)
            count_q = select(func.count()).select_from(Hotel)
            if city:
                q = q.where(Hotel.city == city)
                count_q = count_q.where(Hotel.city == city)
            if district:
                q = q.where(Hotel.district == district)
                count_q = count_q.where(Hotel.district == district)
            total = (await s.execute(count_q)).scalar() or 0
            q = q.offset(offset).limit(limit)
            rows = (await s.execute(q)).scalars().all()
            items = [
                HotelSchema(
                    id=r.id,
                    name=r.name,
                    city=r.city,
                    district=r.district,
                    lat=r.lat,
                    lon=r.lon,
                    rating=r.rating,
                    min_price=getattr(r, "min_price", None),
                    accommodation_type=r.accommodation_type,
                    tripadvisor_rating=r.tripadvisor_rating,
                    tripadvisor_reviews=r.tripadvisor_reviews,
                    tripadvisor_url=r.tripadvisor_url,
                    image_url=r.image_url,
                )
                for r in rows
            ]
            return items, total

    async def get_hotel_statistics(
        self,
        hotel_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[HotelStatsSchema]:
        async with async_session() as s:
            q = select(HotelStatistic)
            if hotel_id:
                q = q.where(HotelStatistic.id == hotel_id)
            if date_from:
                q = q.where(HotelStatistic.date >= date_from)
            if date_to:
                q = q.where(HotelStatistic.date <= date_to)
            q = q.order_by(HotelStatistic.date)
            rows = (await s.execute(q)).scalars().all()
            return [
                HotelStatsSchema(
                    id=r.id,
                    date=r.date,
                    rooms_num=r.rooms_num or 0,
                    free_rooms_amount=r.free_rooms_amount or 0,
                    available_rooms_percent=r.available_rooms_percent or 0.0,
                    min_price=r.min_price,
                    max_capacity=r.max_capacity,
                )
                for r in rows
            ]

    async def get_events(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        source: str | None = None,
        city: str | None = None,
        limit: int = 200,
        skip: int = 0,
    ) -> list[dict]:
        async with async_session() as s:
            q = select(Event)
            if date_from:
                q = q.where(Event.date_start >= date_from)
            if date_to:
                q = q.where(Event.date_start <= date_to)
            if source:
                q = q.where(Event.source_id == source)
            if city:
                escaped_city = city.replace('%', r'\%').replace('_', r'\_')
                q = q.where(Event.location.ilike(f"%{escaped_city}%"))
            q = q.order_by(func.abs(Event.date_start - func.current_date())).offset(skip).limit(limit)
            rows = (await s.execute(q)).scalars().all()
            return [
                {
                    "event_id": r.event_id,
                    "title": r.title,
                    "description": r.description[:300] if r.description else None,
                    "date_start": r.date_start,
                    "date_end": r.date_end,
                    "event_type": r.event_type,
                    "location": r.location,
                    "source_id": r.source_id,
                    "url": r.url,
                    "time_start": r.time_start,
                    "price_min": r.price_min,
                    "price_max": r.price_max,
                    "image_url": r.image_url,
                    "address": r.address,
                    "age_restriction": r.age_restriction,
                }
                for r in rows
            ]

    async def create_events_table(self) -> bool:
        return True

    async def get_events_by_district(
        self,
        district: str,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Получить события, привязанные к району через CITY_TO_DISTRICT (substring-match).

        Логика:
        1. Находим все города этого района из CITY_TO_DISTRICT.
        2. Берём события, где location/address содержит подстроку города → флаг geo_inferred=True.
        3. Берём события без location/address → флаг geo_inferred=False (общерегиональные).
        4. Объединяем оба списка в одном вызове.

        Returns:
            list[dict] — те же поля что get_events + `geo_inferred: bool`.
        """
        from app.constants import CITY_TO_DISTRICT

        cities = [c for c, d in CITY_TO_DISTRICT.items() if d == district]
        if not cities:
            logger.warning("get_events_by_district: район %r не имеет городов в CITY_TO_DISTRICT", district)
            return []

        # Подстроки: и сам район, и каждый город (lowercase для ILIKE)
        patterns = [f"%{district.lower()}%"] + [f"%{c.lower()}%" for c in cities]

        async with async_session() as s:
            q_text = """
                SELECT
                    event_id, title, description, date_start, date_end,
                    event_type, location, source_id, url, time_start,
                    price_min, price_max, image_url, address, age_restriction,
                    CASE
                        WHEN location IS NULL AND address IS NULL THEN false
                        ELSE true
                    END AS has_geo
                FROM events
                WHERE 1=1
            """
            params: dict = {}
            if date_from:
                q_text += " AND date_start >= :date_from"
                params["date_from"] = date_from
            if date_to:
                q_text += " AND date_start <= :date_to"
                params["date_to"] = date_to
            q_text += """
                AND (
                    location IS NULL AND address IS NULL
                    OR EXISTS (
                        SELECT 1 FROM unnest(CAST(:patterns AS text[])) AS p
                        WHERE LOWER(COALESCE(location, '')) LIKE p
                           OR LOWER(COALESCE(address, '')) LIKE p
                    )
                )
                ORDER BY ABS(date_start - CURRENT_DATE)
                LIMIT :limit
            """
            params["patterns"] = patterns
            params["limit"] = limit
            result = await s.execute(text(q_text), params)
            rows = result.mappings().all()

        out: list[dict] = []
        for r in rows:
            loc = (r["location"] or "").lower()
            addr = (r["address"] or "").lower()
            district_lower = district.lower()
            geo_inferred = False
            if r["has_geo"]:
                # True если location/address содержит подстроку района или одного из его городов
                for pattern in [district_lower] + [c.lower() for c in cities]:
                    if pattern in loc or pattern in addr:
                        geo_inferred = True
                        break
            out.append({
                "event_id": r["event_id"],
                "title": r["title"],
                "description": (r["description"] or "")[:300] if r["description"] else None,
                "date_start": r["date_start"],
                "date_end": r["date_end"],
                "event_type": r["event_type"],
                "location": r["location"],
                "source_id": r["source_id"],
                "url": r["url"],
                "time_start": r["time_start"],
                "price_min": r["price_min"],
                "price_max": r["price_max"],
                "image_url": r["image_url"],
                "address": r["address"],
                "age_restriction": r["age_restriction"],
                "geo_inferred": geo_inferred,
            })
        return out

    async def get_occupancy_by_district(
        self,
        district: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        """Средняя занятость по району на каждый день.

        Phase 6: weighted occupancy = 100 * SUM(rooms - free) / SUM(rooms).
        Старая семантика была AVG((100 - available_percent)) — равные веса для каждого отеля,
        что искажает картину в гетерогенных районах (1 хостел на 5 мест vs 1 база на 80 мест).
        Новая — взвешена по физическому inventory'ю, что соответствует STR-методологии.

        Дополнительно: clip percent в [0, 100] перед расчётом (защита от outliers парсера,
        когда available_rooms_percent может выйти за границы из-за rooms_num != sum(rooms.free)).
        """
        async with async_session() as s:
            q_text = """
                WITH clean AS (
                    SELECT
                        hs.date,
                        hs.rooms_num,
                        LEAST(100.0, GREATEST(0.0, COALESCE(hs.available_rooms_percent, 0))) AS available_pct,
                        hs.min_price,
                        hs.max_capacity
                    FROM hotel_statistics hs
                    JOIN hotels h ON h.id = hs.id
                    WHERE h.district = :district
                      AND hs.rooms_num > 0
            """
            params: dict = {"district": district}
            if date_from:
                q_text += " AND hs.date >= :date_from"
                params["date_from"] = date_from
            if date_to:
                q_text += " AND hs.date <= :date_to"
                params["date_to"] = date_to
            q_text += """
                )
                SELECT
                    date,
                    -- Weighted occupancy: SUM(occupied_rooms) / SUM(total_rooms) * 100
                    -- occupied_rooms = rooms_num * (1 - available_pct/100) = rooms_num - rooms_num*available_pct/100
                    100.0 * SUM(rooms_num - rooms_num * available_pct / 100.0)
                        / NULLIF(SUM(rooms_num), 0) AS avg_occupancy,
                    AVG(min_price) FILTER (WHERE min_price > 0) AS avg_price,
                    SUM(rooms_num) AS total_rooms,
                    SUM(max_capacity) AS total_capacity
                FROM clean
                GROUP BY date
                ORDER BY date
            """
            result = await s.execute(text(q_text), params)
            return [
                {
                    "date": row.date,
                    "avg_occupancy": round(float(row.avg_occupancy), 1) if row.avg_occupancy is not None else 0.0,
                    "avg_price": round(float(row.avg_price)) if row.avg_price else None,
                    "total_rooms": int(row.total_rooms) if row.total_rooms is not None else None,
                    "total_capacity": int(row.total_capacity) if row.total_capacity is not None else None,
                }
                for row in result
                if row.avg_occupancy is not None
            ]

    async def get_monthly_statistics(self, year: int | None = None) -> list[dict]:
        """Месячная агрегация. Phase 6: weighted occupancy (как в get_occupancy_by_district)."""
        async with async_session() as s:
            q_text = """
                WITH clean AS (
                    SELECT
                        date,
                        rooms_num,
                        free_rooms_amount,
                        LEAST(100.0, GREATEST(0.0, COALESCE(available_rooms_percent, 0))) AS available_pct,
                        min_price
                    FROM hotel_statistics
                    WHERE date IS NOT NULL AND rooms_num > 0
            """
            params: dict = {}
            if year:
                q_text += " AND EXTRACT(YEAR FROM date) = :year"
                params["year"] = year
            q_text += """
                )
                SELECT
                    EXTRACT(YEAR FROM date)::int AS year,
                    EXTRACT(MONTH FROM date)::int AS month,
                    100.0 * SUM(rooms_num - rooms_num * available_pct / 100.0)
                        / NULLIF(SUM(rooms_num), 0) AS avg_occupancy,
                    AVG(min_price) FILTER (WHERE min_price > 0) AS avg_price,
                    SUM(rooms_num) AS total_rooms,
                    SUM(free_rooms_amount) AS free_rooms,
                    COUNT(*) AS records_count
                FROM clean
                GROUP BY 1, 2 ORDER BY 1, 2
            """
            result = await s.execute(text(q_text), params)
            return [
                {
                    "date_str": f"{int(r.year)}-{int(r.month):02d}",
                    "avg_occupancy": round(float(r.avg_occupancy or 0), 1),
                    "avg_price": round(float(r.avg_price or 0)),
                    "total_rooms": int(r.total_rooms or 0),
                    "free_rooms": int(r.free_rooms or 0),
                    "records_count": int(r.records_count or 0),
                }
                for r in result
            ]

    async def get_events_by_month(self, year: int | None = None) -> list[dict]:
        async with async_session() as s:
            q_text = """
                SELECT
                    EXTRACT(YEAR FROM date_start)::int AS year,
                    EXTRACT(MONTH FROM date_start)::int AS month,
                    COUNT(*) AS events_count
                FROM events
                WHERE date_start IS NOT NULL
            """
            params: dict = {}
            if year:
                q_text += " AND EXTRACT(YEAR FROM date_start) = :year"
                params["year"] = year
            q_text += " GROUP BY 1, 2 ORDER BY 1, 2"
            result = await s.execute(text(q_text), params)
            return [
                {"date_str": f"{int(r.year)}-{int(r.month):02d}", "events_count": int(r.events_count)}
                for r in result
            ]

    def _to_date(self, value) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _clean_location(loc: str | None) -> str | None:
        if not loc:
            return None
        loc = loc.strip()
        if len(loc) < 3 or len(loc) > 200:
            return None
        garbage = ["не могут", "индивидуальное предприятие", "http", "«\""]
        if any(g in loc.lower() for g in garbage):
            return None
        return loc

    async def insert_event(self, event: dict) -> bool:
        ds = self._to_date(event.get("date_start"))
        if not ds:
            return False
        eid = event.get("event_id") or event.get("id")
        if not eid:
            logger.warning("Skipping event without ID: %s", event.get("title", "unknown"))
            return False
        async with async_session() as s:
            try:
                ins = pg_insert(Event).values(
                    event_id=eid,
                    title=event.get("title", ""),
                    description=event.get("description"),
                    date_start=ds,
                    date_end=self._to_date(event.get("date_end")),
                    event_type=event.get("event_type"),
                    location=self._clean_location(event.get("location")),
                    source_id=event.get("source_id", event.get("source", "")),
                    url=event.get("url"),
                    time_start=event.get("time_start"),
                    price_min=event.get("price_min"),
                    price_max=event.get("price_max"),
                    image_url=event.get("image_url"),
                    address=event.get("address"),
                    age_restriction=event.get("age_restriction"),
                )
                stmt = ins.on_conflict_do_update(
                    index_elements=["event_id"],
                    set_={
                        "title": ins.excluded.title,
                        "description": ins.excluded.description,
                        "date_start": ins.excluded.date_start,
                        "date_end": ins.excluded.date_end,
                        "event_type": ins.excluded.event_type,
                        "location": ins.excluded.location,
                        "url": ins.excluded.url,
                        "source_id": ins.excluded.source_id,
                        "time_start": ins.excluded.time_start,
                        "price_min": ins.excluded.price_min,
                        "price_max": ins.excluded.price_max,
                        "image_url": ins.excluded.image_url,
                        "address": ins.excluded.address,
                        "age_restriction": ins.excluded.age_restriction,
                    },
                )
                await s.execute(stmt)
                await s.commit()
                return True
            except Exception as e:
                logger.error(f"Insert event error: {e}")
                await s.rollback()
                return False

    def _build_event_row(self, ev: dict | Any) -> dict | None:
        """Преобразует входящий dict/ParsedEvent парсера в row для INSERT/UPSERT events.

        Принимает как dict (путь /api/parser/events/{src}), так и Pydantic-модель
        ParsedEvent (путь scheduler.collect_events). Без конверсии ParsedEvent.get()
        бросал бы AttributeError, и весь batch-upsert падал бы → 0 сохранённых событий.

        Args:
            ev: Словарь или ParsedEvent с данными события от парсера.

        Returns:
            Словарь с полями для вставки, или None если event_id/date_start отсутствуют.
        """
        if not isinstance(ev, dict):
            if hasattr(ev, "model_dump"):
                ev = ev.model_dump()
            else:
                return None
        ds = self._to_date(ev.get("date_start"))
        eid = ev.get("event_id") or ev.get("id")
        if not ds or not eid:
            return None
        return {
            "event_id": eid,
            "title": ev.get("title", ""),
            "description": ev.get("description"),
            "date_start": ds,
            "date_end": self._to_date(ev.get("date_end")),
            "event_type": ev.get("event_type"),
            "location": self._clean_location(ev.get("location")),
            "source_id": ev.get("source_id", ev.get("source", "")),
            "url": ev.get("url"),
            "time_start": ev.get("time_start"),
            "price_min": ev.get("price_min"),
            "price_max": ev.get("price_max"),
            "image_url": ev.get("image_url"),
            "address": ev.get("address"),
            "age_restriction": ev.get("age_restriction"),
        }

    async def insert_events_batch(self, events: list[dict]) -> int:
        rows = []
        for ev in events:
            row = self._build_event_row(ev)
            if row:
                rows.append(row)
        if not rows:
            return 0
        async with async_session() as s:
            try:
                ins = pg_insert(Event).values(rows)
                stmt = ins.on_conflict_do_update(
                    index_elements=["event_id"],
                    set_={
                        "title": ins.excluded.title,
                        "description": ins.excluded.description,
                        "date_start": ins.excluded.date_start,
                        "date_end": ins.excluded.date_end,
                        "event_type": ins.excluded.event_type,
                        "location": ins.excluded.location,
                        "url": ins.excluded.url,
                        "source_id": ins.excluded.source_id,
                        "time_start": ins.excluded.time_start,
                        "price_min": ins.excluded.price_min,
                        "price_max": ins.excluded.price_max,
                        "image_url": ins.excluded.image_url,
                        "address": ins.excluded.address,
                        "age_restriction": ins.excluded.age_restriction,
                    },
                )
                await s.execute(stmt)
                await s.commit()
                return len(rows)
            except Exception as e:
                logger.error(f"Batch insert events error: {e}")
                await s.rollback()
                return 0

    async def upsert_events_batch(self, events: Sequence[dict | Any]) -> int:
        """Вставить или обновить события с дедупликацией по (source_id, date_start, title).

        Принимает dict или ParsedEvent (конверсия в _build_event_row).

        Uses ON CONFLICT ON CONSTRAINT uq_events_dedup — корректно обрабатывает
        повторные запуски парсеров без создания дублей.

        Args:
            events: Список словарей с данными событий.

        Returns:
            Количество обработанных (не отброшенных при валидации) строк.
        """
        rows = []
        for ev in events:
            row = self._build_event_row(ev)
            if row:
                rows.append(row)
        if not rows:
            return 0
        async with async_session() as s:
            try:
                ins = pg_insert(Event).values(rows)
                stmt = ins.on_conflict_do_update(
                    constraint="uq_events_dedup",
                    set_={
                        "description": func.coalesce(ins.excluded.description, Event.__table__.c.description),
                        "event_type": func.coalesce(ins.excluded.event_type, Event.__table__.c.event_type),
                        "location": func.coalesce(ins.excluded.location, Event.__table__.c.location),
                        "url": func.coalesce(ins.excluded.url, Event.__table__.c.url),
                        "time_start": func.coalesce(ins.excluded.time_start, Event.__table__.c.time_start),
                        "price_min": func.coalesce(ins.excluded.price_min, Event.__table__.c.price_min),
                        "price_max": func.coalesce(ins.excluded.price_max, Event.__table__.c.price_max),
                        "image_url": func.coalesce(ins.excluded.image_url, Event.__table__.c.image_url),
                        "address": func.coalesce(ins.excluded.address, Event.__table__.c.address),
                        "age_restriction": func.coalesce(ins.excluded.age_restriction, Event.__table__.c.age_restriction),
                        "updated_at": func.now(),
                    },
                )
                await s.execute(stmt)
                await s.commit()
                return len(rows)
            except Exception as e:
                logger.error(f"Batch upsert events error: {e}")
                await s.rollback()
                return 0

    async def upsert_event(
        self,
        *,
        event_id: str,
        title: str,
        date_start: date,
        source_id: str,
        description: str | None = None,
        date_end: date | None = None,
        event_type: str | None = None,
        location: str | None = None,
        url: str | None = None,
        time_start: time | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        image_url: str | None = None,
        address: str | None = None,
        age_restriction: str | None = None,
    ) -> bool:
        """Вставить или обновить событие с дедупликацией по (source_id, date_start, title).

        Args:
            event_id: Уникальный идентификатор события.
            title: Название события.
            date_start: Дата начала.
            source_id: Идентификатор источника.
            description: Описание события.
            date_end: Дата окончания.
            event_type: Тип события.
            location: Место проведения.
            url: Ссылка на событие.
            time_start: Время начала.
            price_min: Минимальная цена.
            price_max: Максимальная цена.
            image_url: URL изображения.
            address: Физический адрес.
            age_restriction: Возрастное ограничение.

        Returns:
            True если операция успешна, False при ошибке или отсутствии соединения.
        """
        if not self.is_connected:
            return False
        try:
            async with async_session() as s:
                ins = pg_insert(Event).values(
                    event_id=event_id,
                    title=title,
                    description=description,
                    date_start=date_start,
                    date_end=date_end,
                    event_type=event_type,
                    location=self._clean_location(location),
                    source_id=source_id,
                    url=url,
                    time_start=time_start,
                    price_min=price_min,
                    price_max=price_max,
                    image_url=image_url,
                    address=address,
                    age_restriction=age_restriction,
                )
                stmt = ins.on_conflict_do_update(
                    constraint="uq_events_dedup",
                    set_={
                        "description": func.coalesce(ins.excluded.description, Event.__table__.c.description),
                        "event_type": func.coalesce(ins.excluded.event_type, Event.__table__.c.event_type),
                        "location": func.coalesce(ins.excluded.location, Event.__table__.c.location),
                        "url": func.coalesce(ins.excluded.url, Event.__table__.c.url),
                        "time_start": func.coalesce(ins.excluded.time_start, Event.__table__.c.time_start),
                        "price_min": func.coalesce(ins.excluded.price_min, Event.__table__.c.price_min),
                        "price_max": func.coalesce(ins.excluded.price_max, Event.__table__.c.price_max),
                        "image_url": func.coalesce(ins.excluded.image_url, Event.__table__.c.image_url),
                        "address": func.coalesce(ins.excluded.address, Event.__table__.c.address),
                        "age_restriction": func.coalesce(ins.excluded.age_restriction, Event.__table__.c.age_restriction),
                        "updated_at": func.now(),
                    },
                )
                await s.execute(stmt)
                await s.commit()
            return True
        except Exception as exc:
            logger.error("upsert_event failed for %s: %s", event_id, exc)
            return False

    async def delete_event_by_id(self, event_id: str) -> bool:
        """Удалить событие по первичному ключу event_id.

        Args:
            event_id: Идентификатор события для удаления.

        Returns:
            True если операция успешна, False при ошибке или отсутствии соединения.
        """
        if not self.is_connected:
            return False
        try:
            async with async_session() as s:
                await s.execute(
                    delete(Event).where(Event.event_id == event_id)
                )
                await s.commit()
            return True
        except Exception as exc:
            logger.error("delete_event_by_id failed for %s: %s", event_id, exc)
            return False

    async def delete_events_by_source(self, source: str) -> int:
        async with async_session() as s:
            try:
                result = await s.execute(
                    delete(Event).where(Event.source_id == source)
                )
                await s.commit()
                return result.rowcount
            except Exception:
                await s.rollback()
                raise

    async def save_hotels(self, hotels: list[dict]) -> int:
        if not hotels:
            return 0
        rows = []
        for h in hotels:
            hid = h.get("id")
            hname = h.get("name")
            if not hid or not hname:
                logger.warning(f"Пропущен отель без id/name: {h}")
                continue
            rows.append({
                "id": hid,
                "name": hname,
                "city": h.get("city", ""),
                "district": h.get("district"),
                "lat": h.get("lat"),
                "lon": h.get("lon"),
                "rating": h.get("rating"),
                "min_price": h.get("min_price"),
                "image_url": h.get("image_url"),
                "accommodation_type": h.get("accommodation_type"),
            })
        if not rows:
            return 0
        async with async_session() as s:
            try:
                stmt = pg_insert(Hotel).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "name": stmt.excluded.name,
                        "city": stmt.excluded.city,
                        "district": stmt.excluded.district,
                        "lat": stmt.excluded.lat,
                        "lon": stmt.excluded.lon,
                        "rating": stmt.excluded.rating,
                        "min_price": stmt.excluded.min_price,
                        "image_url": func.coalesce(stmt.excluded.image_url, Hotel.__table__.c.image_url),
                        "accommodation_type": func.coalesce(
                            stmt.excluded.accommodation_type,
                            Hotel.__table__.c.accommodation_type,
                        ),
                    },
                )
                await s.execute(stmt)
                await s.commit()
                return len(rows)
            except Exception:
                await s.rollback()
                raise

    async def save_statistics(self, stats: list[dict]) -> int:
        if not stats:
            return 0
        rows = []
        for st in stats:
            sid = st.get("id")
            sdate = st.get("date")
            if not sid or not sdate:
                logger.warning(f"Пропущена статистика без id/date: {st}")
                continue
            rows.append({
                "id": sid,
                "date": sdate,
                "rooms_num": st.get("rooms_num"),
                "free_rooms_amount": st.get("free_rooms_amount"),
                "available_rooms_percent": st.get("available_rooms_percent"),
                "min_price": st.get("min_price"),
                "max_capacity": st.get("max_capacity"),
            })
        if not rows:
            return 0
        async with async_session() as s:
            try:
                stmt = pg_insert(HotelStatistic).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id", "date"],
                    set_={
                        "rooms_num": stmt.excluded.rooms_num,
                        "free_rooms_amount": stmt.excluded.free_rooms_amount,
                        "available_rooms_percent": stmt.excluded.available_rooms_percent,
                        "min_price": stmt.excluded.min_price,
                        "max_capacity": stmt.excluded.max_capacity,
                    },
                )
                await s.execute(stmt)
                await s.commit()
                return len(rows)
            except Exception:
                await s.rollback()
                raise

    async def get_total_metrics(self) -> dict:
        async with async_session() as s:
            combined = text("""
                SELECT
                    (SELECT count(*) FROM hotels) AS hotels_count,
                    (SELECT count(DISTINCT city) FROM hotels) AS cities_count,
                    (SELECT count(*) FROM events) AS events_count,
                    COALESCE(s.total_rooms, 0) AS total_rooms,
                    COALESCE(s.free_rooms, 0) AS free_rooms,
                    COALESCE(s.avg_avail, 0) AS avg_avail
                FROM (
                    SELECT
                        sum(rooms_num) AS total_rooms,
                        sum(free_rooms_amount) AS free_rooms,
                        avg(available_rooms_percent) AS avg_avail
                    FROM hotel_statistics
                    WHERE date = (SELECT max(date) FROM hotel_statistics)
                ) s
            """)
            row = (await s.execute(combined)).one_or_none()

            if not row:
                return {
                    "total_hotels": 0, "total_cities": 0, "total_events": 0,
                    "total_rooms": 0, "free_rooms": 0, "avg_occupancy": 0.0,
                }

            return {
                "total_hotels": int(row.hotels_count or 0),
                "total_cities": int(row.cities_count or 0),
                "total_events": int(row.events_count or 0),
                "total_rooms": int(row.total_rooms or 0),
                "free_rooms": int(row.free_rooms or 0),
                "avg_occupancy": round(100.0 - float(row.avg_avail or 0), 1),
            }

    async def get_districts_statistics(self) -> list[dict]:
        async with async_session() as s:
            q = text("""
                SELECT
                    h.district,
                    AVG(100.0 - hs.available_rooms_percent) AS avg_occupancy,
                    SUM(hs.free_rooms_amount) AS free_rooms,
                    SUM(hs.rooms_num) AS total_rooms,
                    AVG(hs.min_price) AS avg_price,
                    COUNT(DISTINCT h.id) AS hotels_count
                FROM hotels h
                JOIN hotel_statistics hs ON h.id = hs.id
                WHERE hs.date = (SELECT MAX(date) FROM hotel_statistics)
                GROUP BY h.district
                ORDER BY avg_occupancy DESC
            """)
            result = await s.execute(q)
            return [
                {
                    "district": row.district or "Неизвестный",
                    "hotels_count": int(row.hotels_count),
                    "total_rooms": int(row.total_rooms or 0),
                    "free_rooms": int(row.free_rooms or 0),
                    "avg_occupancy": round(float(row.avg_occupancy or 0), 1),
                    "avg_price": round(float(row.avg_price or 0)),
                }
                for row in result
            ]

    async def get_hotels_by_city(self) -> list[dict]:
        async with async_session() as s:
            q = (
                select(Hotel.city, func.count().label("hotels_count"))
                .group_by(Hotel.city)
                .order_by(func.count().desc())
            )
            rows = (await s.execute(q)).all()
            return [{"city": r.city, "hotels_count": r.hotels_count} for r in rows]

    async def get_hotels_by_district(self) -> list[dict]:
        async with async_session() as s:
            q = (
                select(
                    Hotel.district,
                    func.count().label("hotels_count"),
                    func.avg(Hotel.rating).label("avg_rating"),
                )
                .group_by(Hotel.district)
                .order_by(func.count().desc())
            )
            rows = (await s.execute(q)).all()
            return [
                {
                    "district": r.district or "—",
                    "hotels_count": r.hotels_count,
                    "avg_rating": round(float(r.avg_rating), 2) if r.avg_rating else None,
                }
                for r in rows
            ]

    async def get_latest_hotel_stats(self) -> dict[str, dict]:
        """Последняя статистика номеров по каждому отелю (rooms, free, capacity)."""
        async with async_session() as s:
            latest_date = select(func.max(HotelStatistic.date)).scalar_subquery()
            q = select(
                HotelStatistic.id,
                HotelStatistic.rooms_num,
                HotelStatistic.free_rooms_amount,
                HotelStatistic.max_capacity,
            ).where(HotelStatistic.date == latest_date)
            rows = (await s.execute(q)).all()
            return {
                r.id: {
                    "rooms_num": r.rooms_num or 0,
                    "free_rooms": r.free_rooms_amount or 0,
                    "max_capacity": r.max_capacity or 0,
                }
                for r in rows
            }

    async def get_hotel_stats_on_date(
        self, target_date: date, strict: bool = False
    ) -> dict[str, dict]:
        """Статистика номеров по каждому отелю на конкретную дату (rooms, free, capacity).

        По умолчанию (strict=False) если на target_date нет наблюдений —
        возвращает срез на ближайший предшествующий день, иначе пустой словарь.
        Симметрично get_latest_hotel_stats при target_date == max(date).

        strict=True — только записи строго за target_date, без fallback'а.
        Используется когда вызывающий код хочет честно сказать «за эту дату
        нет данных» вместо подмены результатами с другой даты."""
        async with async_session() as s:
            if strict:
                q = select(
                    HotelStatistic.id,
                    HotelStatistic.rooms_num,
                    HotelStatistic.free_rooms_amount,
                    HotelStatistic.max_capacity,
                ).where(HotelStatistic.date == target_date)
            else:
                chosen_date_q = (
                    select(func.max(HotelStatistic.date))
                    .where(HotelStatistic.date <= target_date)
                    .scalar_subquery()
                )
                q = select(
                    HotelStatistic.id,
                    HotelStatistic.rooms_num,
                    HotelStatistic.free_rooms_amount,
                    HotelStatistic.max_capacity,
                ).where(HotelStatistic.date == chosen_date_q)
            rows = (await s.execute(q)).all()
            return {
                r.id: {
                    "rooms_num": r.rooms_num or 0,
                    "free_rooms": r.free_rooms_amount or 0,
                    "max_capacity": r.max_capacity or 0,
                }
                for r in rows
            }

    async def get_districts_statistics_in_period(
        self,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Агрегаты по районам в произвольном диапазоне дат.

        Усреднение Occupancy и avg_price выполняется по всем снимкам периода;
        free_rooms/total_rooms берутся как средние per-day, чтобы цифры не
        умножались на длину окна."""
        async with async_session() as s:
            q = text("""
                SELECT
                    h.district,
                    AVG(100.0 - hs.available_rooms_percent) AS avg_occupancy,
                    AVG(hs.free_rooms_amount) AS free_rooms_avg,
                    AVG(hs.rooms_num) AS total_rooms_avg,
                    AVG(hs.min_price) AS avg_price,
                    COUNT(DISTINCT h.id) AS hotels_count
                FROM hotels h
                JOIN hotel_statistics hs ON h.id = hs.id
                WHERE hs.date BETWEEN :date_from AND :date_to
                GROUP BY h.district
                ORDER BY avg_occupancy DESC NULLS LAST
            """)
            result = await s.execute(q, {"date_from": date_from, "date_to": date_to})
            return [
                {
                    "district": row.district or "Неизвестный",
                    "hotels_count": int(row.hotels_count),
                    "total_rooms": int(round(row.total_rooms_avg or 0)),
                    "free_rooms": int(round(row.free_rooms_avg or 0)),
                    "avg_occupancy": round(float(row.avg_occupancy or 0), 1),
                    "avg_price": round(float(row.avg_price or 0)),
                }
                for row in result
            ]

    async def update_hotel_metadata(
        self,
        hotel_id: str,
        tripadvisor_rating: float | None = None,
        tripadvisor_reviews: int | None = None,
        tripadvisor_url: str | None = None,
        image_url: str | None = None,
        accommodation_type: str | None = None,
    ) -> bool:
        """Обновить метаданные отеля (TripAdvisor cross-reference)."""
        async with async_session() as s:
            try:
                hotel = await s.get(Hotel, hotel_id)
                if not hotel:
                    return False
                if tripadvisor_rating is not None:
                    hotel.tripadvisor_rating = tripadvisor_rating
                if tripadvisor_reviews is not None:
                    hotel.tripadvisor_reviews = tripadvisor_reviews
                if tripadvisor_url:
                    hotel.tripadvisor_url = tripadvisor_url
                if image_url:
                    hotel.image_url = image_url
                if accommodation_type:
                    hotel.accommodation_type = accommodation_type
                await s.commit()
                return True
            except Exception:
                await s.rollback()
                raise

    async def get_weekday_heatmap(self, district: str | None = None) -> list[dict]:
        """Тепловая карта загрузки: день недели (1=Пн..7=Вс) × месяц (1..12)."""
        async with async_session() as s:
            q_text = """
                SELECT
                    EXTRACT(ISODOW FROM hs.date)::int AS weekday,
                    EXTRACT(MONTH FROM hs.date)::int AS month,
                    AVG(100.0 - hs.available_rooms_percent) AS avg_occupancy,
                    COUNT(*) AS samples
                FROM hotel_statistics hs
                JOIN hotels h ON h.id = hs.id
                WHERE hs.available_rooms_percent IS NOT NULL
            """
            params: dict = {}
            if district:
                q_text += " AND h.district = :district"
                params["district"] = district
            q_text += " GROUP BY 1, 2 ORDER BY 1, 2"
            result = await s.execute(text(q_text), params)
            return [
                {
                    "weekday": int(r.weekday),
                    "month": int(r.month),
                    "occupancy": round(float(r.avg_occupancy or 0), 1),
                    "samples": int(r.samples or 0),
                }
                for r in result
            ]

    async def get_pickup_pace(
        self, district: str | None = None, days: int = 30,
    ) -> list[dict]:
        """Динамика бронирований за последние N дней (район или весь регион)."""
        from datetime import timedelta as _td

        date_from = date.today() - _td(days=days)
        async with async_session() as s:
            q_text = """
                SELECT
                    hs.date AS date,
                    SUM(hs.rooms_num) AS total_rooms,
                    SUM(hs.free_rooms_amount) AS free_rooms,
                    COUNT(DISTINCT hs.id) AS hotels_count
                FROM hotel_statistics hs
                JOIN hotels h ON h.id = hs.id
                WHERE hs.date >= :date_from
            """
            params: dict = {"date_from": date_from}
            if district:
                q_text += " AND h.district = :district"
                params["district"] = district
            q_text += " GROUP BY hs.date ORDER BY hs.date"
            result = await s.execute(text(q_text), params)
            return [
                {
                    "date": r.date.isoformat() if r.date else None,
                    "total_rooms": int(r.total_rooms or 0),
                    "free_rooms": int(r.free_rooms or 0),
                    "hotels_count": int(r.hotels_count or 0),
                }
                for r in result
                if r.date is not None
            ]

    async def export_occupancy_rows(
        self,
        district: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50000,
    ) -> list[dict]:
        """Сырые ряды для CSV-экспорта (для исследовательских задач)."""
        async with async_session() as s:
            q_text = """
                SELECT
                    hs.date,
                    h.id AS hotel_id,
                    h.name AS hotel_name,
                    h.district,
                    h.city,
                    hs.rooms_num,
                    hs.free_rooms_amount,
                    hs.available_rooms_percent,
                    hs.min_price
                FROM hotel_statistics hs
                JOIN hotels h ON h.id = hs.id
                WHERE 1=1
            """
            params: dict = {}
            if district:
                q_text += " AND h.district = :district"
                params["district"] = district
            if date_from:
                q_text += " AND hs.date >= :date_from"
                params["date_from"] = date_from
            if date_to:
                q_text += " AND hs.date <= :date_to"
                params["date_to"] = date_to
            q_text += " ORDER BY hs.date DESC, h.id LIMIT :limit"
            params["limit"] = limit
            result = await s.execute(text(q_text), params)
            return [
                {
                    "date": r.date.isoformat() if r.date else "",
                    "hotel_id": r.hotel_id or "",
                    "hotel_name": r.hotel_name or "",
                    "district": r.district or "",
                    "city": r.city or "",
                    "rooms_num": r.rooms_num or 0,
                    "free_rooms_amount": r.free_rooms_amount or 0,
                    "available_rooms_percent": r.available_rooms_percent or 0.0,
                    "min_price": r.min_price or 0,
                }
                for r in result
            ]

    async def save_ensemble_forecasts(
        self,
        *,
        district: str,
        forecasts: list[dict],
        model_name: str = "ensemble",
    ) -> int:
        """Идемпотентно сохраняет прогноз в таблицу forecasts.

        On conflict (district, forecast_date, model) — обновить значения (последний прогноз побеждает).

        Args:
            district: Название района.
            forecasts: Список словарей с ключами date, occupancy, lower (опц.), upper (опц.).
            model_name: Имя модели (по умолчанию "ensemble").

        Returns:
            Количество записанных строк (0 при ошибке или пустом входе).
        """
        if not self.is_connected or not forecasts:
            return 0
        try:
            rows = [
                {
                    "district": district,
                    "forecast_date": f["date"],
                    "predicted_occupancy": f.get("occupancy"),
                    "model": model_name,
                    "confidence_lower": f.get("lower"),
                    "confidence_upper": f.get("upper"),
                }
                for f in forecasts
                if f.get("date") is not None
            ]
            if not rows:
                return 0
            async with async_session() as s:
                ins = pg_insert(Forecast).values(rows)
                stmt = ins.on_conflict_do_update(
                    constraint="uq_forecasts_district_date_model",
                    set_={
                        "predicted_occupancy": ins.excluded.predicted_occupancy,
                        "confidence_lower": ins.excluded.confidence_lower,
                        "confidence_upper": ins.excluded.confidence_upper,
                        "updated_at": func.now(),
                    },
                )
                await s.execute(stmt)
                await s.commit()
            return len(rows)
        except Exception as exc:
            logger.error("save_ensemble_forecasts failed: %s", exc)
            return 0

    async def get_saved_forecasts(
        self, *, district: str, dates: list[date]
    ) -> dict[date, float]:
        """Возвращает {date -> predicted_occupancy} из таблицы forecasts (model='ensemble').

        Backward-compat: тонкий wrapper над get_saved_forecasts_with_ci, отдаёт только occupancy.

        Args:
            district: Название района.
            dates: Список дат для выборки.

        Returns:
            Словарь {дата: прогнозная загруженность}.
        """
        full = await self.get_saved_forecasts_with_ci(district=district, dates=dates)
        return {d: rec["occupancy"] for d, rec in full.items() if rec.get("occupancy") is not None}

    async def get_saved_forecasts_with_ci(
        self, *, district: str, dates: list[date]
    ) -> dict[date, dict]:
        """Возвращает {date -> {occupancy, lower, upper}} для ci_coverage расчёта (Phase 8)."""
        if not self.is_connected or not dates:
            return {}
        async with async_session() as s:
            rows = (await s.execute(
                select(
                    Forecast.forecast_date,
                    Forecast.predicted_occupancy,
                    Forecast.confidence_lower,
                    Forecast.confidence_upper,
                )
                .where(Forecast.district == district)
                .where(Forecast.forecast_date.in_(dates))
                .where(Forecast.model == "ensemble")
            )).all()
            return {
                r[0]: {"occupancy": r[1], "lower": r[2], "upper": r[3]}
                for r in rows
            }

    async def get_hotels_count(self) -> int:
        """Количество отелей в базе данных."""
        if not self.is_connected:
            return 0
        try:
            async with async_session() as s:
                return (await s.execute(select(func.count(Hotel.id)))).scalar_one()
        except Exception as exc:
            logger.error("get_hotels_count: %s", exc)
            return 0

    async def get_events_count(self) -> int:
        """Количество событий в базе данных."""
        if not self.is_connected:
            return 0
        try:
            async with async_session() as s:
                return (await s.execute(select(func.count(Event.event_id)))).scalar_one()
        except Exception as exc:
            logger.error("get_events_count: %s", exc)
            return 0

    async def get_data_date_range(self) -> dict:
        """Диапазон дат данных (min/max дата в hotel_statistics)."""
        if not self.is_connected:
            return {"from": None, "to": None}
        try:
            async with async_session() as s:
                row = (await s.execute(
                    select(func.min(HotelStatistic.date), func.max(HotelStatistic.date))
                )).first()
                return {
                    "from": row[0].isoformat() if row and row[0] else None,
                    "to": row[1].isoformat() if row and row[1] else None,
                }
        except Exception as exc:
            logger.error("get_data_date_range: %s", exc)
            return {"from": None, "to": None}

    async def detect_gap_periods(self, min_days: int = 7) -> list[dict]:
        """Находит периоды без данных в hotel_statistics длиннее min_days дней.

        Args:
            min_days: Минимальная длина пропуска в днях.

        Returns:
            Список словарей с полями from, to, gap_days, reason.
        """
        if not self.is_connected:
            return []
        try:
            async with async_session() as s:
                result = await s.execute(text("""
                    WITH dated AS (
                        SELECT DISTINCT date FROM hotel_statistics
                    ),
                    leaded AS (
                        SELECT date AS d_prev, LEAD(date) OVER (ORDER BY date) AS d_next FROM dated
                    )
                    SELECT d_prev, d_next, (d_next - d_prev) AS gap_days
                    FROM leaded
                    WHERE d_next - d_prev > :min_days
                    ORDER BY d_prev
                """), {"min_days": min_days})
                rows = result.all()
                return [
                    {
                        "from": r[0].isoformat() if r[0] else None,
                        "to": r[1].isoformat() if r[1] else None,
                        "gap_days": int(r[2]) if r[2] is not None else None,
                        "reason": "data_collection_offline",
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.error("detect_gap_periods: %s", exc)
            return []

    async def get_last_data_refresh(self) -> datetime | None:
        """Дата последнего обновления данных (MAX updated_at в hotel_statistics)."""
        if not self.is_connected:
            return None
        try:
            async with async_session() as s:
                row = (await s.execute(select(func.max(HotelStatistic.updated_at)))).first()
                return row[0] if row else None
        except Exception as exc:
            logger.error("get_last_data_refresh: %s", exc)
            return None

    async def collect_min_prices(self, *, district: str, days: int) -> list[int]:
        """Возвращает все min_price из hotel_statistics за последние N дней по району.

        Args:
            district: Район Иркутской области.
            days: Глубина выборки в днях.

        Returns:
            Список ненулевых значений min_price (целые числа).
        """
        if not self.is_connected:
            return []
        from datetime import timedelta as _td
        cutoff = date.today() - _td(days=days)
        try:
            async with async_session() as s:
                rows = (await s.execute(
                    select(HotelStatistic.min_price)
                    .join(Hotel, Hotel.id == HotelStatistic.id)
                    .where(Hotel.district == district)
                    .where(HotelStatistic.date >= cutoff)
                    .where(HotelStatistic.min_price.is_not(None))
                )).all()
                return [r[0] for r in rows if r[0] is not None]
        except Exception as exc:
            logger.error("collect_min_prices: %s", exc)
            return []

    async def compute_proxy_pickup(
        self,
        *,
        district: str,
        days_ahead: int,
        lookback_days: int,
    ) -> list[dict]:
        """Прокси-pickup: разница occupancy между двумя snapshot'ами для будущих дат.

        Ограничение: таблица hotel_statistics хранит одну строку на (hotel_id, date)
        без временно́й метки snapshot'а.  Настоящий pickup требовал бы двух snapshot'ов —
        «сегодня» и «lookback_days назад» — для одной и той же future_date.
        Поскольку такой timestamp отсутствует, метод возвращает текущий уровень occupancy
        для каждой будущей даты и proxy_pickup_pct=0.0, явно документируя ограничение
        через поле methodology в ответе.

        Args:
            district: Район Иркутской области.
            days_ahead: Количество будущих дней для анализа.
            lookback_days: Запрошенный горизонт ретроспективы (сохраняется для ответа).

        Returns:
            Список словарей с ключами date, occupancy_today, occupancy_lookback, proxy_pickup_pct.
        """
        if not self.is_connected:
            return []
        from datetime import timedelta as _td
        today = date.today()
        futures = [today + _td(days=i) for i in range(1, days_ahead + 1)]

        try:
            async with async_session() as s:
                q_text = """
                    SELECT
                        hs.date,
                        AVG(100.0 - hs.available_rooms_percent) AS occupancy
                    FROM hotel_statistics hs
                    JOIN hotels h ON h.id = hs.id
                    WHERE h.district = :district
                      AND hs.available_rooms_percent IS NOT NULL
                      AND hs.date = ANY(:futures)
                    GROUP BY hs.date
                    ORDER BY hs.date
                """
                result = await s.execute(
                    text(q_text),
                    {"district": district, "futures": futures},
                )
                rows = result.all()

            by_date: dict[date, float] = {r[0]: float(r[1] or 0.0) for r in rows}

            points: list[dict] = []
            for fd in futures:
                today_val = by_date.get(fd)
                # Without per-snapshot timestamps we cannot distinguish "occupancy seen
                # today" vs "occupancy seen lookback_days ago" for the same future date.
                # Both slots receive the same value; proxy_pickup_pct is therefore 0.0 when
                # data exists and None when it doesn't — caller documents this via methodology.
                prev_val = today_val
                pickup = 0.0 if today_val is not None else None
                points.append({
                    "date": fd.isoformat(),
                    "occupancy_today": round(today_val, 2) if today_val is not None else None,
                    "occupancy_lookback": round(prev_val, 2) if prev_val is not None else None,
                    "proxy_pickup_pct": pickup,
                })
            return points
        except Exception as exc:
            logger.error("compute_proxy_pickup: %s", exc)
            return []

    async def segments_by_size(self) -> dict[str, dict]:
        """Возвращает {'mini'/'mid'/'large': {count, avg_occupancy, avg_price}}."""
        if not self.is_connected:
            return {}
        try:
            async with async_session() as s:
                result = await s.execute(text("""
                    WITH latest AS (
                        SELECT DISTINCT ON (id) id, rooms_num, available_rooms_percent, min_price
                        FROM hotel_statistics
                        ORDER BY id, date DESC
                    )
                    SELECT
                        CASE
                            WHEN rooms_num <= 15 THEN 'mini'
                            WHEN rooms_num <= 50 THEN 'mid'
                            ELSE 'large'
                        END AS size_bucket,
                        COUNT(*) AS n,
                        AVG(100 - available_rooms_percent) AS avg_occ,
                        AVG(min_price) AS avg_price
                    FROM latest
                    WHERE rooms_num IS NOT NULL
                    GROUP BY size_bucket
                """))
                return {
                    r[0]: {
                        "count": int(r[1]),
                        "avg_occupancy": round(float(r[2] or 0), 2),
                        "avg_price": int(r[3] or 0),
                    }
                    for r in result.all()
                }
        except Exception as exc:
            logger.error("segments_by_size: %s", exc)
            return {}

    async def segments_by_accommodation_type(self) -> dict[str, dict]:
        """Возвращает {'<type>': {count, avg_price}}."""
        if not self.is_connected:
            return {}
        try:
            async with async_session() as s:
                result = await s.execute(text("""
                    SELECT COALESCE(accommodation_type, 'unknown') AS at, COUNT(*) AS n,
                           AVG(min_price) AS avg_price
                    FROM hotels
                    GROUP BY at
                    ORDER BY n DESC
                """))
                return {
                    r[0]: {"count": int(r[1]), "avg_price": int(r[2] or 0)}
                    for r in result.all()
                }
        except Exception as exc:
            logger.error("segments_by_accommodation_type: %s", exc)
            return {}

    async def district_segment_breakdown(self, district: str) -> dict:
        """Drill-down RMS-таблицы: разбивка района по типу размещения и size_bucket.

        Возвращает:
            {
              "district": "...",
              "total_objects": int,
              "by_size": [{size, count, avg_occupancy, avg_min_price, revpar}, ...],
              "by_accommodation_type": [{type, count, avg_occupancy, avg_min_price, revpar}, ...],
            }
        Метрики берутся с последних снимков hotel_statistics за каждый отель в районе.
        """
        if not self.is_connected:
            return {"district": district, "total_objects": 0, "by_size": [], "by_accommodation_type": []}
        try:
            async with async_session() as s:
                latest_cte = """
                    WITH latest AS (
                        SELECT DISTINCT ON (hs.id)
                               hs.id, hs.rooms_num, hs.available_rooms_percent, hs.min_price,
                               h.accommodation_type
                        FROM hotel_statistics hs
                        JOIN hotels h ON h.id = hs.id
                        WHERE h.district = :district
                        ORDER BY hs.id, hs.date DESC
                    )
                """

                size_q = latest_cte + """
                    SELECT
                        CASE
                            WHEN rooms_num <= 15 THEN 'mini'
                            WHEN rooms_num <= 50 THEN 'mid'
                            ELSE 'large'
                        END AS size_bucket,
                        COUNT(*) AS n,
                        AVG(100 - available_rooms_percent) AS avg_occ,
                        AVG(NULLIF(min_price, 0)) AS avg_price
                    FROM latest
                    WHERE rooms_num IS NOT NULL
                    GROUP BY size_bucket
                    ORDER BY n DESC
                """
                size_rows = (await s.execute(text(size_q), {"district": district})).all()
                by_size = []
                for r in size_rows:
                    occ = float(r.avg_occ or 0)
                    price = float(r.avg_price or 0)
                    by_size.append({
                        "size": r.size_bucket,
                        "count": int(r.n),
                        "avg_occupancy": round(occ, 1),
                        "avg_min_price": int(price) if price else None,
                        "revpar": int(price * occ / 100) if price and occ else None,
                    })

                type_q = latest_cte + """
                    SELECT
                        COALESCE(accommodation_type, 'не указан') AS at,
                        COUNT(*) AS n,
                        AVG(100 - available_rooms_percent) AS avg_occ,
                        AVG(NULLIF(min_price, 0)) AS avg_price
                    FROM latest
                    GROUP BY at
                    ORDER BY n DESC
                """
                type_rows = (await s.execute(text(type_q), {"district": district})).all()
                by_type = []
                for r in type_rows:
                    occ = float(r.avg_occ or 0)
                    price = float(r.avg_price or 0)
                    by_type.append({
                        "type": r.at,
                        "count": int(r.n),
                        "avg_occupancy": round(occ, 1),
                        "avg_min_price": int(price) if price else None,
                        "revpar": int(price * occ / 100) if price and occ else None,
                    })

                total = sum(b["count"] for b in by_size)
                return {
                    "district": district,
                    "total_objects": total,
                    "by_size": by_size,
                    "by_accommodation_type": by_type,
                }
        except Exception as exc:
            logger.error("district_segment_breakdown(%s): %s", district, exc)
            return {"district": district, "total_objects": 0, "by_size": [], "by_accommodation_type": []}

    async def get_hotel_latest_stats(self, hotel_id: str) -> dict:
        """Последняя запись статистики для конкретного отеля.

        Args:
            hotel_id: ID отеля.

        Returns:
            Словарь с ключами date, rooms_num, occupancy, min_price. Пустой dict при ошибке.
        """
        if not self.is_connected:
            return {}
        try:
            async with async_session() as s:
                row = (await s.execute(
                    select(HotelStatistic)
                    .where(HotelStatistic.id == hotel_id)
                    .order_by(HotelStatistic.date.desc())
                    .limit(1)
                )).scalar_one_or_none()
                if not row:
                    return {}
                return {
                    "date": row.date.isoformat() if row.date else None,
                    "rooms_num": row.rooms_num,
                    "occupancy": round(100 - (row.available_rooms_percent or 0), 2),
                    "min_price": row.min_price,
                }
        except Exception as exc:
            logger.error("get_hotel_latest_stats: %s", exc)
            return {}

    async def compute_segment_metrics(
        self,
        *,
        district: str | None,
        size_bucket: str,
        exclude_hotel_id: str | None = None,
    ) -> dict:
        """Средние метрики по сегменту «район × размерная категория».

        Args:
            district: Район Иркутской области.
            size_bucket: "mini" (≤15), "mid" (16-50) или "large" (51+).
            exclude_hotel_id: ID отеля, который следует исключить из расчёта (self-exclusion).

        Returns:
            Словарь с ключами n, avg_occupancy, avg_price.
        """
        if not self.is_connected or not district:
            return {"n": 0, "avg_occupancy": None, "avg_price": None}
        bounds = {"mini": (0, 15), "mid": (16, 50), "large": (51, 10_000)}.get(size_bucket, (0, 10_000))
        try:
            async with async_session() as s:
                params = {
                    "district": district,
                    "min_r": bounds[0],
                    "max_r": bounds[1],
                    "exclude_id": exclude_hotel_id,
                }
                row = (await s.execute(text("""
                    WITH latest AS (
                        SELECT DISTINCT ON (h.id) h.id, h.district, hs.rooms_num,
                               hs.available_rooms_percent, hs.min_price
                        FROM hotels h
                        JOIN hotel_statistics hs ON hs.id = h.id
                        WHERE h.district = :district
                          AND hs.rooms_num BETWEEN :min_r AND :max_r
                          AND (CAST(:exclude_id AS TEXT) IS NULL OR h.id <> CAST(:exclude_id AS TEXT))
                        ORDER BY h.id, hs.date DESC
                    )
                    SELECT COUNT(*) AS n,
                           AVG(100 - available_rooms_percent) AS avg_occ,
                           AVG(min_price) AS avg_price
                    FROM latest
                """), params)).first()
                if not row:
                    return {"n": 0, "avg_occupancy": None, "avg_price": None}
                return {
                    "n": int(row[0] or 0),
                    "avg_occupancy": round(float(row[1] or 0), 2) if row[1] is not None else None,
                    "avg_price": int(row[2] or 0) if row[2] is not None else None,
                }
        except Exception as exc:
            logger.error("compute_segment_metrics: %s", exc)
            return {"n": 0, "avg_occupancy": None, "avg_price": None}

    async def create_tables(self) -> None:
        """Create tables if they don't exist. For schema changes use Alembic:
        cd backend && alembic revision --autogenerate -m "description"
        cd backend && alembic upgrade head
        """
        from app.db.models import Base
        from app.db.session import engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL tables ensured (for schema changes use: alembic upgrade head)")


db_service = DBService()
