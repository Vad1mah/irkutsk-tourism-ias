"""Сервис для работы с LLM (Gemini, GigaChat, Groq, Mistral, DeepSeek, OpenRouter)."""
import logging
from datetime import date
from typing import Any

from app.config import settings
from app.constants import LOCATIONS
from app.services.chroma_service import chroma_service

logger = logging.getLogger(__name__)


def _filter_past_events(docs: list[dict]) -> list[dict]:
    """Фильтрация прошедших событий из результатов RAG."""
    today = date.today().isoformat()
    filtered = []
    
    for doc in docs:
        metadata = doc.get("metadata", {})
        doc_type = metadata.get("type", "")
        
        # Если это не событие — оставляем
        if doc_type != "event":
            filtered.append(doc)
            continue
        
        # Для событий проверяем дату
        date_start = metadata.get("date_start", "")
        if not date_start:
            # Нет даты — оставляем (для старых записей)
            filtered.append(doc)
            continue
        
        # Сравниваем даты
        if date_start >= today:
            filtered.append(doc)
        # Прошедшие события пропускаем
    
    return filtered


def _build_system_prompt() -> str:
    today = date.today()
    today_str = today.strftime("%d.%m.%Y")
    month_names = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return f"""### Роль
Ты — B2B-аналитик информационной системы «Прибайкалье» для трёх сегментов профессиональных пользователей:
- отельеры (владельцы и менеджеры средств размещения),
- региональная администрация (министерство туризма Иркутской области),
- исследователи туристического рынка.

Сегодня: {today.day} {month_names[today.month]} {today.year} ({today_str}).

### Твои возможности
- Аналитика реестра средств размещения по районам Иркутской области
- Метрики событийной активности и её влияния на загрузку
- Прогноз загрузки и спроса на основе ансамбля ML-моделей (Prophet + NeuralProphet + XGBoost)
- Расчёт RMS-показателей: загруженность (Occupancy %), при наличии данных — RevPAR, ADR
- Объяснение динамики и факторов спроса для бизнес-решений

### Задача
Отвечать на запросы профессиональных пользователей, используя контекст из базы данных. Тон — деловой, без маркетинговой риторики и туристических рекомендаций.

### Инструкция
1. На приветствие — кратко представься как B2B-аналитик системы и предложи направления анализа.
2. Изучи контекст, найди релевантные данные.
3. Отвечай конкретно: указывай районы, даты, числовые метрики.
4. Даты из контекста копируй ТОЧНО, не меняй год/месяц/день.
5. Если данных нет в контексте — честно скажи об этом, НЕ выдумывай цифры.
6. Давай интерпретацию для бизнес-решений (загрузка, спрос, ценообразование), а не туристические советы «куда поехать».
7. Указывай район для географической привязки результата.
8. НЕ обсуждай события с датами до {today_str}.

### Формат ответа
Деловой стиль, конкретика:
- Числовые метрики с единицами измерения (%, ₽, дни)
- Период данных, к которым относится ответ
- Сравнение с базой / средним по региону, где это уместно
- Краткий вывод для принятия бизнес-решения

### Ограничения
- НЕ выдумывай метрики, цены, адреса — если в контексте нет, так и пиши.
- НЕ давай данные по другим регионам (Москва, СПб и т.д.) — система ограничена Иркутской областью.
- НЕ давай туристические подборки и личные рекомендации по поездкам — это не B2B-задача.
- Если запрос вне темы (личные путешествия, туристические маршруты для частных лиц) — вежливо переформулируй на B2B-плоскость или откажи."""


_DANGEROUS_PATTERNS = [
    "ignore all previous", "ignore above", "system:", "### instruction",
    "you are now", "new role", "забудь все", "игнорируй", "новая роль",
]


