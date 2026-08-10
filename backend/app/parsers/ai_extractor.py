"""AI-powered извлечение данных с использованием Crawl4AI.

Crawl4AI - современный AI-ready веб-краулер, который:
- Конвертирует HTML в чистый Markdown
- Поддерживает LLM-based extraction
- Обходит защиты от ботов (stealth mode)
- Работает асинхронно

Документация: https://docs.crawl4ai.com/
"""
import asyncio
import logging
import json
import re
from typing import Any
from datetime import date

from app.parsers.base import (
    ParsedEvent, 
    parse_russian_date, 
    detect_event_type,
    BaseParser
)
from app.parsers.anti_detection import (
    rate_limiter,
    response_cache,
    get_realistic_headers,
)

logger = logging.getLogger(__name__)

# Флаг доступности Crawl4AI
CRAWL4AI_AVAILABLE = False

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.extraction_strategy import LLMExtractionStrategy, JsonCssExtractionStrategy
    CRAWL4AI_AVAILABLE = True
    logger.info("Crawl4AI успешно импортирован")
except ImportError:
    logger.warning(
        "Crawl4AI не установлен. Установите: pip install crawl4ai && crawl4ai-setup"
    )


# Схема для извлечения событий
EVENT_EXTRACTION_SCHEMA = {
    "name": "events",
    "baseSelector": "article, .event, .event-card, [data-event], .afisha-item",
    "fields": [
        {"name": "title", "selector": "h1, h2, h3, .title, .event-title, .name", "type": "text"},
        {"name": "date", "selector": ".date, .event-date, time, [datetime]", "type": "text"},
        {"name": "time", "selector": ".time, .event-time", "type": "text"},
        {"name": "location", "selector": ".place, .venue, .location, .address", "type": "text"},
        {"name": "price", "selector": ".price, .cost, .ticket-price", "type": "text"},
        {"name": "description", "selector": ".description, .text, .info, p", "type": "text"},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href"},
        {"name": "image", "selector": "img", "type": "attribute", "attribute": "src"},
    ]
}


# Сайты турбаз и отелей Байкала для AI extraction
BAIKAL_RESORT_SITES = [
    # Крупные турбазы
    "https://pegas-tur.ru/",  # Байкал Пегас
    "https://gremyachinsk.ru/",  # Гремячинск
    "https://baikal-riviera.ru/",  # Байкальская Ривьера
    "https://baikalworld.com/",  # Baikal World Hotel
    "https://chara-baikal.ru/",  # Чара (Ольхон)
    "https://darian.club/",  # Darian Club (Ольхон)

    # Отели Листвянки
    "https://mayakhotel.ru/",  # Маяк
    "https://anastasia-hotel.ru/",  # Анастасия
    "https://sozvezdiebaikala.ru/",  # Созвездие Байкала
    "https://baikalskayaskazka.ru/",  # Байкальская сказка

    # Базы Ольхона
    "https://baikalkhan.ru/",  # Байкал Хан
    "https://nikitas.ru/",  # Никита (Хужир)

    # Байкальск
    "https://sobolinaya.ru/",  # Соболиная

    # Аршан
    "https://arshan.ru/",  # Аршан

    # Слюдянка
    "https://baikal-kaktus.ru/",  # Кактус
]


async def extract_events_from_resorts(
    sites: list[str] | None = None,
    use_jina: bool = True
) -> list[ParsedEvent]:
    """
    Извлечь события с сайтов турбаз и отелей Байкала.

    Args:
        sites: Список URL (по умолчанию BAIKAL_RESORT_SITES)
        use_jina: Использовать Jina Reader (True) или Crawl4AI (False)

    Returns:
        Список ParsedEvent
    """
    sites = sites or BAIKAL_RESORT_SITES
    all_events = []
    seen_titles = set()

    for url in sites:
        try:
            if use_jina or not CRAWL4AI_AVAILABLE:
                events = await extract_events_simple(url, "resort")
            else:
                async with AIEventExtractor(headless=True) as extractor:
                    markdown = await extractor.extract_markdown(url)
                    if markdown:
                        events = await extractor.extract_events_from_markdown(
                            markdown, "resort"
                        )
                    else:
                        events = []

            # Дедупликация
            for event in events:
                title_key = event.title.lower().strip()[:50]
                if title_key not in seen_titles:
                    all_events.append(event)
                    seen_titles.add(title_key)

            logger.info(f"Сайт {url}: {len(events)} событий")
            await asyncio.sleep(0.5)  # Rate limiting

        except Exception as e:
            logger.error(f"Ошибка извлечения с {url}: {e}")
            continue

    logger.info(f"Всего событий с турбаз: {len(all_events)}")
    return all_events


