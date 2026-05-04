from datetime import date, time
from typing import Any
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class Hotel(BaseModel):
    """Данные отеля."""
    id: str
    name: str = Field(..., min_length=1, description="Название отеля")
    city: str = Field("", description="Город")
    district: str | None = Field(None, description="Район (Иркутский, Ольхонский, и т.д.)")
    lat: float | None = Field(None, ge=-90, le=90, description="Широта")
    lon: float | None = Field(None, ge=-180, le=180, description="Долгота")
    rating: float | None = Field(None, ge=0, le=5, description="Рейтинг 0-5")
    min_price: int | None = Field(None, ge=0, description="Минимальная цена")
    accommodation_type: str | None = Field(None, description="Тип размещения")
    tripadvisor_rating: float | None = Field(None, ge=0, le=5)
    tripadvisor_reviews: int | None = Field(None, ge=0)
    tripadvisor_url: str | None = Field(None, description="Ссылка на TripAdvisor")
    image_url: str | None = None

    @field_validator('rating', mode='before')
    @classmethod
    def normalize_rating(cls, v):
        """Нормализовать рейтинг к шкале 0-5."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            # Если рейтинг > 5, предполагаем шкалу 0-10 и конвертируем
            if v > 5:
                return round(v / 2, 1)
            return round(v, 1)
        return v


class HotelStatistics(BaseModel):
    """Статистика отеля за дату."""
    id: str
    date: date
    rooms_num: int | None = Field(None, ge=0, description="Общее количество номеров")
    free_rooms_amount: int | None = Field(None, ge=0, description="Свободных номеров")
    available_rooms_percent: float | None = Field(None, ge=0, le=100, description="Процент свободных")
    min_price: int | None = Field(None, ge=0)
    max_capacity: int | None = Field(None, ge=0, description="Максимальная вместимость")


class Event(BaseModel):
    """Событие/мероприятие."""
    event_id: str = Field(..., description="Уникальный ID события")
    title: str = Field(..., min_length=1, description="Название события")
    description: str | None = None
    date_start: date = Field(..., description="Дата начала")
    date_end: date | None = Field(None, description="Дата окончания")
    event_type: str | None = Field(None, description="Тип события")
    location: str | None = Field(None, description="Место проведения")
    source_id: str = Field(..., description="Источник данных")
    url: str | None = None
    time_start: time | None = Field(None, description="Время начала события (HH:MM:SS)")
    price_min: int | None = Field(None, ge=0, description="Минимальная цена в рублях")
    price_max: int | None = Field(None, ge=0, description="Максимальная цена в рублях")
    image_url: str | None = Field(None, description="URL изображения")
    address: str | None = Field(None, description="Уличный адрес места проведения")
    age_restriction: str | None = Field(None, max_length=10, description="Возрастное ограничение, напр. 16+")

    model_config = ConfigDict(populate_by_name=True)


class QueryRequest(BaseModel):
    """Запрос к AI-агенту."""
    text: str = Field(..., min_length=1, max_length=2000, description="Текст запроса")
    session_id: str | None = Field(None, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$", description="ID сессии для сохранения контекста")
    
    @field_validator('text', mode='before')
    @classmethod
    def strip_text(cls, v: str) -> str:
        """Убираем лишние пробелы."""
        return v.strip() if isinstance(v, str) else v


class QueryResponse(BaseModel):
    """Ответ AI-агента."""
    answer: str = Field(..., description="Ответ модели")
    sources: list[str] = Field(default_factory=list, description="Источники данных")


class ForecastRequest(BaseModel):
    """Запрос на прогноз."""
    hotel_id: str | None = None
    district: str | None = None
    days_ahead: int = Field(30, ge=1, le=365, description="Горизонт прогноза в днях")


class ForecastPoint(BaseModel):
    """Точка прогноза."""
    date: date
    occupancy: float = Field(..., ge=0, le=100, description="Прогнозируемая загрузка %")
    lower_bound: float = Field(..., ge=0, le=100, description="Нижняя граница CI")
    upper_bound: float = Field(..., ge=0, le=100, description="Верхняя граница CI")


class ForecastResponse(BaseModel):
    """Ответ с прогнозом."""
    hotel_id: str | None = None
    district: str | None = None
    forecast: list[ForecastPoint] = Field(..., description="Точки прогноза")
    history_points: int = Field(..., ge=0, description="Количество точек истории")


class DocumentRequest(BaseModel):
    """Запрос на добавление документа."""
    text: str = Field(..., min_length=1, description="Текст документа")
    source: str = Field(..., min_length=1, description="Источник")
    metadata: dict = Field(default_factory=dict, description="Метаданные")


class DocumentResponse(BaseModel):
    """Ответ на добавление документа."""
    id: str
    text: str
    source: str
    metadata: dict


# Analytics response models

class KPIResponse(BaseModel):
    """KPI дашборд."""
    total_hotels: int
    total_cities: int
    total_events: int
    total_rooms: int
    free_rooms: int
    avg_occupancy: float
    avg_price: float | None = None


class DistrictStats(BaseModel):
    """Статистика по району."""
    district: str
    hotels_count: int
    total_rooms: int
    free_rooms: int
    avg_occupancy: float
    avg_price: float


class CityHotels(BaseModel):
    """Отели по городу."""
    city: str
    count: int


class ParserResult(BaseModel):
    """Результат парсинга."""
    status: str
    source: str
    count: int
    message: str | None = None


class HealthResponse(BaseModel):
    """Health check ответ."""
    status: str
    db_backend: str
    db_connected: bool
    redis_connected: bool
    chroma_docs: int


class Recommendation(BaseModel):
    """Рекомендация."""
    type: str
    title: str
    description: str
    period: str | None = None


class CompareForecast(BaseModel):
    """Точка сравнения прогнозов."""
    model_config = ConfigDict(populate_by_name=True)

    date: str
    occupancy: float
    lower: float = Field(0, validation_alias=AliasChoices("lower", "lower_bound"))
    upper: float = Field(0, validation_alias=AliasChoices("upper", "upper_bound"))


class EnsemblePoint(BaseModel):
    """Точка ensemble прогноза."""
    model_config = ConfigDict(populate_by_name=True)

    date: str
    occupancy: float
    lower: float = Field(0, validation_alias=AliasChoices("lower", "lower_bound"))
    upper: float = Field(0, validation_alias=AliasChoices("upper", "upper_bound"))


class EnsembleResponse(BaseModel):
    """Ответ ensemble прогноза."""
    district: str
    history_points: int
    method: str
    weights: dict[str, float]
    ensemble: list[EnsemblePoint]
    models: dict[str, list[CompareForecast]]


class CompareModelsResponse(BaseModel):
    """Ответ сравнения Prophet и NeuralProphet."""
    district: str
    history_points: int
    prophet: list[CompareForecast]
    neuralprophet: list[CompareForecast]


class CompareAllResponse(BaseModel):
    """Ответ сравнения всех моделей."""
    district: str
    history_points: int
    test_days: int
    metrics: dict[str, Any]
    feature_importance: dict[str, dict[str, float]] | None = None


class EventBrief(BaseModel):
    """Краткая информация о событии для сводки."""
    title: str
    date: str
    event_type: str | None = None


class WeatherDay(BaseModel):
    """День прогноза погоды для сводки."""
    date: str
    temp_max: float
    temp_min: float
    weather_code: int
    description: str


class TripSummary(BaseModel):
    """Сводка для планирования поездки."""
    district: str
    forecast_occupancy: float = Field(description="Средняя прогнозная загрузка на период")
    occupancy_level: str = Field(description="low / medium / high")
    occupancy_trend: str = Field(description="growing / stable / declining")
    forecast_source: str = Field(default="ensemble", description="ensemble | fallback")
    weather: list[WeatherDay] = Field(default_factory=list)
    events_count: int = 0
    top_events: list[EventBrief] = Field(default_factory=list)
    available_hotels: int = 0
    avg_price: float | None = None
    recommendation: str = ""


class BestDate(BaseModel):
    """Лучшая дата для поездки."""
    date: str
    predicted_occupancy: float
    weather_temp: float | None = None
    events: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=100, description="Оценка 0-100, выше = лучше")


class ValidationPoint(BaseModel):
    """Точка валидации (прогноз или факт)."""
    date: str
    occupancy: float


class ForecastValidationResponse(BaseModel):
    """Результат самовалидации модели: прогноз vs факт."""
    district: str
    days_back: int
    samples: int
    rmse: float | None = None
    mae: float | None = None
    mae_per_day: list[float] = Field(default_factory=list)
    forecasted: list[ValidationPoint] = Field(default_factory=list)
    actual: list[ValidationPoint] = Field(default_factory=list)

