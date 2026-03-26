"""Парсер погоды с Open-Meteo API.

Open-Meteo (https://open-meteo.com/) - бесплатный API погоды:
- Прогноз на 16 дней
- Исторические данные
- Не требует API ключа
- Без лимитов для некоммерческого использования

Локации:
- Иркутск: 52.2978, 104.2964
- Листвянка: 51.8686, 104.8610
- Ольхон (Хужир): 53.1954, 107.3474
"""
import asyncio
import aiohttp
import logging
from datetime import date, timedelta
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from app.constants import LOCATIONS as _COORDS, CITY_SLUG_TO_NAME

LOCATIONS = {
    key: {"name": CITY_SLUG_TO_NAME.get(key, key), "lat": coords[0], "lon": coords[1]}
    for key, coords in {
        "irkutsk": _COORDS["иркутск"],
        "listvyanka": _COORDS["листвянка"],
        "huzhir": _COORDS["хужир"],
        "baikalsk": _COORDS["байкальск"],
    }.items()
}

# Базовый URL API
OPENMETEO_BASE = "https://api.open-meteo.com/v1"


@dataclass
class WeatherData:
    """Данные о погоде."""
    location: str
    date: str
    temperature_max: float
    temperature_min: float
    temperature_mean: float
    precipitation: float  # мм
    wind_speed: float  # км/ч
    weather_code: int
    weather_description: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "date": self.date,
            "temperature_max": self.temperature_max,
            "temperature_min": self.temperature_min,
            "temperature_mean": self.temperature_mean,
            "precipitation": self.precipitation,
            "wind_speed": self.wind_speed,
            "weather_code": self.weather_code,
            "weather_description": self.weather_description,
        }


# WMO Weather interpretation codes
WEATHER_CODES = {
    0: "Ясно",
    1: "Преимущественно ясно",
    2: "Переменная облачность",
    3: "Пасмурно",
    45: "Туман",
    48: "Изморозь",
    51: "Лёгкая морось",
    53: "Морось",
    55: "Сильная морось",
    61: "Небольшой дождь",
    63: "Дождь",
    65: "Сильный дождь",
    66: "Лёгкий ледяной дождь",
    67: "Ледяной дождь",
    71: "Небольшой снег",
    73: "Снег",
    75: "Сильный снег",
    77: "Снежные зёрна",
    80: "Небольшой ливень",
    81: "Ливень",
    82: "Сильный ливень",
    85: "Небольшой снегопад",
    86: "Снегопад",
    95: "Гроза",
    96: "Гроза с градом",
    99: "Сильная гроза с градом",
}


