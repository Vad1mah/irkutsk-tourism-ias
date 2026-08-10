"""Модуль защиты от блокировок при парсинге.

Стратегии:
1. Адаптивный Rate Limiting - умные задержки между запросами
2. Кэширование - не запрашивать одно и то же дважды
3. Ротация User-Agent - выглядеть как разные браузеры
4. Имитация поведения - случайные паузы

Без прокси - для учебного проекта достаточно.
"""

import asyncio
import random
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

# === User-Agent ротация ===

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
]


def get_random_user_agent() -> str:
    """Случайный User-Agent."""
    return random.choice(USER_AGENTS)


def get_realistic_headers(referer: str | None = None) -> dict[str, str]:
    """Реалистичные HTTP заголовки."""
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# === Адаптивный Rate Limiter ===

@dataclass
class DomainState:
    """Состояние домена для rate limiting."""
    last_request: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    errors_count: int = 0
    blocked_until: datetime | None = None
    
    def is_blocked(self) -> bool:
        if self.blocked_until and datetime.now() < self.blocked_until:
            return True
        return False
    
    def get_delay(self) -> float:
        """Рассчитать задержку на основе истории."""
        base_delay = 5.0  # Базовая задержка 5 сек
        
        # Увеличиваем при ошибках
        if self.errors_count > 0:
            base_delay += self.errors_count * 10  # +10 сек за каждую ошибку
        
        # Увеличиваем при частых запросах
        if self.request_count > 5:
            base_delay += (self.request_count - 5) * 2
        
        # Добавляем случайность (±30%)
        jitter = base_delay * random.uniform(-0.3, 0.3)
        
        return max(3.0, min(base_delay + jitter, 60.0))  # От 3 до 60 сек


