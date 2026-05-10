"""Парсер событий из Telegram каналов.

Telegram каналы региона:
- @visitirkutskregion - официальный туризм области
- @baikalgo - туристический проект
- @baikalgora - горнолыжка
- @glagol38 - культурная жизнь

Методы извлечения:
1. Telethon (MTProto) - для авторизованного доступа
2. Telegram Web Preview - для публичных каналов без авторизации

Требуется для Telethon:
- api_id и api_hash с my.telegram.org
- Добавить в .env:
  TELEGRAM_API_ID=...
  TELEGRAM_API_HASH=...
"""
import asyncio
import aiohttp
import re
import logging
import hashlib
import os
from datetime import datetime, date, timedelta
from typing import Any
from dataclasses import dataclass

from app.parsers.base import (
    ParsedEvent,
    parse_russian_date,
    detect_event_type,
)

logger = logging.getLogger(__name__)

# Проверяем доступность Telethon
TELETHON_AVAILABLE = False
try:
    from telethon import TelegramClient
    from telethon.tl.functions.messages import GetHistoryRequest
    from telethon.tl.types import PeerChannel
    TELETHON_AVAILABLE = True
    logger.info("Telethon успешно импортирован")
except ImportError:
    logger.warning("Telethon не установлен. Установите: pip install telethon")


@dataclass
class TelegramChannel:
    """Конфигурация Telegram канала."""
    username: str  # Без @
    name: str
    category: str  # tourism, events, culture
    priority: int = 1


# Каналы для парсинга (расширенный список)
BAIKAL_CHANNELS = [
    # Официальные и крупные туризм
    TelegramChannel("visitirkutskregion", "Туризм Иркутской области", "tourism", 1),
    TelegramChannel("baikalgo", "Baikal Go", "tourism", 1),
    TelegramChannel("baikalgora", "Байкалгора", "tourism", 2),
    TelegramChannel("OkoloBaikala", "Около Байкала", "tourism", 3),
    TelegramChannel("baikal_teleport", "Байкал Телепорт", "news", 3),

    # Культура и события
    TelegramChannel("glagol38", "Глагол 38", "culture", 2),
    TelegramChannel("irkutsk_events", "События Иркутска", "events", 2),
    TelegramChannel("afisha_irk", "Афиша Иркутск", "events", 2),

    # Турбазы и отели Байкала
    TelegramChannel("baikal_pegas", "Байкал Пегас Турбаза", "resort", 3),
    TelegramChannel("gremyachinsk", "Гремячинск Турбаза", "resort", 3),
    TelegramChannel("baikalskaya_riviera", "Байкальская Ривьера", "resort", 3),
    TelegramChannel("hotels_baikal", "Отели Байкала", "hotels", 3),

    # Активный туризм
    TelegramChannel("baikaltrip", "Байкал Трип", "tours", 2),
    TelegramChannel("avangard_tour", "Авангард Тур", "tours", 3),
    TelegramChannel("baikal_adventure", "Байкал Приключения", "tours", 3),
    TelegramChannel("greatbaikal", "Great Baikal", "tours", 2),

    # Зимний туризм
    TelegramChannel("baikalice", "Байкал Лёд", "winter", 3),
    TelegramChannel("baikalfest", "Байкал Фестиваль", "winter", 3),

    # Ольхон и Малое море
    TelegramChannel("olkhon", "Ольхон", "resort", 2),
    TelegramChannel("maloe_more", "Малое Море", "resort", 3),
]


