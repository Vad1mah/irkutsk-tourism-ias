"""Сервис для получения погодных данных из OpenMeteo API."""
import aiohttp
import time
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

# Координаты Иркутска (центр региона)
IRKUTSK_LAT = 52.28
IRKUTSK_LON = 104.28

# OpenMeteo API endpoints
HISTORICAL_API = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"

# Cache settings
CACHE_TTL = 3600  # 1 час
MAX_CACHE_SIZE = 50


class WeatherService:
    """Сервис для работы с погодными данными."""

    def __init__(self, lat: float = IRKUTSK_LAT, lon: float = IRKUTSK_LON):
        self.lat = lat
        self.lon = lon
        self._cache: dict[str, dict] = {}
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Получить или создать переиспользуемую HTTP-сессию."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрыть HTTP-сессию."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_cached(self, key: str) -> dict | None:
        """Получить значение из кэша с проверкой TTL."""
        cached = self._cache.get(key)
        if cached and (time.time() - cached["timestamp"]) < CACHE_TTL:
            return cached["data"]
        return None

    def _set_cached(self, key: str, data: dict) -> None:
        """Сохранить в кэш с очисткой устаревших."""
        if len(self._cache) >= MAX_CACHE_SIZE:
            now = time.time()
            expired = [k for k, v in self._cache.items()
                       if (now - v["timestamp"]) >= CACHE_TTL]
            for k in expired:
                del self._cache[k]
            if len(self._cache) >= MAX_CACHE_SIZE:
                oldest = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
                del self._cache[oldest]

        self._cache[key] = {"data": data, "timestamp": time.time()}
    
    async def get_historical_weather(
        self,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """
        Получить исторические данные о погоде.
        
        Args:
            date_from: Начальная дата
            date_to: Конечная дата
            
        Returns:
            Список с погодой по дням:
            [{"date": "2025-01-01", "temperature": -15.2, "precipitation": 0.5}, ...]
        """
        cache_key = f"hist_{date_from}_{date_to}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "start_date": str(date_from),
            "end_date": str(date_to),
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max,weathercode",
            "timezone": "Asia/Irkutsk",
        }

        try:
            session = await self._ensure_session()
            async with session.get(
                HISTORICAL_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result = self._parse_daily_data(data)
                    self._set_cached(cache_key, result)
                    return result
                else:
                    logger.error(f"OpenMeteo historical API error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return []
    
    async def get_forecast_weather(
        self,
        days_ahead: int = 14,
        lat: float | None = None,
        lon: float | None = None,
    ) -> list[dict]:
        """
        Получить прогноз погоды на ближайшие дни.
        
        Args:
            days_ahead: Количество дней прогноза (макс 16)
            lat: Широта (None = дефолт Иркутск)
            lon: Долгота (None = дефолт Иркутск)
            
        Returns:
            Список с прогнозом погоды по дням
        """
        params = {
            "latitude": lat or self.lat,
            "longitude": lon or self.lon,
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max,weathercode",
            "timezone": "Asia/Irkutsk",
            "forecast_days": min(days_ahead, 16),
        }
        
        try:
            session = await self._ensure_session()
            async with session.get(
                FORECAST_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_daily_data(data)
                else:
                    logger.error(f"OpenMeteo forecast API error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Weather forecast API error: {e}")
            return []
    
    def _parse_daily_data(self, data: dict) -> list[dict]:
        """Парсит ответ OpenMeteo в список словарей."""
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        temps_mean = daily.get("temperature_2m_mean", [])
        precip = daily.get("precipitation_sum", [])
        winds = daily.get("wind_speed_10m_max", [])
        codes = daily.get("weathercode", [])

        result = []
        for i, d in enumerate(dates):
            t_max = temps_max[i] if i < len(temps_max) else None
            t_min = temps_min[i] if i < len(temps_min) else None
            t_mean = temps_mean[i] if i < len(temps_mean) else (
                round((t_max + t_min) / 2, 1) if t_max is not None and t_min is not None else t_max
            )
            prec = precip[i] if i < len(precip) else 0
            wind = winds[i] if i < len(winds) else None
            result.append({
                "date": d,
                "temperature_max": t_max,
                "temperature_min": t_min,
                "temperature_mean": t_mean,
                "temperature": t_mean,
                "precipitation": prec,
                "wind_speed": round(wind, 1) if wind is not None else 0,
                "wind_unit": "км/ч",
                "weather_code": codes[i] if i < len(codes) else None,
                "weather_description": self._weather_code_to_text(
                    codes[i] if i < len(codes) else None
                ),
                "is_good_weather": self._is_good_weather(t_max, prec),
            })
        return result
    
    def _is_good_weather(self, temp: float | None, precip: float | None) -> bool:
        """
        Определяет хорошая ли погода для туризма.
        
        Хорошая погода: температура > 10°C и осадки < 5мм
        """
        if temp is None:
            return False
        return temp > 10 and (precip or 0) < 5
    
    async def get_weather_for_dates(
        self,
        dates: list[date],
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict[date, dict]:
        """
        Получить погоду для списка дат (комбинирует историю и прогноз).
        
        Returns:
            Словарь {date: weather_data}
        """
        if not dates:
            return {}
        
        today = date.today()
        result = {}
        
        # Разделяем на прошлое и будущее
        past_dates = [d for d in dates if d < today]
        future_dates = [d for d in dates if d >= today]
        
        # Получаем исторические данные
        if past_dates:
            min_date = min(past_dates)
            max_date = max(past_dates)
            historical = await self.get_historical_weather(min_date, max_date)
            for w in historical:
                d = date.fromisoformat(w["date"]) if isinstance(w["date"], str) else w["date"]
                result[d] = w
        
        # Получаем прогноз
        if future_dates:
            max_future = max(future_dates)
            days_ahead = (max_future - today).days + 1
            forecast = await self.get_forecast_weather(days_ahead, lat=lat, lon=lon)
            for w in forecast:
                d = date.fromisoformat(w["date"]) if isinstance(w["date"], str) else w["date"]
                result[d] = w
        
        return result


    async def get_current_weather(
        self,
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict | None:
        """
        Получить текущую погоду для указанных координат.
        
        Использует новый API Open-Meteo с параметром 'current' (рекомендуемый метод 2024+).
        
        Args:
            lat: Широта (по умолчанию Иркутск)
            lon: Долгота (по умолчанию Иркутск)
            
        Returns:
            Словарь с текущей погодой или None
        """
        use_lat = lat or self.lat
        use_lon = lon or self.lon
        
        # Новый синтаксис Open-Meteo API (current вместо current_weather)
        params = {
            "latitude": use_lat,
            "longitude": use_lon,
            "current": "temperature_2m,weathercode,is_day,precipitation,windspeed_10m",
            "timezone": "Asia/Irkutsk",
            "windspeed_unit": "ms",  # м/с более понятно для русскоязычных
        }
        
        try:
            session = await self._ensure_session()
            async with session.get(
                FORECAST_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data.get("current", {})
                    return {
                        "temperature": current.get("temperature_2m"),
                        "weather_code": current.get("weathercode"),
                        "description": self._weather_code_to_text(
                            current.get("weathercode")
                        ),
                        "precipitation": current.get("precipitation", 0),
                        "wind_speed": current.get("windspeed_10m"),
                        "is_day": current.get("is_day", 1),
                    }
                else:
                    logger.warning(f"OpenMeteo current weather: status {response.status}")
        except Exception as e:
            logger.warning(f"Current weather API error: {e}")
        
        return None
    
    def _weather_code_to_text(self, code: int | None) -> str:
        """Конвертация WMO weather code в текст."""
        if code is None:
            return "нет данных"
        
        codes = {
            0: "ясно",
            1: "преимущественно ясно",
            2: "переменная облачность",
            3: "пасмурно",
            45: "туман",
            48: "туман с изморозью",
            51: "лёгкая морось",
            53: "морось",
            55: "сильная морось",
            61: "небольшой дождь",
            63: "дождь",
            65: "сильный дождь",
            71: "небольшой снег",
            73: "снег",
            75: "сильный снег",
            77: "снежные зёрна",
            80: "ливневый дождь",
            81: "сильный ливень",
            85: "небольшой снегопад",
            86: "сильный снегопад",
            95: "гроза",
            96: "гроза с градом",
        }
        return codes.get(code, f"код {code}")


# Глобальный экземпляр сервиса
weather_service = WeatherService()