def _sanitize_query(query: str) -> str:
    """Basic prompt injection protection."""
    sanitized = query
    lower = sanitized.lower()
    for pattern in _DANGEROUS_PATTERNS:
        idx = lower.find(pattern)
        while idx != -1:
            sanitized = sanitized[:idx] + "[filtered]" + sanitized[idx + len(pattern):]
            lower = sanitized.lower()
            idx = lower.find(pattern)
    return sanitized


class LLMService:
    """
    Универсальный сервис для работы с LLM.
    
    Поддерживаемые провайдеры:
    - Google Gemini (бесплатно 1500 req/day)
    - GigaChat (Сбер) — с поддержкой tools
    - Groq (требует VPN)
    - DeepSeek / OpenRouter
    
    Режимы работы:
    - RAG mode (legacy): поиск контекста → LLM генерирует ответ
    - Tools mode: LLM выбирает tool → выполняется tool → LLM формирует ответ
    """
    
    def __init__(self):
        self._client: Any = None
        self._provider: str = "gemini"
    
    def init(self):
        """Инициализация клиента LLM на основе конфигурации."""
        self._provider = settings.llm_provider.lower()
        
        if self._provider == "gemini":
            self._init_gemini()
        elif self._provider == "gigachat":
            self._init_gigachat()
        elif self._provider == "groq":
            self._init_groq()
        elif self._provider == "mistral":
            self._init_mistral()
        elif self._provider == "deepseek":
            self._init_deepseek()
        elif self._provider == "openrouter":
            self._init_openrouter()
        else:
            logger.warning(f"Unknown LLM provider: {self._provider}, using Gemini")
            self._init_gemini()
        
        logger.info(f"LLM Service initialized: provider={self._provider}")
    
    def _init_gemini(self):
        """Инициализация Google Gemini API (новый SDK google-genai)."""
        api_key = settings.gemini_api_key
        
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, LLM will not work")
            return
        
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key.get_secret_value())
            logger.info(f"Gemini client initialized: model={settings.gemini_model}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
    
    def _init_gigachat(self):
        """Инициализация GigaChat API."""
        credentials = settings.gigachat_llm_credentials or settings.gigachat_credentials
        scope = settings.gigachat_llm_scope or settings.gigachat_scope
        
        if not credentials:
            logger.warning("GIGACHAT_CREDENTIALS not set, LLM will not work")
            return
        
        try:
            from langchain_gigachat import GigaChat
            
            self._client = GigaChat(
                credentials=credentials,
                scope=scope,
                model=settings.gigachat_model,
                verify_ssl_certs=settings.gigachat_verify_ssl,
                temperature=settings.gigachat_temperature,
                max_tokens=settings.gigachat_max_tokens,
                top_p=settings.gigachat_top_p,
                repetition_penalty=settings.gigachat_repetition_penalty,
                timeout=180,
            )
            
            logger.info(
                f"GigaChat client initialized: model={settings.gigachat_model}, "
                f"scope={scope}, temp={settings.gigachat_temperature}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize GigaChat: {e}")
    
    def _init_groq(self):
        """Инициализация Groq API."""
        api_key = settings.groq_api_key
        
        if not api_key:
            logger.warning("GROQ_API_KEY not set, LLM will not work")
            return
        
        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=api_key.get_secret_value())
            logger.info(f"Groq client initialized: model={settings.groq_model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq: {e}")
    
    def _init_mistral(self):
        """Инициализация Mistral API (1B токенов/месяц бесплатно)."""
        api_key = settings.mistral_api_key
        
        if not api_key:
            logger.warning("MISTRAL_API_KEY not set, LLM will not work")
            return
        
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                base_url=settings.mistral_base_url,
                timeout=60.0,
            )
            logger.info(f"Mistral client initialized: model={settings.mistral_model}")
        except Exception as e:
            logger.error(f"Failed to initialize Mistral: {e}")
    
    def _init_deepseek(self):
        """Инициализация DeepSeek API."""
        api_key = settings.deepseek_api_key
        
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY not set, LLM will not work")
            return
        
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                base_url=settings.deepseek_base_url,
                timeout=60.0,
            )
            logger.info(f"DeepSeek client initialized: model={settings.deepseek_model}")
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek: {e}")
    
    def _init_openrouter(self):
        """Инициализация OpenRouter API."""
        api_key = settings.openrouter_api_key
        
        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set, LLM will not work")
            return
        
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                base_url=settings.openrouter_base_url,
                timeout=60.0,
            )
            logger.info(f"OpenRouter client initialized: model={settings.openrouter_model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter: {e}")
    
    def _provider_config(self) -> dict[str, str | int | float]:
        """Конфигурация текущего провайдера (model, max_tokens, temperature)."""
        configs: dict[str, dict] = {
            "gemini": {"model": settings.gemini_model, "max_tokens": settings.gemini_max_tokens, "temperature": settings.gemini_temperature},
            "gigachat": {"model": settings.gigachat_model, "max_tokens": settings.gigachat_max_tokens, "temperature": settings.gigachat_temperature},
            "groq": {"model": settings.groq_model, "max_tokens": settings.groq_max_tokens, "temperature": settings.groq_temperature},
            "mistral": {"model": settings.mistral_model, "max_tokens": settings.mistral_max_tokens, "temperature": settings.mistral_temperature},
            "deepseek": {"model": settings.deepseek_model, "max_tokens": settings.deepseek_max_tokens, "temperature": settings.deepseek_temperature},
            "openrouter": {"model": settings.openrouter_model, "max_tokens": settings.openrouter_max_tokens, "temperature": settings.openrouter_temperature},
        }
        return configs.get(self._provider, configs["openrouter"])

    def _get_model(self) -> str:
        return str(self._provider_config()["model"])

    def _get_max_tokens(self) -> int:
        return int(self._provider_config()["max_tokens"])

    def _get_temperature(self) -> float:
        return float(self._provider_config()["temperature"])
    
    async def _call_gemini(self, messages: list[dict]) -> str:
        """Вызов Google Gemini API (новый SDK)."""
        if not self._client:
            raise ValueError("Gemini client not initialized. Check API key.")
        
        # Конвертируем messages в строку для Gemini
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt_parts.append(f"Инструкция: {content}\n\n")
            elif role == "user":
                prompt_parts.append(f"{content}")
            elif role == "assistant":
                prompt_parts.append(f"Ответ: {content}\n")
        
        prompt = "".join(prompt_parts)
        
        # Gemini API асинхронный
        response = await self._client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        
        return response.text
    
    async def _call_gigachat(self, messages: list[dict]) -> str:
        """Вызов GigaChat API (async через ainvoke)."""
        if not self._client:
            raise ValueError("GigaChat client not initialized. Check credentials.")
        
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        lc_messages = []
        for msg in messages:
            if msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        
        # Нативный async вызов (без run_in_executor) — лучше для производительности
        response = await self._client.ainvoke(lc_messages)
        
        return response.content
    
    async def _call_groq(self, messages: list[dict]) -> str:
        """Вызов Groq API."""
        if not self._client:
            raise ValueError("Groq client not initialized. Check API key.")
        
        response = await self._client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            max_tokens=settings.groq_max_tokens,
            temperature=settings.groq_temperature,
        )
        return response.choices[0].message.content or ""
    
    def _get_mistral_config(self, task_type: str = "default") -> dict:
        """
        Получение оптимальной конфигурации Mistral для типа задачи.
        
        Типы задач (docs/MISTRAL_MODELS_RESEARCH.md):
        - extraction: извлечение JSON, фактов (temp=0.0, fast model)
        - classification: классификация событий (temp=0.0, fast model)  
        - recommendation: персональные рекомендации (temp=0.4, large model)
        - planning: планирование маршрутов (temp=0.4, large model)
        - dialog: общий диалог (temp=0.5, large model)
        - default: стандартные настройки
        """
        configs = {
            "extraction": {
                "model": settings.mistral_model_balanced,  # small
                "temperature": settings.mistral_temp_extraction,  # 0.0
                "max_tokens": 200,
            },
            "classification": {
                "model": settings.mistral_model_fast,  # 8b
                "temperature": settings.mistral_temp_classification,  # 0.0
                "max_tokens": 50,
            },
            "recommendation": {
                "model": settings.mistral_model,  # large
                "temperature": settings.mistral_temp_recommendation,  # 0.4
                "max_tokens": 1000,
            },
            "planning": {
                "model": settings.mistral_model,  # large
                "temperature": settings.mistral_temp_recommendation,  # 0.4
                "max_tokens": 2000,
            },
            "dialog": {
                "model": settings.mistral_model,  # large
                "temperature": settings.mistral_temp_dialog,  # 0.5
                "max_tokens": 500,
            },
            "default": {
                "model": settings.mistral_model,
                "temperature": settings.mistral_temperature,
                "max_tokens": settings.mistral_max_tokens,
            },
        }
        return configs.get(task_type, configs["default"])

    async def _call_mistral(
        self, 
        messages: list[dict], 
        task_type: str = "default",
        json_schema: dict | None = None,
    ) -> str:
        """
        Вызов Mistral API с оптимальными параметрами для задачи.
        
        Args:
            messages: Список сообщений для LLM
            task_type: Тип задачи (extraction/classification/recommendation/planning/dialog)
            json_schema: Опционально - JSON Schema для structured output
        """
        if not self._client:
            raise ValueError("Mistral client not initialized. Check API key.")
        
        config = self._get_mistral_config(task_type)
        
        # Базовые параметры
        # При temperature=0 (greedy sampling) top_p должен быть 1
        top_p = 1.0 if config["temperature"] == 0 else settings.mistral_top_p
        
        params = {
            "model": config["model"],
            "messages": messages,
            "max_tokens": config["max_tokens"],
            "temperature": config["temperature"],
            "top_p": top_p,
        }
        
        # Добавляем json_schema для structured output (best practice из Context7)
        if json_schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "schema": {**json_schema, "type": "object"},
                    "name": "extraction",
                    "strict": True,
                }
            }
        
        response = await self._client.chat.completions.create(**params)
        
        logger.debug(
            f"Mistral call: task={task_type}, model={config['model']}, "
            f"temp={config['temperature']}, json_schema={json_schema is not None}"
        )
        
        return response.choices[0].message.content or ""
    
    async def extract_structured(
        self, 
        text: str, 
        schema: dict,
        system_prompt: str = "Извлеки информацию из текста в JSON формате."
    ) -> dict:
        """
        Извлечение структурированных данных из текста.
        Использует json_schema для гарантированного формата.
        
        Args:
            text: Текст для извлечения
            schema: JSON Schema с properties и required
            system_prompt: Системный промпт
            
        Returns:
            dict с извлеченными данными
        """
        import json
        
        if self._provider != "mistral":
            # Fallback для других провайдеров
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
            response = await self._call_llm(messages)
            try:
                return json.loads(response)
            except (json.JSONDecodeError, ValueError):
                return {"error": "Failed to parse JSON", "raw": response}
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        response = await self._call_mistral(
            messages, 
            task_type="extraction",
            json_schema=schema
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {"error": str(e), "raw": response}
    
    async def _call_openai_compatible(self, messages: list[dict]) -> str:
        """Вызов OpenAI-совместимых API (DeepSeek, OpenRouter)."""
        if not self._client:
            raise ValueError("LLM client not initialized. Check API key.")
        
        params = {
            "model": self._get_model(),
            "messages": messages,
            "stream": False,
        }
        
        if self._provider == "deepseek":
            params["max_tokens"] = self._get_max_tokens()
            params["temperature"] = self._get_temperature()
        else:
            params["extra_headers"] = {
                "HTTP-Referer": "https://baikal-tourism.ru",
                "X-Title": "Baikal Tourism Analytics",
            }
        
        response = await self._client.chat.completions.create(**params)
        return response.choices[0].message.content or ""
    
    async def _call_llm(self, messages: list[dict]) -> str:
        """Унифицированный вызов LLM."""
        if self._provider == "gemini":
            return await self._call_gemini(messages)
        elif self._provider == "gigachat":
            return await self._call_gigachat(messages)
        elif self._provider == "groq":
            return await self._call_groq(messages)
        elif self._provider == "mistral":
            return await self._call_mistral(messages)
        else:
            return await self._call_openai_compatible(messages)
    
    async def generate_response(self, query: str) -> tuple[str, list[str]]:
        """Генерация ответа на запрос пользователя с RAG."""
        from datetime import datetime
        
        query = _sanitize_query(query)
        
        # Вычисляем текущую дату как epoch days (ChromaDB требует числа для $gte)
        today_epoch_days = (date.today() - date(1970, 1, 1)).days
        
        # ChromaDB фильтр: исключаем прошедшие события на уровне БД (эффективнее)
        # Используем $or: либо не событие, либо событие с датой >= сегодня
        chroma_filter = {
            "$or": [
                {"type": {"$ne": "event"}},  # Не события — берём все
                {"date_epoch_days": {"$gte": today_epoch_days}},  # События только будущие
            ]
        }
        
        # Поиск с фильтрацией на уровне ChromaDB
        try:
            relevant_docs = chroma_service.search(
                query, 
                n_results=settings.rag_search_results,
                where=chroma_filter,
            )
        except Exception as e:
            # Fallback без фильтра если ChromaDB не поддерживает
            logger.warning(f"ChromaDB filter error, falling back: {e}")
            relevant_docs = chroma_service.search(query, n_results=settings.rag_search_results)
            # Пост-фильтрация как fallback
            relevant_docs = _filter_past_events(relevant_docs)
        
        context_parts = []
        sources = []
        for doc in relevant_docs:
            context_parts.append(doc["text"])
            if doc["metadata"].get("source"):
                sources.append(doc["metadata"]["source"])
        
        # Добавляем погоду если запрос про погоду или куда поехать
        weather_context = ""
        weather_keywords = ["погод", "сейчас", "сегодня", "куда поехать", "куда съездить", "выходные"]
        query_lower = query.lower()
        if any(kw in query_lower for kw in weather_keywords):
            weather_context = await self._get_weather_context()
        
        context = "\n\n".join(context_parts) if context_parts else "Нет данных в базе."
        
        # Формируем сообщение с погодой если есть
        today_str = date.today().strftime("%d.%m.%Y")
        
        if weather_context:
            user_message = f"""Сегодня: {today_str}

Текущая погода на Байкале:
{weather_context}

Контекст из базы данных:
{context}

Вопрос пользователя: {query}"""
        else:
            user_message = f"""Сегодня: {today_str}

Контекст из базы данных:
{context}

Вопрос пользователя: {query}"""
        
        messages = [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": user_message},
        ]
        
        try:
            answer = await self._call_llm(messages)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer = f"Извините, сервис временно недоступен. Попробуйте позже. ({type(e).__name__})"
        
        return answer, list(set(sources))
    
    async def generate_response_with_tools(
        self, 
        query: str,
        history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> tuple[str, list[str]]:
        """
        Генерация ответа с использованием LangGraph агента с tools.
        
        Args:
            query: Запрос пользователя
            history: История диалога (fallback если нет session_id)
            session_id: ID сессии для LangGraph checkpointer
        
        Returns:
            tuple[str, list[str]]: (ответ, список использованных tools)
        """
        supported_providers = ["mistral", "gigachat", "groq"]
        
        if self._provider not in supported_providers:
            logger.info(f"Provider {self._provider} not supported for tools, falling back to RAG")
            return await self.generate_response(query)
        
        try:
            from app.services.main_agent import main_agent
            
            response, tools_used = await main_agent.chat(
                message=query,
                history=history,
                session_id=session_id,
            )
            
            logger.info(f"[LangGraph] Response generated, tools: {tools_used}")
            return response, tools_used
            
        except Exception as e:
            logger.error(f"LangGraph agent error: {e}")
            # Fallback на RAG-режим
            logger.info("Falling back to RAG mode due to LangGraph error")
            return await self.generate_response(query)
    
    async def _get_weather_context(self) -> str:
        """Получить контекст с текущей погодой."""
        try:
            from app.services.weather_service import weather_service
            
            # Координаты основных точек Байкала
            locations = [
                (name.title(), coords[0], coords[1])
                for name, coords in list(LOCATIONS.items())[:3]
            ]
            
            weather_parts = []
            for name, lat, lon in locations:
                weather = await weather_service.get_current_weather(lat, lon)
                if weather:
                    temp = weather.get("temperature", "?")
                    desc = weather.get("description", "")
                    weather_parts.append(f"{name}: {temp}°C, {desc}")
            
            if weather_parts:
                return "Сейчас:\n" + "\n".join(weather_parts)
        except Exception as e:
            logger.warning(f"Weather fetch error: {e}")
        
        return ""
    
    async def generate_simple(self, prompt: str, system_prompt: str | None = None) -> str:
        """Простая генерация без RAG."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            return await self._call_llm(messages)
        except Exception as e:
            logger.error(f"LLM simple generation error: {e}")
            return f"Ошибка генерации: {type(e).__name__}"
    
    async def explain_forecast(
        self,
        district: str,
        target_date: str,
        occupancy: float,
        factors: list[dict],
    ) -> str:
        """Генерирует объяснение прогноза загрузки."""
        positive = [f for f in factors if f.get("direction") == "positive"]
        negative = [f for f in factors if f.get("direction") == "negative"]
        neutral = [f for f in factors if f.get("direction") not in ("positive", "negative")]

        def _fmt(items: list[dict]) -> str:
            if not items:
                return "нет"
            return "\n".join(
                f"- {f['name']}: {f['description']} (влияние {f.get('impact', '?')}%)"
                for f in items
            )

        level = "высокая" if occupancy > 65 else "средняя" if occupancy > 40 else "низкая"

        prompt = f"""### Район
{district} (Иркутская область, Прибайкалье)

### Прогноз
Дата: {target_date}
Ожидаемая загрузка: {occupancy:.1f}% ({level})

### Факторы роста загрузки
{_fmt(positive)}

### Факторы снижения загрузки
{_fmt(negative)}

### Прочие факторы (ML-модели)
{_fmt(neutral)}

### Задача
1. Напиши краткое резюме прогноза (2-3 предложения), деловым тоном.
2. Перечисли 2-3 главных фактора, влияющих на загрузку.
3. Дай B2B-рекомендацию для отельера (корректировка тарифов, промо, ёмкость) или для администрации (мониторинг показателей региона).
4. Оцени уверенность прогноза (высокая/средняя/низкая) исходя из количества факторов и качества данных.

### Формат ответа
Деловой стиль, кратко, маркированные списки. Без туристических советов."""

        system = (
            "Ты — B2B-аналитик информационной системы «Прибайкалье». "
            "Твои прогнозы основаны на реальных данных: статистика средств размещения, "
            "события региона, погода, праздники. "
            "Отвечаешь по-русски, профессиональным деловым тоном, "
            "пользователи — отельеры, региональная администрация и исследователи рынка."
        )

        return await self.generate_simple(prompt, system)
    
    def get_provider_info(self) -> dict:
        """Возвращает информацию о текущем провайдере."""
        return {
            "provider": self._provider,
            "model": self._get_model(),
            "max_tokens": self._get_max_tokens(),
            "temperature": self._get_temperature(),
            "initialized": self._client is not None,
        }


# Глобальный экземпляр
llm_service = LLMService()