_DATE_PATTERNS = [
    # "15 мая", "с 15 по 20 мая", "15-17 февраля"
    re.compile(
        r'(?:с\s+)?(\d{1,2})(?:\s*[-–]\s*\d{1,2})?'
        r'\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)'
        r'(?:\s+(\d{4}))?',
        re.IGNORECASE,
    ),
    # "15.03.2026", "15.03"
    re.compile(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b'),
    # "2026-03-15"
    re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
]

_VENUE_KEYWORDS = (
    r'дворец|театр|музей|галерея|центр|клуб|филармония|'
    r'ДК|библиотека|зал|арена|стадион|отель|гостиница|парк|площадь'
)

_VENUE_PATTERNS = [
    re.compile(r'📍\s*([^\n]{3,60})'),
    re.compile(r'(?:место|где|адрес|площадка|локация)\s*[:\-–]\s*([^\n]{3,80})', re.IGNORECASE),
    re.compile(
        rf'(?:^|[.!?]\s)(?:в|на)\s+((?:[А-ЯЁ][а-яё]{{1,20}}\s+){{0,3}}(?:{_VENUE_KEYWORDS})(?:\s*«[^»]+»)?)',
        re.IGNORECASE | re.MULTILINE,
    ),
]


def _extract_event_date(text: str) -> str | None:
    """Извлечь дату события из текста сообщения."""
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            result = parse_russian_date(m.group(0))
            if result:
                return result
    return None


def _extract_location_from_text(text: str) -> str:
    """Извлечь место проведения из текста."""
    for pattern in _VENUE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()[:100]
    return "Иркутск"


class TelegramEventParser:
    """
    Парсер событий из Telegram каналов.
    
    Использует Telethon для MTProto доступа к Telegram.
    Требует api_id и api_hash.
    """
    
    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        session_name: str = "baikal_parser"
    ):
        self.api_id = api_id or int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH", "")
        self.session_name = session_name
        self._client: "TelegramClient" | None = None
    
    async def __aenter__(self):
        if TELETHON_AVAILABLE and self.api_id and self.api_hash:
            self._client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash
            )
            await self._client.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.disconnect()
    
    async def fetch_channel_messages(
        self,
        channel_username: str,
        limit: int = 50,
        days_back: int = 7
    ) -> list[dict[str, Any]]:
        """
        Получить сообщения из канала.
        
        Args:
            channel_username: Username канала (без @)
            limit: Максимум сообщений
            days_back: Сколько дней назад искать
            
        Returns:
            Список сообщений
        """
        if not self._client:
            logger.warning("Telegram клиент не инициализирован")
            return []

        messages = []
        min_date = datetime.now() - timedelta(days=days_back)

        try:
            channel = await self._client.get_entity(channel_username)

            async for message in self._client.iter_messages(
                channel,
                limit=limit,
                offset_date=datetime.now()
            ):
                if message.date.replace(tzinfo=None) < min_date:
                    break

                if message.text:
                    # Best-effort извлечение url изображения. У Telethon нет
                    # прямого file_url; в production-режиме можно подключить
                    # download_media. Здесь — только web-preview /
                    # external link, если он есть в media.
                    image_url: str | None = None
                    media = getattr(message, "media", None)
                    if media is not None:
                        web_preview = getattr(media, "webpage", None)
                        if web_preview is not None:
                            url_attr = getattr(web_preview, "photo", None) or getattr(
                                web_preview, "url", None
                            )
                            if isinstance(url_attr, str):
                                image_url = url_attr

                    messages.append({
                        "id": message.id,
                        "text": message.text,
                        "date": message.date,
                        "views": getattr(message, 'views', 0),
                        "url": f"https://t.me/{channel_username}/{message.id}",
                        "image_url": image_url,
                    })
            
            logger.info(f"Получено {len(messages)} сообщений из @{channel_username}")
            
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из @{channel_username}: {e}")
        
        return messages
    
    async def extract_events_from_messages(
        self,
        messages: list[dict[str, Any]],
        source: str
    ) -> list[ParsedEvent]:
        """
        Извлечь события из сообщений.
        
        Args:
            messages: Список сообщений
            source: Название источника
            
        Returns:
            Список ParsedEvent
        """
        events = []
        
        for msg in messages:
            event = await self._parse_message(msg, source)
            if event:
                events.append(event)
        
        return events
    
    async def _is_real_event(self, text: str) -> bool:
        """LLM-классификация: это реальное мероприятие или спам/новость?"""
        try:
            from pydantic import BaseModel, Field
            from typing import Literal
            from app.services.main_agent import get_llm_with_tools

            class EventCheck(BaseModel):
                is_event: bool = Field(description="Это анонс мероприятия/события с конкретной датой и местом?")
                category: Literal["event", "spam"] = Field(description="event=мероприятие, spam=поздравление/новость/реклама")

            llm = get_llm_with_tools()
            base_llm = llm.bound if hasattr(llm, "bound") else llm
            structured = base_llm.with_structured_output(EventCheck)
            result = await structured.ainvoke(
                f"Классифицируй пост из Telegram-канала туризма. Это анонс конкретного мероприятия (концерт, выставка, фестиваль, экскурсия) или это спам (поздравление, новость, реклама, ЖКХ)?\n\nТекст: {text[:500]}"
            )
            return result.is_event and result.category == "event"
        except Exception as e:
            logger.debug(f"LLM event classification failed, allowing: {e}")
            return True

    async def _parse_message(self, msg: dict[str, Any], source: str) -> ParsedEvent | None:
        """Парсинг одного сообщения в событие."""
        text = msg.get("text", "")
        if not text or len(text) < 30:
            return None
        
        event_keywords = [
            'концерт', 'выставка', 'фестиваль', 'мастер-класс',
            'экскурсия', 'тур ', 'поход', 'праздник', 'открытие',
            'спектакль', 'премьера', 'шоу', 'форум', 'семинар',
            'конференция', 'ярмарка', 'марафон', 'вечер ',
            'festival', 'concert', 'show', 'exhibition', 'tour',
        ]
        
        text_lower = text.lower()
        if not any(kw in text_lower for kw in event_keywords):
            return None
        
        if not await self._is_real_event(text):
            return None
        
        # Извлекаем заголовок (первая строка или жирный текст)
        lines = text.strip().split('\n')
        title = lines[0].strip()
        
        # Убираем эмодзи и форматирование
        title = re.sub(r'[\U0001F300-\U0001F9FF]', '', title)
        title = re.sub(r'[*_~`]', '', title)
        title = title.strip()
        
        if len(title) < 5 or len(title) > 150:
            name_match = re.search(r'«([^»]+)»|"([^"]+)"', text)
            if name_match:
                title = name_match.group(1) or name_match.group(2)
            else:
                return None
        
        _day_of_week_re = re.compile(
            r'понедельник|вторник|сред|четверг|пятниц|суббот|воскресень|настроен',
            re.IGNORECASE,
        )
        title_lower = title.lower()
        if (len(title) < 50 and _day_of_week_re.search(title_lower)
                and not any(kw in title_lower for kw in event_keywords)
                and title.upper() == title):
            return None
        
        event_date = _extract_event_date(text)
        
        if not event_date:
            msg_date = msg.get("date")
            if msg_date:
                event_date = str(msg_date.date())
            else:
                return None
        
        # Валидация: отклоняем даты >1 года назад или >1 года вперёд
        try:
            from datetime import date as _date
            parsed = _date.fromisoformat(event_date)
            today = _date.today()
            if abs((parsed - today).days) > 365:
                return None
        except (ValueError, TypeError):
            return None
        
        # Время
        time_match = re.search(r'(\d{1,2}):(\d{2})', text)
        event_time = time_match.group(0) if time_match else None
        
        location = _extract_location_from_text(text)
        
        # Цена
        price_match = re.search(r'(?:от\s*)?(\d[\d\s]*)\s*(?:руб|₽|р\.?)', text)
        price = price_match.group(0).strip() if price_match else None
        price_min = None
        if price_match:
            try:
                price_min = int(re.sub(r'\s+', '', price_match.group(1)))
            except ValueError:
                pass
        
        # Описание
        description = text[:500]

        # Возрастное ограничение из текста
        age_restriction: str | None = None
        m_age = re.search(r"\b(\d{1,2})\s*\+", text)
        if m_age:
            try:
                age = int(m_age.group(1))
                if 0 < age <= 21:
                    age_restriction = f"{age}+"
            except ValueError:
                pass

        image_url = msg.get("image_url")

        # Генерируем ID
        event_id = f"tg_{source}_{hashlib.md5(f'{title}{event_date}'.encode()).hexdigest()[:10]}"

        try:
            return ParsedEvent(
                id=event_id,
                title=title,
                description=description,
                date_start=event_date,
                time_start=event_time,
                event_type=detect_event_type(title, description),
                location=location,
                price=price,
                price_min=price_min,
                age_restriction=age_restriction,
                source=f"telegram_{source}",
                url=msg.get("url"),
                image_url=image_url,
            )
        except Exception as e:
            logger.debug(f"Ошибка создания события: {e}")
            return None


