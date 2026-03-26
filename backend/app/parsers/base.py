"""Базовый класс для всех парсеров.

Предоставляет общую функциональность:
- Retry логика с exponential backoff
- Rate limiting
- Единый формат логирования
- Валидация данных
"""
import asyncio
import logging
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Any
from dataclasses import dataclass, field

import aiohttp
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.parsers.anti_detection import get_random_user_agent

logger = logging.getLogger(__name__)


class ParsedEvent(BaseModel):
    """Единая схема события для всех парсеров."""
    
    id: str = Field(..., description="Уникальный идентификатор")
    title: str = Field(..., min_length=1, description="Название события")
    description: str | None = Field(None, description="Описание")
    date_start: str = Field(..., description="Дата начала (YYYY-MM-DD)")
    date_end: str | None = Field(None, description="Дата окончания")
    time_start: str | None = Field(None, description="Время начала (HH:MM)")
    event_type: str = Field("event", description="Тип события")
    location: str = Field("Иркутск", description="Место проведения")
    address: str | None = Field(None, description="Адрес")
    price: str | None = Field(None, description="Цена/диапазон цен")
    price_min: int | None = Field(None, description="Минимальная цена")
    price_max: int | None = Field(None, description="Максимальная цена")
    source: str = Field(..., description="Источник данных")
    url: str | None = Field(None, description="Ссылка на событие")
    image_url: str | None = Field(None, description="URL изображения")
    category: str | None = Field(None, description="Категория")
    tags: list[str] = Field(default_factory=list, description="Теги")
    parsed_at: datetime = Field(default_factory=datetime.now, description="Время парсинга")
    
    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_validator('date_start', 'date_end', mode='before')
    @classmethod
    def validate_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return str(v)
        return v


@dataclass
class ParserConfig:
    """Конфигурация парсера."""

    name: str
    source: str
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_delay: float = 0.5
    user_agent: str = field(default_factory=get_random_user_agent)
    headers: dict[str, str] = field(default_factory=lambda: {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    })