class AIEventExtractor:
    """
    AI-powered извлечение событий с веб-страниц.
    
    Использует Crawl4AI для:
    1. Загрузки страницы (включая JS-рендеринг)
    2. Конвертации в Markdown
    3. Извлечения структурированных данных
    """
    
    def __init__(
        self,
        headless: bool = True,
        verbose: bool = False,
        use_stealth: bool = True
    ):
        self.headless = headless
        self.verbose = verbose
        self.use_stealth = use_stealth
        self._crawler = None
    
    async def __aenter__(self):
        if CRAWL4AI_AVAILABLE:
            browser_config = BrowserConfig(
                headless=self.headless,
                verbose=self.verbose,
            )
            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._crawler:
            await self._crawler.__aexit__(exc_type, exc_val, exc_tb)
    
    async def extract_markdown(self, url: str, use_cache: bool = True) -> str | None:
        """
        Извлечь Markdown контент со страницы.
        
        Args:
            url: URL страницы
            use_cache: Использовать кэш
            
        Returns:
            Markdown текст или None
        """
        # Проверяем кэш
        if use_cache:
            cached = response_cache.get(url)
            if cached:
                logger.debug(f"Используем кэш для {url}")
                return cached
        
        if not CRAWL4AI_AVAILABLE:
            logger.error("Crawl4AI не доступен")
            return None
        
        # Rate limiting
        await rate_limiter.wait_for(url)
        
        try:
            config = CrawlerRunConfig(
                wait_until="domcontentloaded",  # Быстрее чем networkidle
                page_timeout=30000,
            )
            result = await self._crawler.arun(url=url, config=config)
            
            if result.success:
                await rate_limiter.report_success(url)
                # Сохраняем в кэш
                if use_cache and result.markdown:
                    response_cache.set(url, result.markdown)
                return result.markdown
            else:
                logger.error(f"Ошибка краулинга {url}: {result.error_message}")
                await rate_limiter.report_error(url, 500)
                return None
                
        except Exception as e:
            logger.error(f"Ошибка извлечения {url}: {e}")
            await rate_limiter.report_error(url)
            return None
    
    async def extract_events_css(
        self,
        url: str,
        schema: dict | None = None
    ) -> list[dict[str, Any]]:
        """
        Извлечь события используя CSS селекторы.
        
        Args:
            url: URL страницы
            schema: Схема извлечения (по умолчанию EVENT_EXTRACTION_SCHEMA)
            
        Returns:
            Список извлечённых событий
        """
        if not CRAWL4AI_AVAILABLE:
            logger.error("Crawl4AI не доступен")
            return []
        
        schema = schema or EVENT_EXTRACTION_SCHEMA
        
        try:
            extraction_strategy = JsonCssExtractionStrategy(schema, verbose=self.verbose)
            
            config = CrawlerRunConfig(
                extraction_strategy=extraction_strategy,
                wait_until="networkidle",
            )
            
            result = await self._crawler.arun(url=url, config=config)
            
            if result.success and result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    return data if isinstance(data, list) else [data]
                except json.JSONDecodeError:
                    logger.warning(f"Не удалось распарсить JSON из {url}")
                    return []
            
            return []
            
        except Exception as e:
            logger.error(f"Ошибка CSS extraction {url}: {e}")
            return []
    
    async def extract_events_from_markdown(
        self,
        markdown: str,
        source: str
    ) -> list[ParsedEvent]:
        """
        Извлечь события из Markdown текста с помощью regex.
        
        Это fallback метод, когда LLM недоступен.
        
        Args:
            markdown: Markdown текст страницы
            source: Название источника
            
        Returns:
            Список ParsedEvent
        """
        events = []
        
        # Паттерны для поиска событий
        # Формат: заголовок, дата, место, цена
        event_blocks = re.split(r'\n#{1,3}\s+', markdown)
        
        for block in event_blocks:
            if len(block) < 20:
                continue
            
            lines = block.strip().split('\n')
            if not lines:
                continue
            
            title = lines[0].strip()
            if len(title) < 5 or len(title) > 200:
                continue
            
            # Пропускаем служебные заголовки
            skip_words = ['меню', 'навигация', 'поиск', 'войти', 'регистрация', 'корзина']
            if any(w in title.lower() for w in skip_words):
                continue
            
            # Ищем дату
            date_match = re.search(
                r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)',
                block.lower()
            )
            event_date = parse_russian_date(date_match.group(0)) if date_match else str(date.today())
            
            # Ищем цену
            price_match = re.search(r'от\s*(\d+)\s*(?:руб|₽|р\.?)', block.lower())
            price = price_match.group(0) if price_match else None
            price_min = int(price_match.group(1)) if price_match else None
            
            # Ищем место
            location_match = re.search(
                r'(?:место|площадка|адрес)[:\s]+([^\n]+)',
                block.lower()
            )
            location = location_match.group(1).strip() if location_match else "Иркутск"
            
            # Описание - первые 2-3 строки после заголовка
            description = ' '.join(lines[1:4]).strip()[:500]
            
            event_id = BaseParser.generate_event_id(title, event_date, source)
            event_type = detect_event_type(title, description)
            
            try:
                event = ParsedEvent(
                    id=event_id,
                    title=title,
                    description=description,
                    date_start=event_date,
                    event_type=event_type,
                    location=location,
                    price=price,
                    price_min=price_min,
                    source=source,
                )
                events.append(event)
            except Exception as e:
                logger.debug(f"Не удалось создать событие: {e}")
        
        return events