class TelegramWebParser:
    """
    Парсер Telegram каналов через веб-превью.
    
    Не требует авторизации, но имеет ограничения:
    - Только последние ~20 сообщений
    - Только публичные каналы
    """
    
    async def fetch_channel_preview(
        self,
        channel_username: str
    ) -> list[dict[str, Any]]:
        """
        Получить превью канала через t.me/s/.
        
        Args:
            channel_username: Username канала
            
        Returns:
            Список сообщений
        """
        url = f"https://t.me/s/{channel_username}"
        messages = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                    }
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        messages = self._parse_preview_html(html, channel_username)
                    else:
                        logger.warning(f"Telegram вернул {response.status} для @{channel_username}")
        
        except Exception as e:
            logger.error(f"Ошибка получения превью @{channel_username}: {e}")
        
        return messages
    
    def _parse_preview_html(self, html: str, channel: str) -> list[dict[str, Any]]:
        """Парсинг HTML превью канала."""
        from bs4 import BeautifulSoup
        
        messages = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем сообщения
        for msg_div in soup.find_all('div', class_='tgme_widget_message'):
            try:
                # ID сообщения
                msg_id = msg_div.get('data-post', '').split('/')[-1]
                
                # Текст
                text_div = msg_div.find('div', class_='tgme_widget_message_text')
                text = text_div.get_text(separator='\n', strip=True) if text_div else ""
                
                if not text:
                    continue
                
                # Дата
                time_tag = msg_div.find('time', class_='datetime')
                msg_date = None
                if time_tag and time_tag.get('datetime'):
                    try:
                        msg_date = datetime.fromisoformat(
                            time_tag['datetime'].replace('Z', '+00:00')
                        )
                    except (ValueError, AttributeError, TypeError):
                        pass

                # image_url из background-image превью или photo wrap
                image_url: str | None = None
                photo_wrap = msg_div.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_wrap and photo_wrap.get('style'):
                    m_bg = re.search(
                        r"background-image:\s*url\(['\"]?(https?://[^)'\"]+)",
                        photo_wrap['style'],
                    )
                    if m_bg:
                        image_url = m_bg.group(1)

                messages.append({
                    "id": msg_id,
                    "text": text,
                    "date": msg_date,
                    "url": f"https://t.me/{channel}/{msg_id}",
                    "image_url": image_url,
                })
                
            except Exception as e:
                logger.debug(f"Ошибка парсинга сообщения: {e}")
        
        logger.info(f"Получено {len(messages)} сообщений из @{channel} (web preview)")
        return messages