class BaseParser(ABC):
    """Базовый класс парсера с общей логикой."""
    
    def __init__(self, config: ParserConfig):
        self.config = config
        self.logger = logging.getLogger(f"parser.{config.name}")
        self._session: aiohttp.ClientSession | None = None
        self._request_count = 0
        self._error_count = 0
        self._last_request_time = 0
    
    async def __aenter__(self):
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session()
    
    async def _create_session(self):
        """Создать HTTP сессию."""
        headers = {
            "User-Agent": self.config.user_agent,
            **self.config.headers
        }
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
    
    async def _close_session(self):
        """Закрыть HTTP сессию."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _rate_limit(self):
        """Применить rate limiting."""
        try:
            loop = asyncio.get_running_loop()
            now = loop.time()
        except RuntimeError:
            now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            await asyncio.sleep(self.config.rate_limit_delay - elapsed)
        try:
            loop = asyncio.get_running_loop()
            self._last_request_time = loop.time()
        except RuntimeError:
            self._last_request_time = asyncio.get_event_loop().time()
    
    async def fetch_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs
    ) -> str | None:
        """
        Выполнить HTTP запрос с retry логикой.
        
        Args:
            url: URL для запроса
            method: HTTP метод
            **kwargs: Дополнительные параметры для aiohttp
            
        Returns:
            Текст ответа или None при ошибке
        """
        if not self._session:
            await self._create_session()
        
        for attempt in range(self.config.max_retries):
            try:
                await self._rate_limit()
                self._request_count += 1
                
                async with self._session.request(method, url, ssl=settings.parser_ssl_verify, **kwargs) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        # Too Many Requests - увеличиваем задержку
                        delay = self.config.retry_delay * (2 ** attempt)
                        self.logger.warning(f"Rate limited, waiting {delay}s")
                        await asyncio.sleep(delay)
                    elif response.status >= 500:
                        # Server error - повторяем
                        delay = self.config.retry_delay * (2 ** attempt)
                        self.logger.warning(f"Server error {response.status}, retry in {delay}s")
                        await asyncio.sleep(delay)
                    else:
                        self.logger.error(f"HTTP {response.status} for {url}")
                        self._error_count += 1
                        return None
                        
            except TimeoutError:
                delay = self.config.retry_delay * (2 ** attempt)
                self.logger.warning(f"Timeout for {url}, retry in {delay}s")
                await asyncio.sleep(delay)
            except aiohttp.ClientError as e:
                self.logger.error(f"Client error for {url}: {e}")
                self._error_count += 1
                delay = self.config.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            except Exception as e:
                self.logger.error(f"Unexpected error for {url}: {e}")
                self._error_count += 1
                return None
        
        self.logger.error(f"Failed after {self.config.max_retries} retries: {url}")
        return None
    
    @staticmethod
    def generate_event_id(title: str, date_str: str, source: str) -> str:
        """Генерация уникального ID события."""
        content = f"{source}_{date_str}_{title}"
        return f"{source}_{hashlib.md5(content.encode()).hexdigest()[:12]}"
    
    @staticmethod
    def clean_text(text: str, max_length: int = 500) -> str:
        """Очистка текста от лишних пробелов и HTML."""
        import re
        if not text:
            return ""
        # Удаляем HTML теги
        clean = re.sub(r'<[^>]+>', ' ', text)
        # Нормализуем пробелы
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Ограничиваем длину
        if len(clean) > max_length:
            clean = clean[:max_length-3] + "..."
        return clean
    
    @abstractmethod
    async def fetch_events(self, **kwargs) -> list[ParsedEvent]:
        """
        Получить список событий.
        
        Должен быть реализован в каждом парсере.
        """
        pass
    
    def get_stats(self) -> dict[str, Any]:
        """Получить статистику парсера."""
        return {
            "parser": self.config.name,
            "source": self.config.source,
            "requests": self._request_count,
            "errors": self._error_count,
            "error_rate": self._error_count / max(1, self._request_count),
        }
    
    def log_stats(self):
        """Залогировать статистику."""
        stats = self.get_stats()
        self.logger.info(
            f"Parser {stats['parser']}: "
            f"{stats['requests']} requests, "
            f"{stats['errors']} errors "
            f"({stats['error_rate']:.1%} error rate)"
        )


# Вспомогательные функции для парсинга дат

RUSSIAN_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


def parse_russian_date(date_str: str, default_year: int | None = None) -> str | None:
    """
    Парсинг русской даты в формат YYYY-MM-DD.
    
    Примеры:
        - "15 февраля" -> "2026-02-15"
        - "3 марта 2026" -> "2026-03-03"
        - "15.02.2026" -> "2026-02-15"
    """
    import re
    
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    today = date.today()
    year = default_year or today.year
    
    # Формат: "15 февраля" или "15 февраля 2026"
    match = re.search(r'(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?', date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        if match.group(3):
            year = int(match.group(3))
        
        month = RUSSIAN_MONTHS.get(month_name)
        if month:
            # Если месяц уже прошёл - следующий год
            if month < today.month or (month == today.month and day < today.day):
                if not match.group(3):  # год не указан явно
                    year = today.year + 1
            return f"{year}-{month:02d}-{day:02d}"
    
    # Формат: "15.02.2026" или "15.02"
    match = re.search(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?', date_str)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        if match.group(3):
            year = int(match.group(3))
            if year < 100:
                year += 2000
        return f"{year}-{month:02d}-{day:02d}"
    
    return None


def detect_event_type(title: str, description: str = "") -> str:
    """Определить тип события по названию и описанию."""
    text = f"{title} {description}".lower()
    
    categories = {
        "concert": ["концерт", "stand up", "стендап", "шоу", "выступление"],
        "theater": ["балет", "спектакль", "опера", "театр", "мюзикл", "драма"],
        "exhibition": ["выставка", "экспозиция", "вернисаж", "галерея"],
        "festival": ["фестиваль", "праздник", "карнавал", "фест"],
        "sport": ["матч", "чемпионат", "турнир", "марафон", "соревнование", "хоккей", "футбол"],
        "business": ["конференция", "форум", "саммит", "семинар", "мастер-класс"],
        "cinema": ["фильм", "кино", "премьера", "показ"],
        "kids": ["детский", "для детей", "дети", "семейный"],
    }
    
    for event_type, keywords in categories.items():
        if any(kw in text for kw in keywords):
            return event_type
    
    return "event"