# Простой fallback без Crawl4AI - использует Jina Reader API
async def fetch_markdown_jina(url: str, use_cache: bool = True) -> str | None:
    """
    Получить Markdown через бесплатный Jina Reader API.
    
    Jina Reader: https://r.jina.ai/{URL} -> Markdown
    
    Args:
        url: URL страницы
        use_cache: Использовать кэш
        
    Returns:
        Markdown текст
    """
    import aiohttp
    
    # Проверяем кэш (ключ - оригинальный URL)
    if use_cache:
        cached = response_cache.get(url)
        if cached:
            logger.debug(f"Jina: кэш для {url}")
            return cached
    
    jina_url = f"https://r.jina.ai/{url}"

    # Прод-IP получает от Jina 451 Unavailable For Legal Reasons. Без этой
    # проверки каждый парсер честно ждал бы своей очереди и растущего бэкоффа,
    # чтобы получить тот же отказ.
    if rate_limiter.is_unavailable(jina_url):
        logger.debug("Jina Reader недоступен для этого хоста, пропускаем")
        return None

    # Rate limiting (для Jina API)
    await rate_limiter.wait_for("r.jina.ai")

    headers = get_realistic_headers()
    headers["Accept"] = "text/markdown"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                jina_url,
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    await rate_limiter.report_success("r.jina.ai")
                    # Кэшируем
                    if use_cache and text:
                        response_cache.set(url, text)
                    return text
                else:
                    logger.warning(f"Jina Reader вернул {response.status}")
                    await rate_limiter.report_error("r.jina.ai", response.status)
                    return None
    except Exception as e:
        logger.error(f"Ошибка Jina Reader: {e}")
        await rate_limiter.report_error("r.jina.ai")
        return None


async def extract_events_simple(
    url: str,
    source: str
) -> list[ParsedEvent]:
    """
    Простое извлечение событий без Crawl4AI.
    
    Использует Jina Reader API + regex парсинг.
    
    Args:
        url: URL страницы
        source: Название источника
        
    Returns:
        Список ParsedEvent
    """
    markdown = await fetch_markdown_jina(url)
    if not markdown:
        return []
    
    extractor = AIEventExtractor()
    return await extractor.extract_events_from_markdown(markdown, source)


# Тестовая функция
async def test_extractor():
    """Тест AI extractor."""
    test_url = "https://irk.zeroevent.ru/"
    
    print(f"Тестируем извлечение с {test_url}")
    print(f"Crawl4AI доступен: {CRAWL4AI_AVAILABLE}")
    
    if CRAWL4AI_AVAILABLE:
        async with AIEventExtractor(headless=True, verbose=True) as extractor:
            markdown = await extractor.extract_markdown(test_url)
            if markdown:
                print(f"Получено {len(markdown)} символов Markdown")
                events = await extractor.extract_events_from_markdown(markdown, "zeroevent")
                print(f"Извлечено {len(events)} событий")
                for event in events[:3]:
                    print(f"  - {event.title} ({event.date_start})")
    else:
        print("Используем Jina Reader fallback...")
        events = await extract_events_simple(test_url, "zeroevent")
        print(f"Извлечено {len(events)} событий")
        for event in events[:3]:
            print(f"  - {event.title} ({event.date_start})")


if __name__ == "__main__":
    asyncio.run(test_extractor())
