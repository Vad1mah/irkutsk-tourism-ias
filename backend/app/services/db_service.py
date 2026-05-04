"""PostgreSQL сервис данных."""
import logging
from datetime import date, time

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Event, Hotel, HotelStatistic
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
                }
                for r in rows
            ]

    async def create_events_table(self) -> bool:
        return True

    async def get_occupancy_by_district(
        self,
        district: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        async with async_session() as s:
            q_text = """
                SELECT hs.date,
                       AVG(100.0 - hs.available_rooms_percent) AS avg_occupancy,
                       AVG(hs.min_price) FILTER (WHERE hs.min_price > 0) AS avg_price
                FROM hotel_statistics hs
                JOIN hotels h ON h.id = hs.id
                WHERE h.district = :district
            """
            params: dict = {"district": district}
            if date_from:
                q_text += " AND hs.date >= :date_from"
                params["date_from"] = date_from
            if date_to:
                q_text += " AND hs.date <= :date_to"
                params["date_to"] = date_to
            q_text += " GROUP BY hs.date ORDER BY hs.date"
            result = await s.execute(text(q_text), params)
            return [
                {
                    "date": row.date,
                    "avg_occupancy": round(float(row.avg_occupancy), 1) if row.avg_occupancy is not None else 0.0,
                    "avg_price": round(float(row.avg_price)) if row.avg_price else None,
                }
                for row in result
                if row.avg_occupancy is not None
            ]

    async def get_monthly_statistics(self, year: int | None = None) -> list[dict]:
        async with async_session() as s:
            q_text = """
                SELECT
                    EXTRACT(YEAR FROM date)::int AS year,
                    EXTRACT(MONTH FROM date)::int AS month,
                    AVG(100.0 - available_rooms_percent) AS avg_occupancy,
                    AVG(min_price) AS avg_price,
                    SUM(rooms_num) AS total_rooms,
                    SUM(free_rooms_amount) AS free_rooms,
                    COUNT(*) AS records_count
                FROM hotel_statistics
                WHERE date IS NOT NULL
            """
            params: dict = {}
            if year:
                q_text += " AND EXTRACT(YEAR FROM date) = :year"
                params["year"] = year
            q_text += " GROUP BY 1, 2 ORDER BY 1, 2"
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

    async def insert_events_batch(self, events: list[dict]) -> int:
        rows = []
        for ev in events:
            ds = self._to_date(ev.get("date_start"))
            if not ds:
                continue
            eid = ev.get("event_id") or ev.get("id")
            if not eid:
                continue
            rows.append({
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
            })
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