class AdaptiveRateLimiter:
    """Адаптивный rate limiter с учётом состояния каждого домена."""

    MAX_DOMAINS = 100  # Лимит доменов в памяти
    # Коды, после которых повторять запрос бессмысленно: это отказ по существу
    # (география, отсутствие прав), а не временная перегрузка.
    TERMINAL_STATUSES = frozenset({401, 451})

    def __init__(self):
        self.domains: dict[str, DomainState] = {}
        self._unavailable: set[str] = set()
        self._lock = asyncio.Lock()
    
    def _get_domain(self, url: str) -> str:
        """Извлечь домен из URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]

    def _cleanup_inactive_domains(self):
        """Удалить неактивные домены."""
        now = datetime.now()
        inactive = [
            d for d, state in self.domains.items()
            if (now - state.last_request).total_seconds() > 3600  # Неактивен > 1 часа
        ]
        for domain in inactive[:50]:  # Удаляем до 50 за раз
            del self.domains[domain]
        if inactive:
            logger.debug(f"Очистка rate limiter: удалено {len(inactive[:50])} неактивных доменов")
    
    async def wait_for(self, url: str):
        """Подождать перед запросом к URL.

        Под локом только расчёт задержки и обновление состояния; само ожидание
        идёт снаружи. Лок здесь один на все домены, поэтому сон под ним
        превращал бэкофф одного домена в остановку всех парсеров сразу:
        четыре источника в общем `asyncio.gather` выстраивались в очередь и
        выбирали свой таймаут, ни разу не сходив в сеть.
        """
        domain = self._get_domain(url)

        async with self._lock:
            # Очистка при достижении лимита
            if len(self.domains) >= self.MAX_DOMAINS and domain not in self.domains:
                # Удаляем неактивные домены (без недавних запросов)
                self._cleanup_inactive_domains()

            if domain not in self.domains:
                self.domains[domain] = DomainState()

            state = self.domains[domain]
            wait_time = 0.0

            if state.is_blocked() and state.blocked_until is not None:
                wait_time = max((state.blocked_until - datetime.now()).total_seconds(), 0.0)
                logger.warning(f"Домен {domain} заблокирован, ждём {wait_time:.0f} сек")
                state.blocked_until = None
                state.errors_count = 0
            else:
                time_since_last = (datetime.now() - state.last_request).total_seconds()
                required_delay = state.get_delay()
                if time_since_last < required_delay:
                    wait_time = required_delay - time_since_last
                    logger.debug(f"Rate limit для {domain}: ждём {wait_time:.1f} сек")

            # Отметка времени ставится до сна, иначе параллельные вызовы к тому же
            # домену проснутся одновременно и задержка окажется бесполезной.
            state.last_request = datetime.now() + timedelta(seconds=wait_time)
            state.request_count += 1

        if wait_time > 0:
            await asyncio.sleep(wait_time)

    def is_unavailable(self, url: str) -> bool:
        """Помечен ли домен как недоступный навсегда в пределах процесса."""
        return self._get_domain(url) in self._unavailable

    async def report_success(self, url: str):
        """Сообщить об успешном запросе."""
        domain = self._get_domain(url)
        async with self._lock:
            if domain in self.domains:
                # Постепенно снижаем счётчик ошибок
                self.domains[domain].errors_count = max(0, self.domains[domain].errors_count - 1)

    async def report_error(self, url: str, status_code: int | None = None):
        """Сообщить об ошибке."""
        domain = self._get_domain(url)
        async with self._lock:
            if domain not in self.domains:
                self.domains[domain] = DomainState()

            state = self.domains[domain]
            state.errors_count += 1

            # 451 и 401 — отказ по существу, а не перегрузка: ждать и повторять
            # бессмысленно. Прод-IP получает 451 от r.jina.ai, и без этой ветки
            # каждый следующий вызов лишь наращивал задержку до потолка в 60 сек.
            if status_code in self.TERMINAL_STATUSES:
                self._unavailable.add(domain)
                logger.warning(
                    f"Домен {domain} помечен недоступным (код {status_code}): "
                    "дальнейшие обращения в этом процессе пропускаются"
                )
                return

            # Блокировка при определённых кодах
            if status_code in [429, 403, 503]:
                # Экспоненциальная блокировка
                block_minutes = min(2 ** state.errors_count, 60)  # До 60 минут
                state.blocked_until = datetime.now() + timedelta(minutes=block_minutes)
                logger.warning(f"Домен {domain} заблокирован на {block_minutes} мин (код {status_code})")

    def get_stats(self) -> dict[str, Any]:
        """Статистика по доменам."""
        return {
            domain: {
                "requests": state.request_count,
                "errors": state.errors_count,
                "blocked": state.is_blocked(),
                "next_delay": state.get_delay(),
            }
            for domain, state in self.domains.items()
        }


# === Кэширование ===

class ResponseCache:
    """Кэш ответов для избежания повторных запросов."""

    MAX_MEMORY_ENTRIES = 500  # Лимит записей в памяти

    def __init__(self, cache_dir: str = ".cache/parser", ttl_hours: int = 6):
        self.ttl = timedelta(hours=ttl_hours)
        self.memory_cache: dict[str, Any] = {}
        # Кэш на диске — ускорение, а не требование. Экземпляр создаётся на
        # импорте модуля, поэтому упавший mkdir роняет импорт приложения целиком:
        # так контейнер уходил в crash-loop с `Errno 28` при заполненном диске.
        self.cache_dir: Path | None = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(
                f"Дисковый кэш парсеров недоступен ({e}); работаем только в памяти"
            )
            self.cache_dir = None
    
    def _get_key(self, url: str) -> str:
        """Генерировать ключ кэша."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_path(self, key: str) -> Path | None:
        """Путь к файлу кэша; None, если дисковый кэш недоступен."""
        return self.cache_dir / f"{key}.json" if self.cache_dir else None
    
    def get(self, url: str) -> str | None:
        """Получить из кэша."""
        key = self._get_key(url)
        
        # Проверяем память
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if datetime.fromisoformat(entry["expires"]) > datetime.now():
                logger.debug(f"Cache HIT (memory): {url[:50]}...")
                return entry["data"]
        
        # Проверяем файл
        path = self._get_path(key)
        if path and path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    entry = json.load(f)
                if datetime.fromisoformat(entry["expires"]) > datetime.now():
                    logger.debug(f"Cache HIT (disk): {url[:50]}...")
                    self.memory_cache[key] = entry
                    return entry["data"]
                else:
                    path.unlink()  # Удаляем устаревший
            except Exception:
                pass
        
        return None
    
    def set(self, url: str, data: str):
        """Сохранить в кэш."""
        key = self._get_key(url)
        entry = {
            "url": url,
            "data": data,
            "created": datetime.now().isoformat(),
            "expires": (datetime.now() + self.ttl).isoformat(),
        }

        # В память (с лимитом)
        if len(self.memory_cache) >= self.MAX_MEMORY_ENTRIES:
            # Удаляем 20% самых старых
            self._evict_oldest(int(self.MAX_MEMORY_ENTRIES * 0.2))
        self.memory_cache[key] = entry

        # На диск
        path = self._get_path(key)
        if path is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Ошибка записи кэша: {e}")

    def _evict_oldest(self, count: int):
        """Удалить старые записи из памяти."""
        if not self.memory_cache:
            return
        sorted_keys = sorted(
            self.memory_cache.keys(),
            key=lambda k: self.memory_cache[k].get("created", "")
        )
        for key in sorted_keys[:count]:
            del self.memory_cache[key]
    
    def clear_expired(self):
        """Очистить устаревшие записи."""
        now = datetime.now()
        
        # Память
        expired = [
            k for k, v in self.memory_cache.items()
            if datetime.fromisoformat(v["expires"]) < now
        ]
        for k in expired:
            del self.memory_cache[k]
        
        # Диск
        for path in (self.cache_dir.glob("*.json") if self.cache_dir else ()):
            try:
                with open(path) as f:
                    entry = json.load(f)
                if datetime.fromisoformat(entry["expires"]) < now:
                    path.unlink()
            except Exception:
                pass
    
    def stats(self) -> dict[str, int]:
        """Статистика кэша."""
        return {
            "memory_entries": len(self.memory_cache),
            "disk_entries": len(list(self.cache_dir.glob("*.json"))) if self.cache_dir else 0,
        }


