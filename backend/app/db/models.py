"""SQLAlchemy ORM модели для PostgreSQL."""
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    min_price: Mapped[int | None] = mapped_column(Integer)
    accommodation_type: Mapped[str | None] = mapped_column(String(100))
    tripadvisor_rating: Mapped[float | None] = mapped_column(Float)
    tripadvisor_reviews: Mapped[int | None] = mapped_column(Integer)
    tripadvisor_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 10", name="ck_hotel_rating"),
        CheckConstraint("min_price >= 0 OR min_price IS NULL", name="ck_hotel_min_price"),
        Index("idx_hotels_city", "city"),
        Index("idx_hotels_district", "district"),
    )


class HotelStatistic(Base):
    __tablename__ = "hotel_statistics"

    id: Mapped[str] = mapped_column(
        String(64), ForeignKey("hotels.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    rooms_num: Mapped[int | None] = mapped_column(Integer)
    free_rooms_amount: Mapped[int | None] = mapped_column(Integer)
    available_rooms_percent: Mapped[float | None] = mapped_column(Float)
    min_price: Mapped[int | None] = mapped_column(Integer)
    max_capacity: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "available_rooms_percent >= 0 AND available_rooms_percent <= 100",
            name="ck_stat_occupancy",
        ),
        Index("idx_stats_date", "date"),
    )


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date | None] = mapped_column(Date)
    event_type: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    time_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_restriction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("source_id", "date_start", "title", name="uq_events_dedup"),
        Index("idx_events_date", "date_start"),
        Index("idx_events_source", "source_id"),
        Index("idx_events_type", "event_type"),
    )


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_occupancy: Mapped[float | None] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_lower: Mapped[float | None] = mapped_column(Float)
    confidence_upper: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("district", "forecast_date", "model", name="uq_forecasts_district_date_model"),
        Index("idx_forecasts_district_date", "district", "forecast_date"),
    )