class OpenMeteoParser:
    """Парсер погоды Open-Meteo."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_session(self):
        """Создать сессию если её нет."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
    
    async def close(self):
        """Закрыть сессию."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def fetch_forecast(
        self,
        location: str = "irkutsk",
        days: int = 7
    ) -> list[WeatherData]:
        """
        Получить прогноз погоды.
        
        Args:
            location: Название локации
            days: Количество дней (до 16)
            
        Returns:
            Список WeatherData по дням
        """
        if location not in LOCATIONS:
            logger.error(f"Неизвестная локация: {location}")
            return []
        
        await self._ensure_session()
        
        loc = LOCATIONS[location]
        
        params = {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
            "timezone": "Asia/Irkutsk",
            "forecast_days": min(days, 16),
        }
        
        url = f"{OPENMETEO_BASE}/forecast"
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_forecast_response(data, loc["name"])
                else:
                    logger.error(f"Open-Meteo вернул {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка запроса погоды: {e}")
            return []
    
    def _parse_forecast_response(
        self,
        data: dict[str, Any],
        location_name: str
    ) -> list[WeatherData]:
        """Парсинг ответа API."""
        weather_list = []
        
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        precipitation = daily.get("precipitation_sum", [])
        wind_speed = daily.get("wind_speed_10m_max", [])
        weather_codes = daily.get("weather_code", [])
        
        for i in range(len(dates)):
            try:
                t_max = temp_max[i] if i < len(temp_max) else 0
                t_min = temp_min[i] if i < len(temp_min) else 0
                
                weather_list.append(WeatherData(
                    location=location_name,
                    date=dates[i],
                    temperature_max=t_max,
                    temperature_min=t_min,
                    temperature_mean=(t_max + t_min) / 2,
                    precipitation=precipitation[i] if i < len(precipitation) else 0,
                    wind_speed=wind_speed[i] if i < len(wind_speed) else 0,
                    weather_code=weather_codes[i] if i < len(weather_codes) else 0,
                    weather_description=WEATHER_CODES.get(
                        weather_codes[i] if i < len(weather_codes) else 0,
                        "Неизвестно"
                    ),
                ))
            except Exception as e:
                logger.debug(f"Ошибка парсинга дня {i}: {e}")
        
        return weather_list
    
    async def fetch_historical(
        self,
        location: str = "irkutsk",
        start_date: str = None,
        end_date: str = None
    ) -> list[WeatherData]:
        """
        Получить исторические данные.
        
        Args:
            location: Название локации
            start_date: Начальная дата (YYYY-MM-DD)
            end_date: Конечная дата (YYYY-MM-DD)
            
        Returns:
            Список WeatherData
        """
        if location not in LOCATIONS:
            logger.error(f"Неизвестная локация: {location}")
            return []
        
        await self._ensure_session()
        
        loc = LOCATIONS[location]
        
        # По умолчанию - последние 30 дней
        if not end_date:
            end_date = str(date.today() - timedelta(days=1))
        if not start_date:
            start_date = str(date.today() - timedelta(days=30))
        
        params = {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
            "timezone": "Asia/Irkutsk",
        }
        
        url = f"{OPENMETEO_BASE}/archive"
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_forecast_response(data, loc["name"])
                else:
                    logger.error(f"Open-Meteo Archive вернул {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка запроса исторических данных: {e}")
            return []


async def fetch_weather_forecast(
    locations: list[str] = None,
    days: int = 7
) -> dict[str, list[WeatherData]]:
    """
    Получить прогноз для всех локаций.
    
    Args:
        locations: Список локаций (по умолчанию все)
        days: Количество дней
        
    Returns:
        Словарь {location: [WeatherData]}
    """
    if locations is None:
        locations = list(LOCATIONS.keys())
    
    result = {}
    
    async with OpenMeteoParser() as parser:
        for loc in locations:
            weather = await parser.fetch_forecast(loc, days)
            result[loc] = weather
            logger.info(f"Получен прогноз для {loc}: {len(weather)} дней")
            await asyncio.sleep(0.2)  # Rate limiting
    
    return result


async def fetch_weather_historical(
    location: str = "irkutsk",
    days_back: int = 30
) -> list[WeatherData]:
    """
    Получить исторические данные погоды.
    
    Args:
        location: Локация
        days_back: Количество дней назад
        
    Returns:
        Список WeatherData
    """
    end_date = str(date.today() - timedelta(days=1))
    start_date = str(date.today() - timedelta(days=days_back))
    
    async with OpenMeteoParser() as parser:
        return await parser.fetch_historical(location, start_date, end_date)


def get_weather_impact(weather: WeatherData) -> str:
    """
    Оценить влияние погоды на туризм.
    
    Args:
        weather: Данные о погоде
        
    Returns:
        Оценка: positive, neutral, negative
    """
    # Критерии
    # Положительно: ясно/облачно, t > -10 зимой или > 15 летом, без осадков
    # Негативно: сильные осадки, штормовой ветер, экстремальные температуры
    
    bad_codes = {65, 67, 75, 82, 86, 95, 96, 99}  # Сильные осадки, грозы
    
    if weather.weather_code in bad_codes:
        return "negative"
    
    if weather.precipitation > 10:  # > 10 мм
        return "negative"
    
    if weather.wind_speed > 50:  # > 50 км/ч
        return "negative"
    
    if weather.temperature_max < -25 or weather.temperature_max > 35:
        return "negative"
    
    if weather.weather_code in {0, 1, 2} and weather.precipitation < 1:
        return "positive"
    
    return "neutral"


# Тест
async def test_weather_parser():
    """Тестирование парсера погоды."""
    print("=" * 50)
    print("Тест парсера Open-Meteo")
    print("=" * 50)
    
    # Прогноз
    print("\n--- Прогноз на 7 дней ---")
    forecasts = await fetch_weather_forecast(["irkutsk", "huzhir"], days=7)
    
    for loc, weather_list in forecasts.items():
        print(f"\n{loc.upper()}:")
        for w in weather_list[:3]:
            impact = get_weather_impact(w)
            print(f"  {w.date}: {w.temperature_min:.0f}..{w.temperature_max:.0f}°C, "
                  f"{w.weather_description}, {w.precipitation:.1f}мм [{impact}]")
    
    # Исторические
    print("\n--- Исторические данные (7 дней) ---")
    historical = await fetch_weather_historical("irkutsk", days_back=7)
    for w in historical:
        print(f"  {w.date}: {w.temperature_min:.0f}..{w.temperature_max:.0f}°C")


if __name__ == "__main__":
    asyncio.run(test_weather_parser())