# === Crawl4AI Stealth Config ===

def get_stealth_config() -> dict[str, Any]:
    """Конфигурация для Crawl4AI с максимальной защитой."""
    return {
        "headless": True,
        "browser_type": "chromium",
        "verbose": False,
        
        # Stealth режим
        "stealth": True,
        "user_agent": get_random_user_agent(),
        
        # Имитация реального браузера
        "viewport": {
            "width": random.choice([1366, 1440, 1536, 1920]),
            "height": random.choice([768, 900, 864, 1080]),
        },
        
        # Таймауты
        "page_timeout": 30000,
        "wait_until": "domcontentloaded",  # Быстрее чем networkidle
        
        # Блокируем лишнее (ускоряет + уменьшает fingerprint)
        "excluded_tags": ["script", "style", "noscript", "iframe"],
        
        # Без медиа
        "screenshot": False,
        "pdf": False,
    }


# === Глобальные экземпляры ===

rate_limiter = AdaptiveRateLimiter()
response_cache = ResponseCache()


# === Декораторы ===

def with_rate_limit(func):
    """Декоратор для автоматического rate limiting."""
    @wraps(func)
    async def wrapper(url: str, *args, **kwargs):
        await rate_limiter.wait_for(url)
        try:
            result = await func(url, *args, **kwargs)
            await rate_limiter.report_success(url)
            return result
        except Exception as e:
            status = getattr(e, 'status', None) or getattr(e, 'status_code', None)
            await rate_limiter.report_error(url, status)
            raise
    return wrapper


def with_cache(ttl_hours: int = 6):
    """Декоратор для кэширования."""
    cache = ResponseCache(ttl_hours=ttl_hours)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(url: str, *args, **kwargs):
            # Проверяем кэш
            cached = cache.get(url)
            if cached:
                return cached
            
            # Выполняем запрос
            result = await func(url, *args, **kwargs)
            
            # Сохраняем в кэш
            if result:
                cache.set(url, result)
            
            return result
        return wrapper
    return decorator


# === Тест ===

if __name__ == "__main__":
    async def test():
        print("=== Тест Anti-Detection модуля ===\n")
        
        # User-Agent
        print("1. User-Agent ротация:")
        for _ in range(3):
            print(f"   {get_random_user_agent()[:60]}...")
        
        # Headers
        print("\n2. Реалистичные заголовки:")
        headers = get_realistic_headers()
        for k, v in list(headers.items())[:5]:
            print(f"   {k}: {v[:40]}...")
        
        # Rate Limiter
        print("\n3. Rate Limiter:")
        limiter = AdaptiveRateLimiter()
        
        for i in range(3):
            print(f"   Запрос {i+1} к kassir.ru...")
            await limiter.wait_for("https://irk.kassir.ru/")
            print("   ✓ Выполнен")
        
        print(f"\n   Статистика: {limiter.get_stats()}")
        
        # Cache
        print("\n4. Кэш:")
        cache = ResponseCache(ttl_hours=1)
        cache.set("https://example.com", "test data")
        result = cache.get("https://example.com")
        print(f"   Сохранено и получено: {result}")
        print(f"   Статистика: {cache.stats()}")
        
        # Stealth config
        print("\n5. Stealth конфиг для Crawl4AI:")
        config = get_stealth_config()
        print(f"   viewport: {config['viewport']}")
        print(f"   user_agent: {config['user_agent'][:50]}...")
        
        print("\n=== Тест завершён ===")
    
    asyncio.run(test())
