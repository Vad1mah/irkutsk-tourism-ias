# ДОКУМЕНТАЦИЯ ПРАКТИЧЕСКОЙ ЧАСТИ ВКР

## Тема: Разработка интеллектуальной системы анализа туристического потока Иркутской области

---

## СОДЕРЖАНИЕ

1. [Введение и постановка задачи](#1-введение-и-постановка-задачи)
2. [Архитектура системы](#2-архитектура-системы)
3. [Этап 1: Проектирование базы данных](#этап-1-проектирование-базы-данных)
4. [Этап 2: Разработка Backend API](#этап-2-разработка-backend-api)
5. [Этап 3: Реализация парсеров данных](#этап-3-реализация-парсеров-данных)
6. [Этап 4: Внедрение RAG-системы и AI-агента](#этап-4-внедрение-rag-системы)
7. [Этап 5: Разработка Frontend](#этап-5-разработка-frontend)
8. [Этап 6: Интеграция и тестирование](#этап-6-интеграция-и-тестирование)
9. [Этап 7: Продвинутая аналитика](#этап-7-продвинутая-аналитика)
10. [Этап 8: Ансамблевое прогнозирование и безопасность](#этап-8-ансамблевое-прогнозирование)
11. [Используемые технологии](#используемые-технологии)
12. [Результаты и выводы](#результаты-и-выводы)

---

## 1. ВВЕДЕНИЕ И ПОСТАНОВКА ЗАДАЧИ

### 1.1 Актуальность

Туристическая отрасль Иркутской области демонстрирует устойчивый рост, однако отсутствие единой системы анализа данных затрудняет:
- Прогнозирование загруженности гостиничной инфраструктуры
- Оперативный мониторинг культурных и спортивных мероприятий
- Принятие управленческих решений на основе данных

### 1.2 Цель работы

Разработка интеллектуальной веб-системы для:
1. Сбора и агрегации данных о туристической инфраструктуре
2. Анализа загруженности отелей с прогнозированием
3. Мониторинга событий и мероприятий региона
4. Предоставления AI-ассистента для ответов на вопросы

### 1.3 Задачи

| № | Задача | Результат |
|---|--------|-----------|
| 1 | Спроектировать архитектуру системы | Клиент-серверная архитектура с модульным бэкендом, Docker Compose |
| 2 | Разработать базу данных | PostgreSQL 16 (SQLAlchemy 2.0 + asyncpg) |
| 3 | Реализовать REST API | FastAPI backend (7 роутеров, 59 endpoints) |
| 4 | Создать парсеры данных | 17 модулей парсеров (8 источников событий, 2 отеля, погода + утилиты) |
| 5 | Внедрить AI-агента | LangGraph + Mistral + ChromaDB (RAG + tools) |
| 6 | Реализовать прогнозирование | Ensemble (Prophet + NeuralProphet + XGBoost + LightGBM) |
| 7 | Разработать веб-интерфейс | React + TypeScript + Recharts + ECharts (8 страниц: Home, Chat, Analytics, Events, Map, Forecast, HotelDetail, About) |
| 8 | Обеспечить безопасность | Rate Limiting + API key auth + CORS |
| 9 | Провести тестирование | Unit (94) + E2E (9) тесты |

---

## 2. АРХИТЕКТУРА СИСТЕМЫ

### 2.1 Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│   React 18 + TypeScript + Tailwind CSS 4 + Recharts + ECharts   │
│                         (port 5173)                              │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND API                              │
│               FastAPI + Uvicorn + APScheduler                   │
│                         (port 8000)                              │
├─────────────────────────────────────────────────────────────────┤
│  Роутеры:                                                        │
│  • /api/hotels     - данные отелей                              │
│  • /api/events     - события и мероприятия                      │
│  • /api/query      - AI-агент (LangGraph + tools)               │
│  • /api/forecast   - прогнозирование (Ensemble)                 │
│  • /api/analytics  - аналитика и KPI                            │
│  • /api/documents  - индексация документов                      │
│  • /api/parser     - парсинг внешних источников                 │
├─────────────────────────────────────────────────────────────────┤
│  Middleware: Rate Limiting (Redis) + API Key Auth               │
└─────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│ PostgreSQL │  │  ChromaDB  │  │ Mistral AI │  │   Redis    │
│     16     │  │ (Vector DB)│  │  (LLM API) │  │  (Cache)   │
│            │  │            │  │            │  │            │
│ • hotels   │  │ • embed-   │  │ • mistral- │  │ • API cache│
│ • events   │  │   dings    │  │   large    │  │ • rate     │
│ • stats    │  │ • documents│  │ • tools    │  │   limiting │
│ • forecasts│  │            │  │            │  │            │
└────────────┘  └────────────┘  └────────────┘  └────────────┘
                       │
                       ▼
                ┌────────────┐
                │  GigaChat  │
                │ Embeddings │
                │   (Sber)   │
                └────────────┘
```

### 2.2 Принципы проектирования

1. **Модульная архитектура** — разделение на независимые модули
2. **RESTful API** — стандартизированный интерфейс взаимодействия
3. **Конфигурация через переменные окружения** — гибкость развёртывания
4. **Graceful degradation** — устойчивость к отказам внешних сервисов
5. **Batch processing** — оптимизация работы с большими объёмами данных

---

## ЭТАП 1: ПРОЕКТИРОВАНИЕ БАЗЫ ДАННЫХ

### 1.1 Выбор СУБД

Основное хранилище — **PostgreSQL 16** (Docker, SQLAlchemy 2.0 + asyncpg). Ранее на этапе MVP использовалась Yandex YDB Serverless; миграция выполнена для локальной разработки, полноценного ORM и независимости от провайдера.

| Критерий | PostgreSQL 16 (текущее) |
|----------|-------------------------|
| Развёртывание | Docker Compose |
| ORM | SQLAlchemy 2.0 |
| Миграции | Alembic |
| Async драйвер | asyncpg |
| Независимость | Полная |

### 1.2 Схема данных (SQLAlchemy ORM)

Файл: `backend/app/db/models.py`

```python
class Hotel(Base):
    __tablename__ = "hotels"
    id = Column(String, primary_key=True)
    name = Column(String)
    city = Column(String, index=True)
    district = Column(String, index=True)
    lat = Column(Float)
    lon = Column(Float)
    rating = Column(Float)
    min_price = Column(Float)
    accommodation_type = Column(String)
    tripadvisor_rating = Column(Float)
    statistics = relationship("HotelStatistic", back_populates="hotel")

class HotelStatistic(Base):
    __tablename__ = "hotel_statistics"
    id = Column(String, ForeignKey("hotels.id"), primary_key=True)
    date = Column(Date, primary_key=True)
    rooms_num = Column(Integer)
    free_rooms_amount = Column(Integer)
    available_rooms_percent = Column(Float)
    min_price = Column(Float)

class Event(Base):
    __tablename__ = "events"
    event_id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(Text)
    date_start = Column(Date, index=True)
    date_end = Column(Date)
    event_type = Column(String)
    location = Column(String)
    source_id = Column(String)
    url = Column(String)
    created_at = Column(DateTime, server_default=func.now())
```

### 1.3 Data Service Factory

Файл: `backend/app/services/data_service.py`

Доступ к данным централизован через фабрику `data_service` и реализацию `db_service` (PostgreSQL):

```python
# Упрощённо: единая точка — data_service / DBService (PostgreSQL)
from app.services.data_service import data_service
from app.services.db_service import db_service
```

Файл: `backend/app/services/db_service.py`

```python
class DBService:
    """Сервис для работы с PostgreSQL через SQLAlchemy."""

    async def connect(self):
        self._engine = create_async_engine(settings.database_url)
        self._session_factory = async_sessionmaker(self._engine)

    async def get_hotels(self, city: str = None) -> list[dict]:
        async with self._session_factory() as session:
            query = select(Hotel)
            if city:
                query = query.where(Hotel.city.ilike(f"%{city}%"))
            result = await session.execute(query)
            return [row._asdict() for row in result.scalars()]
```

### 1.4 Инфраструктура (Docker Compose)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: tourism
      POSTGRES_USER: tourism
      POSTGRES_PASSWORD: tourism_pass
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tourism"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --appendonly yes
```

**Данные в БД:** 1 366 отелей, 37 663 записи статистики, 318 событий из 8 источников

---

## ЭТАП 2: РАЗРАБОТКА BACKEND API

### 2.1 Структура проекта

```
backend/
├── app/
│   ├── main.py                 # Точка входа FastAPI + lifespan
│   ├── config.py               # Конфигурация (pydantic-settings)
│   ├── constants.py            # Константы (районы, slug-и, лимиты)
│   ├── scheduler.py            # APScheduler (автосбор данных)
│   ├── db/
│   │   ├── models.py           # SQLAlchemy ORM модели
│   │   └── session.py          # Async session factory
│   ├── models/
│   │   └── schemas.py          # Pydantic схемы (~20 моделей)
│   ├── routers/
│   │   ├── hotels.py           # API отелей
│   │   ├── events.py           # API событий
│   │   ├── query.py            # API AI-агента (LangGraph)
│   │   ├── forecast.py         # API прогнозирования (Ensemble)
│   │   ├── analytics.py        # API аналитики и KPI
│   │   ├── documents.py        # API индексации ChromaDB
│   │   └── parser.py           # API парсинга (API key)
│   ├── services/
│   │   ├── data_service.py     # Фабрика / единая точка доступа к данным
│   │   ├── db_service.py       # PostgreSQL (SQLAlchemy 2.0 + asyncpg)
│   │   ├── chroma_service.py   # ChromaDB (RAG)
│   │   ├── llm_service.py      # Мультипровайдер LLM
│   │   ├── cache_service.py    # Redis кэширование
│   │   ├── main_agent.py       # LangGraph AI-агент + определение tools
│   │   ├── forecast_agent.py   # Агент прогнозирования
│   │   ├── prophet_service.py  # Prophet модель
│   │   ├── neuralprophet_service.py  # NeuralProphet
│   │   ├── xgboost_service.py  # XGBoost
│   │   ├── ensemble_service.py # Ансамбль моделей
│   │   ├── feature_engineering.py # Инженерия признаков
│   │   ├── weather_service.py  # Погода (Open-Meteo)
│   │   └── holidays_service.py # Праздники РФ
│   ├── middleware/
│   │   └── rate_limit.py       # Rate Limiting (Redis)
│   ├── dependencies/
│   │   ├── __init__.py         # DI (10 сервисных зависимостей)
│   │   └── auth.py             # API key verification
│   ├── parsers/                # 17 модулей парсеров
│   └── llm/
│       └── groq_provider.py    # Groq HTTP client
├── tests/                      # pytest + pytest-asyncio
├── requirements.txt
└── .env
```

### 2.2 Конфигурация приложения

Файл: `backend/app/config.py`

```python
class Settings(BaseSettings):
    """Настройки приложения."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_backend: str = "postgresql"
    database_url: str = "postgresql+asyncpg://tourism:tourism_pass@localhost:5432/tourism"

    llm_provider: str = "mistral"
    mistral_api_key: SecretStr | None = None
    mistral_model: str = "mistral-large-latest"

    gigachat_credentials: SecretStr | None = None
    chroma_persist_dir: str = "./chroma_db"

    redis_host: str = "localhost"
    redis_port: int = 6379

    api_key: SecretStr | None = None
    rate_limit_requests: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]
```

Все чувствительные данные хранятся через `SecretStr`, конфигурация загружается из `.env` файла.

### 2.3 Жизненный цикл приложения

Файл: `backend/app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup: PostgreSQL, Redis, ChromaDB, LLM, APScheduler
    await db_service.connect()
    await db_service.create_tables()

    await cache_service.connect()
    chroma_service.init()
    llm_service.init()

    sched = get_scheduler()
    await sched.start(run_initial=False)

    yield

    # Shutdown
    sched.stop()
    await cache_service.close()
    await db_service.close()
```

### 2.4 API Endpoints

| Метод | Endpoint | Описание | Auth |
|-------|----------|----------|------|
| GET | `/api/hotels` | Список отелей (кэш) | — |
| GET | `/api/hotels/{id}/statistics` | Статистика отеля | — |
| GET | `/api/events` | Список событий | — |
| POST | `/api/query` | AI-агент (LangGraph + tools) | — |
| GET | `/api/forecast/ensemble` | Ансамблевый прогноз | — |
| GET | `/api/forecast/compare-all` | Сравнение моделей | — |
| POST | `/api/forecast` | Prophet (в составе Ensemble) | — |
| POST | `/api/forecast/xgboost` | XGBoost прогноз | — |
| GET | `/api/analytics/kpi` | KPI дашборд | — |
| GET | `/api/analytics/correlation` | Корреляция событий/загрузки | — |
| GET | `/api/analytics/heatmap` | Тепловая карта загрузки | — |
| POST | `/api/parser/events/{source}` | Парсинг событий | API Key |
| POST | `/api/parser/hotels` | Парсинг отелей | API Key |
| POST | `/api/documents/reindex` | Индексация в ChromaDB из PostgreSQL | API Key |

---

## ЭТАП 3: РЕАЛИЗАЦИЯ ПАРСЕРОВ ДАННЫХ

### 3.1 Архитектура парсинга

```
Внешние источники          Парсеры              База данных
┌──────────────┐      ┌────────────────┐      ┌───────────┐
│  irk.ru      │ ───▶ │ events_irk.py  │ ───▶ │           │
│  /afisha/    │      │                │      │PostgreSQL │
└──────────────┘      └────────────────┘      │  events   │
                                              │  table    │
┌──────────────┐      ┌────────────────┐      │           │
│ culture38.ru │ ───▶ │events_culture38│ ───▶ │           │
│              │      │     .py        │      │           │
└──────────────┘      └────────────────┘      └───────────┘
```

### 3.2 Парсер irk.ru

Файл: `backend/app/parsers/events_irk.py`

```python
async def fetch_events_irk(days_ahead: int = 30) -> List[Dict[str, Any]]:
    """Получить события с irk.ru/afisha/."""
    url = settings.parser_irk_url
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TourismBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=settings.parser_timeout),
            ssl=False,
        ) as response:
            if response.status == 200:
                html = await response.text()
                return _parse_irk_html(html)
    return []


def _parse_irk_html(html: str) -> List[Dict[str, Any]]:
    """Парсинг HTML страницы irk.ru."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # CSS-селекторы определены эмпирически
    cards = soup.find_all("article", class_="afisha-article__article")
    
    for card in cards:
        # Жанр события
        genre_elem = card.find("span", class_="afisha-article__genre")
        genre = genre_elem.get_text(strip=True) if genre_elem else ""
        
        # Название
        title_elem = card.find("h4", class_="afisha-article__title")
        title = title_elem.get_text(strip=True) if title_elem else ""
        
        # Дата
        date_elem = card.find("span", class_="afisha-article__date")
        date_str = ""
        if date_elem:
            time_elem = date_elem.find("time")
            date_str = time_elem.get_text(strip=True) if time_elem else ""
        
        # URL
        link_elem = card.find("a", class_="afisha-article__link")
        url = ""
        if link_elem and link_elem.get("href"):
            href = link_elem.get("href")
            base_url = settings.parser_irk_url.rstrip("/").rsplit("/", 1)[0]
            url = f"{base_url}{href}" if href.startswith("/") else href
        
        events.append({
            "title": title,
            "date": date_str,
            "date_parsed": _parse_irk_date(date_str),
            "event_type": genre,
            "location": "",
            "url": url,
            "source": "irk.ru",
        })
    
    return events
```

**Особенности реализации:**
- Асинхронные HTTP-запросы через `aiohttp`
- Настраиваемый User-Agent для имитации браузера
- Timeout из конфигурации
- Генерация уникального ID через MD5 хеш

### 3.3 Генерация уникальных ID

```python
def generate_event_id(title: str, date_str: str, source: str = "irk") -> str:
    """Генерация уникального ID события."""
    raw = f"{source}:{title}:{date_str}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]
```

---

## ЭТАП 4: ВНЕДРЕНИЕ RAG-СИСТЕМЫ

### 4.1 Архитектура RAG

```
          Пользователь
               │
               ▼
        ┌─────────────┐
        │   Запрос    │
        │  "Какие     │
        │  отели...?" │
        └─────────────┘
               │
               ▼
    ┌───────────────────┐
    │   ChromaDB        │
    │   (поиск по       │
    │   эмбеддингам)    │
    └───────────────────┘
               │
               ▼
    ┌───────────────────┐
    │   GigaChat        │
    │   Embeddings      │
    │   (Sber API)      │
    └───────────────────┘
               │
               ▼
    ┌───────────────────┐
    │   Top-K           │
    │   релевантных     │
    │   документов      │
    └───────────────────┘
               │
               ▼
    ┌───────────────────┐
    │   LLM (Mistral)   │
    │   LangGraph Agent │
    │                   │
    │   Контекст +      │
    │   Tools +         │
    │   Системный промпт│
    └───────────────────┘
               │
               ▼
        ┌─────────────┐
        │   Ответ с   │
        │  источниками│
        └─────────────┘
```

### 4.2 Сервис ChromaDB

Файл: `backend/app/services/chroma_service.py`

```python
class ChromaService:
    """Сервис для работы с векторной БД Chroma v1.0+."""
    
    def init(self):
        """Инициализация Chroma и GigaChat embeddings."""
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embeddings = GigaChatEmbeddings(
            credentials=settings.gigachat_credentials,
            verify_ssl_certs=settings.gigachat_verify_ssl,
            scope=settings.gigachat_scope,
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    
    def add_documents_batch(
        self, 
        texts: list[str], 
        metadatas: list[dict], 
        ids: list[str],
        batch_size: int | None = None,
    ) -> int:
        """Пакетная индексация документов."""
        batch_size = batch_size or settings.rag_index_batch_size
        indexed = 0
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            
            embeddings = self._embeddings.embed_documents(batch_texts)
            self._collection.upsert(
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=batch_metas,
                ids=batch_ids,
            )
            indexed += len(batch_texts)
        
        return indexed
    
    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Поиск релевантных документов."""
        query_embedding = self._embeddings.embed_query(query)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        # ... форматирование результатов
```

### 4.3 AI-агент на LangGraph

Файл: `backend/app/services/main_agent.py`

Вместо простого RAG-подхода реализован полноценный AI-агент на LangGraph с инструментами:

```python
from langgraph.graph import StateGraph, START, END
from langchain_mistralai import ChatMistral

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

tools = [search_hotels, search_events, get_weather,
         forecast_occupancy, get_statistics]

def assistant(state: AgentState) -> Command[Literal["tools", "respond"]]:
    """Узел агента: вызов LLM с tools."""
    llm = ChatMistral(model=settings.mistral_model, temperature=0.3)
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(state["messages"])

    if response.tool_calls:
        return Command(goto="tools", update={"messages": [response]})
    return Command(goto="respond", update={"messages": [response]})

graph = StateGraph(AgentState)
graph.add_node("assistant", assistant)
graph.add_node("tools", ToolNode(tools))
graph.add_node("respond", respond)
graph.add_edge(START, "assistant")
agent = graph.compile()
```

**Режимы работы:**
- **tools** — агент использует инструменты для получения данных из БД
- **rag** — fallback на поиск по ChromaDB (если tools недоступны)

**Инструменты агента:** `search_hotels`, `search_events`, `get_weather`, `forecast_occupancy`, `get_statistics`

**Результат:** tool usage rate ~90% (агент выбирает правильный инструмент в 9 из 10 запросов)

### 4.4 Системный промпт AI-агента

```python
SYSTEM_PROMPT = """### Роль
Ты — аналитик туризма Иркутской области. Отвечаешь на вопросы 
о загруженности отелей, событиях и туристических трендах.

### Задача
Анализировать данные и давать полезные ответы туристам 
и владельцам отелей.

#### Инструкция
1. Используй предоставленный контекст из базы данных
2. Отвечай конкретно и по делу
3. Если данных недостаточно — честно скажи об этом
4. Давай практические рекомендации

#### Формат ответа
Краткий структурированный ответ на русском языке.

#### Примечание
Не выдумывай данные. Опирайся только на предоставленную информацию."""
```

### 4.5 Индексация данных

Файл: `backend/app/routers/documents.py`

```python
@router.post("/reindex")
async def index_data(clear: bool = False) -> Dict[str, Any]:
    """Индексация данных из PostgreSQL (через data_service/db_service) в ChromaDB."""
    
    if clear:
        chroma_service.clear_collection()
    
    texts, metadatas, ids = [], [], []
    
    # Индексация отелей
    hotels = await data_service.get_hotels(limit=1000)
    for hotel in hotels:
        text = _format_hotel_text(hotel)
        texts.append(text)
        metadatas.append({"type": "hotel", "source": "postgresql_hotels"})
        ids.append(f"hotel_{hotel.id}")
    
    # Индексация событий
    events = await data_service.get_events()
    for event in events:
        text = _format_event_text(event)
        texts.append(text)
        metadatas.append({"type": "event", "source": "postgresql_events"})
        ids.append(f"event_{event['event_id']}")
    
    # Пакетная индексация
    indexed_count = chroma_service.add_documents_batch(
        texts=texts,
        metadatas=metadatas,
        ids=ids,
        batch_size=settings.rag_index_batch_size,
    )
    
    return {
        "status": "ok",
        "indexed_count": indexed_count,
        "collection_count": chroma_service.get_collection_count(),
    }
```

---

## ЭТАП 5: РАЗРАБОТКА FRONTEND

### 5.1 Технологический стек

| Технология | Версия | Назначение |
|------------|--------|------------|
| React | 18.3 | UI-библиотека |
| TypeScript | 5.9 | Типизация |
| Vite | 7.2 | Сборщик |
| Tailwind CSS | 4.0 | Стилизация |
| React Query | 5.62 | Управление состоянием запросов |
| React Router | 7.1 | Маршрутизация |
| Recharts | 2.15 | Графики (Area, Bar, Line, Radar, Treemap) |
| ECharts | tree-shaken | GeoMap на Map |
| Lucide React | 0.468 | Иконки |

### 5.2 Структура проекта

```
frontend/
├── src/
│   ├── main.tsx              # Точка входа + ErrorBoundary + React Query
│   ├── App.tsx               # Lazy loading страниц + роутинг
│   ├── index.css             # Tailwind CSS 4, CSS-переменные, анимации
│   ├── api/
│   │   └── client.ts         # Типизированный API (17 методов)
│   ├── components/
│   │   ├── Layout.tsx        # Sidebar + мобильное меню
│   │   ├── ErrorBoundary.tsx # Обработка ошибок
│   │   ├── HeatmapGrid.tsx   # Тепловая карта
│   │   └── ui/               # Button, Card, Input, Badge
│   ├── pages/
│   │   ├── Home.tsx          # AI-чат с агентом
│   │   ├── Chat.tsx          # SSE streaming чат
│   │   ├── Analytics.tsx     # Аналитика (KPI, прогноз, рекомендации)
│   │   ├── Events.tsx        # Каталог событий (поиск + фильтры)
│   │   ├── Map.tsx           # Аналитика регионов (treemap, radar)
│   │   ├── Forecast.tsx      # Прогнозирование (Ensemble + сравнение)
│   │   ├── HotelDetail.tsx   # Карточка отеля (/hotels/:id)
│   │   └── About.tsx         # О системе для комиссии
│   ├── lib/cn.ts             # clsx + tailwind-merge
│   └── utils/weather.ts      # Weather emoji helper
├── package.json
├── vite.config.ts            # Proxy + code splitting
├── Dockerfile                # Multi-stage Node → Nginx
└── nginx.conf                # SPA routing
```

### 5.3 Конфигурация Vite (Proxy)

Файл: `frontend/vite.config.ts`

```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    allowedHosts: true,  // Для внешних туннелей
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

### 5.4 Компонент AI-ассистента

Файл: `frontend/src/pages/Home.tsx`

```typescript
export function Home() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  
  const mutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      return res.json();
    },
    onSuccess: (data) => setResponse(data),
  });
  
  return (
    <div className="space-y-6">
      <Card>
        <h2>AI-ассистент</h2>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Задайте вопрос о туризме..."
        />
        <Button 
          onClick={() => mutation.mutate(query)}
          loading={mutation.isPending}
        >
          Отправить
        </Button>
      </Card>
      
      {response && (
        <Card>
          <p>{response.answer}</p>
          <div className="flex gap-2">
            {response.sources.map((s) => (
              <Badge key={s}>{s}</Badge>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
```

---

## ЭТАП 6: ИНТЕГРАЦИЯ И ТЕСТИРОВАНИЕ

### 6.1 Проверка работоспособности

#### Health Check API

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/api/query/health
# {"status":"ok","chroma_initialized":true,"documents_count":535+}
```

#### Тест RAG-системы

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"text": "Какие отели есть в Иркутске?"}'
```

### 6.2 Результаты тестирования

| Тест | Статус | Примечание |
|------|--------|------------|
| Подключение к PostgreSQL | ✅ | 1 366 отелей в БД |
| Индексация ChromaDB | ✅ | 535 документов |
| Парсер irk.ru | ✅ | События загружаются |
| AI-агент | ✅ | Retry logic работает |
| Frontend | ✅ | 8 страниц отображаются |

### 6.3 Обработка ошибок

```python
# Retry logic для LLM
@retry(
    retry=retry_if_exception_type((RateLimitError, APIError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
)
async def _call_llm(self, messages):
    ...

# Fallback при ошибке
try:
    answer = await self._call_llm(messages)
except Exception as e:
    answer = f"Сервис временно недоступен. ({type(e).__name__})"
```

---

## ЭТАП 7: ПРОДВИНУТАЯ АНАЛИТИКА

### 7.1 Корреляционный анализ

Реализован модуль анализа корреляции между событиями и загруженностью отелей.

#### API Endpoints

```
GET /api/analytics/correlation   → Данные корреляции по месяцам
GET /api/analytics/districts     → Статистика по районам
GET /api/analytics/kpi           → Ключевые метрики
GET /api/analytics/recommendations → Рекомендации
GET /api/analytics/events-impact → Влияние событий
```

#### Результаты корреляционного анализа

| Показатель | Значение |
|------------|----------|
| Коэффициент корреляции (Пирсона) | **r = 0.96** |
| Влияние одного события | **+1.2%** к загруженности |
| Пиковый месяц | Июль (78% загрузки) |
| Минимальная загрузка | Октябрь (35%) |

#### Влияние крупных событий на загруженность

| Событие | Район | Влияние на загрузку | Влияние на цену |
|---------|-------|---------------------|-----------------|
| Майские праздники | Ольхонский | **+35%** | +25% |
| Летний туристический сезон | Все районы | **+40%** | +30% |
| Байкальский ледовый марафон | Слюдянский | **+23%** | +15% |
| Фестиваль ледяных скульптур | Иркутский | **+18%** | +10% |
| Новогодние праздники | Иркутский | **+25%** | +20% |

### 7.2 Рекомендательная система

Реализована система рекомендаций для двух целевых аудиторий:

#### Для туристов

```
Рекомендация: "Лучшее время для поездки на Ольхон"
Период: Октябрь
Обоснование: Минимальная загруженность (35%), низкие цены
Экономия: 35%
```

#### Для отельеров

```
Рекомендация: "Повышение цен в пик сезона"
Период: Июнь-Июль
Обоснование: Загруженность 68-78%
Рекомендуемое увеличение: +15-20%
```

### 7.3 Реализация

Файл: `backend/app/routers/analytics.py`

```python
@router.get("/correlation")
async def get_correlation_data() -> Dict[str, Any]:
    """Получить данные корреляции событий и загруженности."""
    months_data = [...]  # Данные по месяцам
    
    # Расчёт коэффициента корреляции Пирсона
    occupancies = [m["occupancy"] for m in months_data]
    events = [m["events"] for m in months_data]
    
    n = len(occupancies)
    mean_occ = sum(occupancies) / n
    mean_evt = sum(events) / n
    
    numerator = sum((o - mean_occ) * (e - mean_evt) 
                    for o, e in zip(occupancies, events))
    denom_occ = sum((o - mean_occ) ** 2 for o in occupancies) ** 0.5
    denom_evt = sum((e - mean_evt) ** 2 for e in events) ** 0.5
    
    correlation = numerator / (denom_occ * denom_evt)
    
    return {
        "months": months_data,
        "correlation_coefficient": round(correlation, 2),
    }
```

### 7.4 Визуализация на Frontend

Страницы: `Analytics.tsx`, `Map.tsx` (Recharts + ECharts)

Компоненты:
1. **KPI карточки** — ключевые метрики
2. **График корреляции** — ComposedChart (Area + Bar + Line)
3. **Сезонность цен** — AreaChart
4. **Загруженность по районам** — BarChart (горизонтальный)
5. **Рекомендации** — карточки с разделением по аудитории

### 7.5 Дополнительные страницы

#### Страница "Отели" (`/hotels`)

Функционал:
- Таблица 1 366 отелей с сортировкой и поиском
- Статистика по городам с загруженностью
- Фильтрация по городу
- Координаты для геопозиционирования
- Карта отелей на Map (ECharts GeoMap) и графики на Recharts

#### Улучшения страницы "События" (`/events`)

Добавлено:
- Блок "Влияние событий на загрузку отелей"
- Карточки с процентом влияния каждого события
- Интеграция с API `/api/analytics/events-impact`

#### Улучшения страницы "Прогноз" (`/forecast`)

Добавлено:
- Блок "События, влияющие на загрузку"
- Фильтрация событий по выбранному району
- Рекомендации по ценообразованию

---

## ЭТАП 8: АНСАМБЛЕВОЕ ПРОГНОЗИРОВАНИЕ

### 8.1 Архитектура Ensemble

Реализовано ансамблевое прогнозирование с параллельным запуском моделей:

```
┌────────────────────────────────────────────────────────┐
│                 Ensemble Service                        │
├────────────────────────────────────────────────────────┤
│                                                         │
│   asyncio.gather(                                       │
│     ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐   │
│     │ Prophet  │ │ NeuralProphet│ │ XGBoost  │ │ LightGBM │   │
│     │ weather  │ │ events +     │ │ 38 feat  │ │ boosting │   │
│     │ regressor│ │ autoregress  │ │ quantile │ │          │   │
│     └────┬─────┘ └──────┬───────┘ └────┬─────┘ └────┬─────┘   │
│          │              │              │              │         │
│          └──────────────┴──────────────┴──────────────┘         │
│                          ▼                              │
│              Weighted Average (adaptive)                │
│              + Confidence Intervals                     │
│                          │                              │
│                          ▼                              │
│                 Ensemble Forecast                       │
│                 (кэш TTL 30 мин)                        │
└────────────────────────────────────────────────────────┘
```

### 8.2 Feature Engineering

Файл: `backend/app/services/feature_engineering.py`

Генерация 38 признаков для XGBoost:

| Категория | Признаки |
|-----------|----------|
| Календарные | day_of_week, month, quarter, is_weekend, is_holiday |
| Лаговые | lag_1, lag_7, lag_14, lag_30, lag_90 |
| Скользящие | rolling_mean_7/14/30, rolling_std_7, rolling_min/max_7 |
| Дифференциальные | diff_1, diff_7 |
| Погодные | temperature, precipitation, wind_speed |
| Событийные | events_count, event_type |
| Расстояние | days_from_holiday |

### 8.3 Метрики моделей

| Район | Prophet RMSE | NeuralProphet RMSE | XGBoost RMSE | Ensemble RMSE |
|-------|-------------|-------------------|-------------|--------------|
| Иркутский | 5.58 | 5.92 | 6.11 | **2.67** |
| Ольхонский | **17.5** | 37.02 | 27.16 | 24.48 |
| Слюдянский | 10.8 | 10.32 | 14.06 | **8.52** |

### 8.4 Безопасность

| Мера | Реализация |
|------|------------|
| Rate Limiting | Redis sliding window (10 req/min для /api/query, 5 req/min для /api/parser) |
| API Key Auth | X-API-Key header для parser/admin endpoints |
| SQL Injection | Экранирование %, _ в LIKE запросах |
| CORS | Ограниченные origins, methods, headers |
| Secrets | Pydantic SecretStr для API ключей |

---

## ИСПОЛЬЗУЕМЫЕ ТЕХНОЛОГИИ

### Backend

| Библиотека | Версия | Назначение |
|------------|--------|------------|
| FastAPI | ≥0.115.0 | Web-фреймворк |
| Uvicorn | ≥0.32.0 | ASGI-сервер |
| Pydantic | ≥2.10.0 | Валидация данных |
| SQLAlchemy | ≥2.0.36 | ORM для PostgreSQL |
| asyncpg | ≥0.30.0 | Async драйвер PostgreSQL |
| redis | ≥5.0.0 | Кэширование и rate limiting |
| chromadb | ≥0.5.23 | Векторная база данных |
| langchain-mistralai | ≥0.2.0 | Mistral LLM с tool calling |
| langgraph | ≥0.2.0 | AI-агенты с графами |
| langchain-gigachat | ≥0.3.2 | GigaChat embeddings |
| prophet | ≥1.3.0 | Временные ряды |
| neuralprophet | ≥0.8.0 | Нейросетевое прогнозирование |
| xgboost | ≥2.0.0 | Gradient boosting |
| lightgbm | ≥4.0.0 | Gradient boosting (ансамбль) |
| scikit-learn | ≥1.4.0 | ML метрики и утилиты |
| aiohttp | ≥3.11.0 | Асинхронные HTTP-запросы |
| beautifulsoup4 | ≥4.12.3 | HTML-парсинг |
| apscheduler | ≥3.10.0 | Планировщик задач |

### Frontend

| Библиотека | Версия | Назначение |
|------------|--------|------------|
| React | 18.3 | UI-библиотека |
| TypeScript | 5.9 | Типизация (strict mode) |
| Vite | 7.2 | Сборщик с code splitting |
| Tailwind CSS | 4.0 | CSS-фреймворк |
| @tanstack/react-query | 5.62 | Data fetching и кэширование |
| react-router-dom | 7.1 | Маршрутизация с lazy loading |
| recharts | 2.15 | Графики и визуализация |
| echarts | tree-shaken | GeoMap (Map) |
| lucide-react | 0.468 | Иконки |
| react-hot-toast | 2.6 | Уведомления |

### Внешние сервисы

| Сервис | Назначение |
|--------|------------|
| PostgreSQL 16 | Основная база данных (Docker) |
| Redis 7 | Кэширование и rate limiting (Docker) |
| Mistral AI | LLM API (mistral-large-latest) |
| GigaChat API (Sber) | Embeddings для RAG |
| Open-Meteo API | Данные погоды |

---

## РЕЗУЛЬТАТЫ И ВЫВОДЫ

### Достигнутые результаты

1. **Разработана модульная клиент-серверная архитектура** с чётким разделением ответственности (7 роутеров, 16 сервисов)
2. **Реализован REST API** с 59 эндпоинтами, кэшированием (Redis) и rate limiting
3. **Внедрён AI-агент** на LangGraph с 5 инструментами и RAG-fallback (Mistral + ChromaDB)
4. **Создано 17 модулей парсеров** (8 источников событий, 2 отеля, погода + утилиты) с автоматическим сбором данных (APScheduler)
5. **Реализовано ансамблевое прогнозирование** (Prophet + NeuralProphet + XGBoost + LightGBM)
6. **Разработан современный UI** на React с 8 страницами (Recharts + ECharts) и адаптивным дизайном
7. **Реализован корреляционный анализ** событий и загруженности
8. **Обеспечена безопасность** — Rate Limiting, API key auth, CORS, экранирование SQL
9. **Контейнеризация** — Docker Compose (PostgreSQL 16 + Redis 7 + Backend + Frontend)

### Технические показатели

| Метрика | Значение |
|---------|----------|
| Отелей в БД | 1 366 |
| Записей статистики | 37 663 |
| Событий из 8 источников | 318 |
| Документов в ChromaDB | 629 |
| Время ответа API (кэш) | < 100ms |
| Время Ensemble прогноза | ~2 сек (async + кэш) |
| Tool usage rate агента | ~90% |
| Ensemble RMSE (Иркутский) | 2.67 |
| API endpoints | 59 |
| Страниц frontend | 8 |
| Unit тестов | 94 passed |
| E2E тестов | 9/9 passed |

### Результаты тестирования (2026-02-03)

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Backend Health | ✅ OK | Сервер работает |
| ChromaDB | ✅ OK | 535 документов |
| Hotels API | ✅ OK | 1 366 отелей |
| Events API | ✅ OK | 318 событий из 8 источников |
| Analytics KPI | ✅ OK | Все метрики |
| Analytics Correlation | ✅ OK | r=0.96 |
| Analytics Districts | ✅ OK | 5 районов |
| Events Impact | ✅ OK | 5 событий |
| Recommendations | ✅ OK | 4 рекомендации |
| Forecast API | ✅ OK | Ensemble (Prophet + NeuralProphet + XGBoost + LightGBM) |
| AI Query | ✅ OK | Mistral Large (основной LLM) |
| Frontend Pages | ✅ OK | 8/8 страниц (HTTP 200) |

**Общий результат: 17/17 проверок (100%)**

### Обновления по результатам аудита (2026-02-03)

#### PostgreSQL и data_service / db_service
- Основное хранилище: PostgreSQL 16 (Docker), SQLAlchemy 2.0 + asyncpg
- Единая точка доступа: `data_service` и `DBService` (`db_service.py`)
- Параметризованные запросы и экранирование `%`, `_` в LIKE
- Alembic для миграций схемы

#### LLM Промпт
- Расширен системный промпт с контекстом региона
- Добавлены знания о сезонности и районах
- Улучшена структура инструкций

#### Парсер IRK.ru
- Обновлены селекторы под актуальную структуру сайта 2026
- Улучшен алгоритм извлечения названий событий
- Добавлена фильтрация дубликатов
- Результат: 23 события за один запрос

#### Redis кэширование
- Добавлен Docker-контейнер с Redis 7 Alpine
- Создан асинхронный CacheService
- Кэширование отелей и статистики
- Ускорение запросов в **5 раз** (329ms → 66ms)

#### Парсеры событий
- IRK.ru: 23 события за запрос
- Culture38.ru: 6 событий за запрос
- Добавлен endpoint `/api/parser/events/all` для запуска всех парсеров
- Автоматическое сохранение в PostgreSQL (расписание APScheduler)
- **Всего в базе: 318 событий из 8 источников**

#### UI исправления
- Кнопка "Подробнее" теперь ведёт на /hotels
- Добавлены проценты на PieChart
- Улучшены подписи на графиках
- Адаптивная вёрстка для разных разрешений (1280px-1920px)

#### Политика NO DEMO DATA
- Создано правило `.cursor/rules/no-demo-data.mdc`
- Все данные аналитики берутся из PostgreSQL
- Убраны все хардкод константы SEASON_DATA, DISTRICT_DATA, RECOMMENDATIONS
- При отсутствии данных показывается empty state, а не фейковые данные
- Рекомендации генерируются динамически на основе реальных данных

#### Новые API endpoints аналитики
- `GET /api/analytics/correlation` — корреляция из PostgreSQL
- `GET /api/analytics/districts` — районы из PostgreSQL
- `GET /api/analytics/recommendations` — динамические рекомендации
- `GET /api/analytics/kpi` — KPI из PostgreSQL
- `GET /api/analytics/hotels-by-city` — отели по городам
- `GET /api/analytics/hotels-by-district` — отели по районам

#### Обработка пропущенных данных

**Проблема:** В период Июль-Сентябрь 2025 парсер был неактивен, что привело к отсутствию данных за эти месяцы в таблице `hotels_statistics`.

**Анализ пропусков:**

| Период | Записей | Статус |
|--------|---------|--------|
| Мар 2025 | 1,642 | ✓ |
| Апр 2025 | 4,645 | ✓ |
| Май 2025 | 5,270 | ✓ |
| Июн 2025 | 3,763 | ✓ |
| **Июл-Сен 2025** | **0** | ❌ Парсер неактивен |
| Окт 2025 | 1,108 | ✓ |
| Ноя 2025 | 4,693 | ✓ |
| Дек 2025 | 5,133 | ✓ |
| Янв 2026 | 5,158 | ✓ |
| Фев 2026 | 521 | ✓ (текущий) |

**Покрытие данных:** 9/12 месяцев (75%)

**Принятое решение (вместо генерации синтетических данных):**

1. **Визуализация пропусков** — на графиках серым цветом отображаются периоды без данных
2. **Информационный блок** — на странице аналитики показывается предупреждение о неполных данных
3. **API с метаинформацией** — endpoint `/api/analytics/correlation` возвращает:
   - `hasData: boolean` — флаг для каждого месяца
   - `missing_periods: []` — список пропущенных периодов
   - `data_coverage: "9/12 месяцев"` — показатель полноты данных
4. **Документирование в ВКР** — описание проблемы как урока отказоустойчивости

**Уроки для будущего:**
- Необходим мониторинг работы парсеров (health checks, alerting)
- Автоматический retry при сбоях
- Резервное копирование данных
- Логирование с оповещениями

**Реализация на фронтенде:**

```typescript
// Данные с флагом hasData
type SeasonData = {
  month: string
  occupancy: number
  hasData: boolean  // Флаг наличия реальных данных
}

// Отображение пропусков серым на графике
<Area
  dataKey="missingArea"
  name="Нет данных"
  stroke="hsl(var(--muted-foreground))"
  strokeDasharray="4 4"
  fill="url(#missingGradient)"
/>
```

**Реализация на бэкенде:**

```python
# В /api/analytics/correlation
@router.get("/correlation")
async def get_correlation_data(year: int | None = None) -> Dict[str, Any]:
    """
    Args:
        year: Год для фильтрации (None = все годы)
    """
    stats = await data_service.get_monthly_statistics(year=year)
    
    # Определяем доступные годы для UI
    available_years = sorted(set(
        int(row.get("date_str", "")[:4]) for row in all_stats
    ))
    
    return {
        "months": months_data,
        "missing_periods": missing_periods,
        "data_coverage": f"{len(valid_months)}/12 месяцев",
        "available_years": available_years,  # Для UI селектора
        "selected_year": year,
    }
```

#### Фильтр по году

Добавлена возможность фильтрации данных по году:

| Режим | Покрытие | Описание |
|-------|----------|----------|
| **Все годы** | 9/12 | Агрегация за всё время |
| **2025** | 7/12 | Мар-Июн, Окт-Дек (без летних пропусков) |
| **2026** | 2/12 | Янв-Фев (текущий год) |

**UI компонент:**

```typescript
// Селектор года в header страницы Analytics
<select
  value={selectedYear ?? ''}
  onChange={(e) => setSelectedYear(e.target.value ? Number(e.target.value) : null)}
>
  <option value="">Все годы</option>
  {availableYears.map((year) => (
    <option key={year} value={year}>{year}</option>
  ))}
</select>

// useQuery с зависимостью от года
const { data } = useQuery({
  queryKey: ['correlation', selectedYear],
  queryFn: () => api.getCorrelation(selectedYear),
})
```

**Преимущества:**
- При выборе "Все годы" — пропуски размываются со временем
- При выборе конкретного года — видны реальные пропуски
- Для ВКР — демонстрация гибкости системы

### Научная новизна

1. **Ансамблевое прогнозирование** загруженности отелей (Prophet + NeuralProphet + XGBoost + LightGBM) с адаптивной калибровкой весов
2. **AI-агент на LangGraph** с инструментами для аналитики туристической активности
3. **Корреляционный анализ** влияния событий на загруженность с визуализацией пропусков данных
4. **Мультипровайдерная LLM-архитектура** (основной — Mistral Large, до 1B токенов/мес; резервные провайдеры по `LLM_PROVIDER`)
5. **Feature Engineering** (38 признаков) для моделей прогнозирования с учётом погоды и событий

### Рекомендации по развитию

1. **Настроить Alembic** миграции для управления схемой БД
2. **Внедрить мониторинг** (Prometheus + Grafana)
3. **Добавить frontend-тесты** (Vitest)
4. **При необходимости настроить CI/CD** (сбор данных уже по APScheduler, ежедневно)
5. **Расширить географию** парсинга за пределы Иркутской области

---

## ОГРАНИЧЕНИЯ ДАННЫХ И ИНТЕРПРЕТАЦИЯ РЕЗУЛЬТАТОВ

Система использует данные агрегатора 101Hotels как прокси для оценки загруженности средств размещения. Необходимо учитывать следующие ограничения:

1. **Неполнота данных:** В период июль-сентябрь 2025 года сбор данных не осуществлялся, что приводит к разрыву временного ряда и влияет на качество долгосрочных прогнозов.

2. **Репрезентативность источника:** Данные 101Hotels покрывают зарегистрированные на платформе средства размещения, что не включает весь номерной фонд региона. Для полной картины необходимо сопоставление с данными Росстата.

3. **Доверительные интервалы:** Интервалы уверенности ансамбля являются эвристической оценкой неопределённости, основанной на взвешенном среднем интервалов отдельных моделей и межмодельном расхождении, а не калиброванным статистическим интервалом.

4. **Горизонт прогнозирования:** Рекомендуемый горизонт — 7–14 дней. На более длинных горизонтах (30+ дней) качество прогнозов снижается (R² может стать отрицательным).

---

## ПРИЛОЖЕНИЯ

### Приложение А: Структура .env файла

```env
# Database
DB_BACKEND=postgresql
DATABASE_URL=postgresql+asyncpg://tourism:tourism_pass@localhost:5432/tourism

# LLM
LLM_PROVIDER=mistral
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-large-latest

# Embeddings
GIGACHAT_CREDENTIALS=...

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Security
API_KEY=your-secret-key-here
RATE_LIMIT_REQUESTS=60
```

### Приложение Б: Запуск проекта

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Приложение В: API Документация

Доступна по адресу: `http://localhost:8000/docs` (Swagger UI)

---

*Документ подготовлен: Февраль 2026*
*Последнее обновление: 12.03.2026*
*Версия системы: 2.0.0*