async def fetch_events_telegram(
    channels: list[TelegramChannel] | None = None,
    use_telethon: bool = True,
    days_back: int = 7,
    limit_per_channel: int = 50
) -> list[ParsedEvent]:
    """
    Получить события из Telegram каналов.
    
    Args:
        channels: Список каналов (по умолчанию BAIKAL_CHANNELS)
        use_telethon: Использовать Telethon (требует api_id/hash)
        days_back: Сколько дней назад искать
        limit_per_channel: Лимит сообщений на канал
        
    Returns:
        Список ParsedEvent
    """
    if channels is None:
        channels = BAIKAL_CHANNELS
    
    all_events = []
    seen_ids = set()
    
    if use_telethon and TELETHON_AVAILABLE:
        # Используем Telethon
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        
        if api_id and api_hash:
            async with TelegramEventParser(int(api_id), api_hash) as parser:
                for channel in channels:
                    messages = await parser.fetch_channel_messages(
                        channel.username,
                        limit=limit_per_channel,
                        days_back=days_back
                    )
                    events = await parser.extract_events_from_messages(
                        messages,
                        channel.username
                    )
                    
                    for event in events:
                        if event.id not in seen_ids:
                            all_events.append(event)
                            seen_ids.add(event.id)
                    
                    await asyncio.sleep(1)  # Rate limiting
        else:
            logger.warning("TELEGRAM_API_ID/HASH не заданы, используем web preview")
            use_telethon = False
    
    if not use_telethon:
        web_parser = TelegramWebParser()
        telethon_parser = TelegramEventParser()

        for channel in channels:
            try:
                messages = await web_parser.fetch_channel_preview(channel.username)
            except Exception as exc:
                logger.warning(f"[telegram] @{channel.username}: web preview failed: {exc}")
                messages = []

            if not messages:
                logger.info(f"[telegram] @{channel.username}: 0 сообщений в web preview")
                await asyncio.sleep(0.5)
                continue

            events = await telethon_parser.extract_events_from_messages(
                messages, channel.username
            )

            new_for_channel = 0
            for event in events:
                if event.id not in seen_ids:
                    all_events.append(event)
                    seen_ids.add(event.id)
                    new_for_channel += 1

            logger.info(
                f"[telegram] @{channel.username}: messages={len(messages)} "
                f"events_extracted={len(events)} new={new_for_channel}"
            )
            await asyncio.sleep(0.5)

    logger.info(f"Всего получено {len(all_events)} событий из Telegram (каналов: {len(channels)})")
    return all_events


# Тест
async def test_telegram_parser():
    """Тестирование парсера Telegram."""
    print("=" * 50)
    print("Тест парсера Telegram каналов")
    print("=" * 50)
    
    # Тестируем web preview (без авторизации)
    events = await fetch_events_telegram(
        channels=[BAIKAL_CHANNELS[0], BAIKAL_CHANNELS[1]],
        use_telethon=False
    )
    
    print(f"\nВсего получено событий: {len(events)}")
    
    for event in events[:5]:
        print(f"\n- {event.title}")
        print(f"  Дата: {event.date_start}")
        print(f"  Источник: {event.source}")
        print(f"  URL: {event.url}")


if __name__ == "__main__":
    asyncio.run(test_telegram_parser())
