"""
LangGraph Agent для туристической аналитики Байкала.

Архитектура:
- StateGraph с conditional routing
- Tools для поиска, погоды, прогнозов
- Визуализация графа (Mermaid)
- Работает с любым LLM (Mistral, GigaChat, Groq)

Документация: docs/LANGGRAPH_AGENT.md
"""
import json
import logging
import uuid
from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

from app.config import settings
from app.constants import (
    AGENT_MAX_TOOL_CALLS,
    AGENT_RECURSION_LIMIT,
    AGENT_SEARCH_RESULTS,
    CITY_TO_DISTRICT,
    LOCATIONS,
    MONTH_NAMES_RU,
)
from app.services.chroma_service import chroma_service
from app.services.weather_service import weather_service

logger = logging.getLogger(__name__)


# =============================================================================
# STATE DEFINITION
# =============================================================================

class AgentState(TypedDict):
    """Состояние агента между узлами графа."""
    messages: Annotated[list[BaseMessage], add_messages]
    tool_calls_count: int  # Счетчик вызовов tools (для защиты от loop)


# =============================================================================
# TOOLS DEFINITION (LangChain @tool decorator)
# =============================================================================

@tool
def search_hotels(location: str = "Байкал", query: str = "") -> str:
    """Поиск отелей и баз отдыха на Байкале.
    
    Используй когда пользователь спрашивает:
    - Где остановиться / переночевать
    - Отели в конкретном месте (Листвянка, Ольхон, Хужир)
    - Рекомендации по размещению
    
    Args:
        location: Город или район (Листвянка, Хужир, Иркутск, Ольхон)
        query: Дополнительные критерии (недорого, с видом на озеро)
    """
    search_query = f"отели {location} {query}".strip()
    logger.info(f"[Tool] search_hotels: {search_query}")
    
    # Поиск в ChromaDB
    where_filter = {"type": "hotel"}
    if location and location.lower() != "байкал":
        where_filter = {
            "$and": [
                {"type": "hotel"},
                {"city": location}
            ]
        }
    
    docs = chroma_service.search(
        query=search_query,
        n_results=AGENT_SEARCH_RESULTS,
        where=where_filter
    )
    
    # Fallback без фильтра города
    if not docs and location:
        docs = chroma_service.search(
            query=search_query,
            n_results=AGENT_SEARCH_RESULTS,
            where={"type": "hotel"}
        )
    
    if not docs:
        return f"Не найдено отелей по запросу '{location}'. Попробуйте другой район."
    
    result_parts = [f"Найдено {len(docs)} отелей в районе {location}:\n"]
    for doc in docs:
        text = doc.get("text", "")
        result_parts.append(f"- {text}")
    
    return "\n".join(result_parts)


@tool
def search_events(query: str, month: int | None = None) -> str:
    """Поиск событий и мероприятий в Иркутской области.
    
    Используй когда пользователь спрашивает:
    - Что происходит / какие события
    - Концерты, фестивали, выставки
    - Куда сходить / что посмотреть
    
    Args:
        query: Поисковый запрос (концерт, фестиваль, выставка)
        month: Месяц (1-12) если указан
    """
    search_query = query
    if month:
        search_query = f"{query} {MONTH_NAMES_RU.get(month, '')}"
    
    logger.info(f"[Tool] search_events: {search_query}")
    
    # Фильтр: только будущие события
    today_epoch_days = (date.today() - date(1970, 1, 1)).days
    
    try:
        docs = chroma_service.search(
            query=search_query,
            n_results=AGENT_SEARCH_RESULTS,
            where={
                "$and": [
                    {"type": "event"},
                    {"date_epoch_days": {"$gte": today_epoch_days}}
                ]
            }
        )
    except Exception:
        docs = chroma_service.search(query=search_query, n_results=AGENT_SEARCH_RESULTS)
        docs = [d for d in docs if d.get("metadata", {}).get("type") == "event"]
    
    if not docs:
        return f"Не найдено событий по запросу '{query}'. Попробуйте другой период."
    
    result_parts = ["Предстоящие события:\n"]
    for doc in docs:
        meta = doc.get("metadata", {})
        text = doc.get("text", "")
        date_str = meta.get("date_start", "")
        result_parts.append(f"- [{date_str}] {text}")
    
    return "\n".join(result_parts)


@tool
async def get_weather(location: str = "Иркутск") -> str:
    """Получить текущую погоду на Байкале.
    
    Используй когда пользователь спрашивает:
    - Какая погода сейчас / сегодня
    - Погода в конкретном месте
    
    Args:
        location: Локация (Иркутск, Листвянка, Ольхон/Хужир)
    """
    logger.info(f"[Tool] get_weather: {location}")
    
    lat, lon = LOCATIONS.get(location.lower(), LOCATIONS["иркутск"])
    weather = await weather_service.get_current_weather(lat=lat, lon=lon)
    
    if not weather:
        return f"Не удалось получить погоду для {location}."
    
    temp = weather.get("temperature", "?")
    condition = weather.get("description", weather.get("condition", "неизвестно"))
    wind = weather.get("wind_speed", "?")
    
    return f"""Погода в {location} сейчас:
- Температура: {temp}°C
- Условия: {condition}
- Ветер: {wind} м/с"""


@tool
async def forecast_occupancy(district: str, days: int = 7) -> str:
    """Прогноз загрузки отелей для бизнеса.
    
    Используй когда пользователь (владелец отеля, аналитик) спрашивает:
    - Какая будет загрузка
    - Прогноз на следующую неделю/месяц
    - Ожидаемый спрос
    
    Args:
        district: Район Байкала (Иркутский, Ольхонский, Слюдянский)
        days: На сколько дней прогноз (7, 14, 30)
    """
    district = CITY_TO_DISTRICT.get(district.lower(), district)
    
    logger.info(f"[Tool] forecast_occupancy: {district}, {days} дней")
    
    try:
        from app.services.forecast_agent import forecast_agent
        
        result = await forecast_agent.run(
            district=district,
            days_ahead=days,
        )
        
        if result.get("error"):
            logger.warning(f"Forecast error detail: {result['error']}")
            return "Прогноз временно недоступен. Попробуйте позже."
        
        forecast_values = result.get("forecasts", {}).get(result.get("best_model", ""), [])
        explanation = result.get("explanation", "")
        
        parts = [f"Прогноз загрузки для {district} района на {days} дней:\n"]
        
        if forecast_values:
            avg_occupancy = sum(f.get("occupancy", 0) for f in forecast_values) / len(forecast_values)
            parts.append(f"Средняя ожидаемая загрузка: {avg_occupancy:.1f}%\n")
        
        if explanation:
            parts.append(f"\nАнализ:\n{explanation}")
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        return "Прогноз временно недоступен. Попробуйте позже."


@tool
async def get_statistics() -> str:
    """Получить общую статистику системы: количество отелей, событий, загрузку.

    Используй когда пользователь спрашивает:
    - Сколько отелей / всего отелей в базе
    - Сколько событий / мероприятий
    - Какая загрузка / средняя загрузка
    - Общая статистика / KPI
    """
    logger.info("[Tool] get_statistics")

    try:
        from app.services.data_service import data_service

        if not data_service.is_connected:
            return "База данных временно недоступна."

        metrics = await data_service.get_total_metrics()
        districts = await data_service.get_districts_statistics()

        total_rooms = sum(d.get("total_rooms", 0) or 0 for d in districts) if districts else 0
        free_rooms = sum(d.get("free_rooms", 0) or 0 for d in districts) if districts else 0
        avg_occupancy = 0
        if districts:
            occupancies = [d.get("avg_occupancy", 0) or 0 for d in districts if d.get("avg_occupancy")]
            avg_occupancy = round(sum(occupancies) / len(occupancies), 1) if occupancies else 0

        result = f"""Статистика системы (по данным на сегодня):
- Всего отелей: {metrics.get('total_hotels', 0)}
- Населённых пунктов: {metrics.get('total_cities', 0)}
- Событий в календаре: {metrics.get('total_events', 0)}
- Всего номеров: {total_rooms}
- Свободных номеров: {free_rooms}
- Средняя загрузка: {avg_occupancy}%"""

        return result

    except Exception as e:
        logger.error(f"[Tool] get_statistics error: {e}")
        return "Не удалось получить статистику. Попробуйте позже."


# Список всех tools
ALL_TOOLS = [search_hotels, search_events, get_weather, forecast_occupancy, get_statistics]
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


# =============================================================================
# LLM INITIALIZATION
# =============================================================================

_llm_with_tools = None


def get_llm_with_tools():
    """Получить LLM с привязанными tools."""
    global _llm_with_tools
    if _llm_with_tools is not None:
        return _llm_with_tools

    provider = settings.llm_provider.lower()
    
    if provider == "mistral":
        try:
            # Пробуем langchain-mistralai (нативная интеграция)
            from langchain_mistralai import ChatMistralAI
            
            # Параметры по Mistral Best Practices для Function Calling:
            # - temperature=0.1 (рекомендовано для tools)
            # - top_p=0.9 (рекомендовано)
            # Документация: https://docs.mistral.ai/capabilities/function_calling
            llm = ChatMistralAI(
                model=settings.mistral_model,
                api_key=settings.mistral_api_key,
                temperature=0.1,  # Низкая для стабильного tool selection
                max_tokens=settings.mistral_max_tokens,
                top_p=0.9,
            )
            logger.info(f"[Agent] Using ChatMistralAI: {settings.mistral_model}, temp=0.1, top_p=0.9")
            _llm_with_tools = llm.bind_tools(ALL_TOOLS)
            return _llm_with_tools
            
        except ImportError:
            # Fallback на ChatOpenAI с настройками для Mistral
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(
                model=settings.mistral_model,
                api_key=settings.mistral_api_key,
                base_url=settings.mistral_base_url,
                temperature=0.1,  # Низкая для стабильного tool selection
            )
            logger.info(f"[Agent] Using ChatOpenAI for Mistral: {settings.mistral_model}")
            _llm_with_tools = llm.bind_tools(ALL_TOOLS)
            return _llm_with_tools
    
    elif provider == "gigachat":
        from langchain_gigachat import GigaChat
        
        credentials = settings.gigachat_llm_credentials or settings.gigachat_credentials
        scope = settings.gigachat_llm_scope or settings.gigachat_scope
        
        llm = GigaChat(
            credentials=credentials,
            scope=scope,
            model=settings.gigachat_model,
            verify_ssl_certs=settings.gigachat_verify_ssl,
            temperature=settings.gigachat_temperature,
        )
        _llm_with_tools = llm.bind_tools(ALL_TOOLS)
        return _llm_with_tools
    
    elif provider == "groq":
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=settings.groq_temperature,
        )
        _llm_with_tools = llm.bind_tools(ALL_TOOLS)
        return _llm_with_tools
    
    else:
        raise ValueError(f"Provider {provider} not supported for tools")


# =============================================================================
# GRAPH NODES
# =============================================================================

# System Prompt оптимизирован по Mistral Best Practices:
# - Простой и понятный (не дублирует tools specs)
# - Ключевые ограничения сохранены
# - Примеры использования tools
# Документация: https://docs.mistral.ai/capabilities/function_calling
def _build_system_prompt() -> str:
    """Формирует системный промпт с актуальной датой."""
    return f"""Ты — AI-ассистент по туризму на Байкале и в Иркутской области.
Сегодня: {date.today().strftime("%d.%m.%Y")}

Ты ОБЯЗАН использовать инструменты для получения актуальных данных.

Правила:
- Отвечай на русском языке
- ВСЕГДА используй инструменты для получения данных — не выдумывай информацию
- Если данных нет в результате инструмента — честно скажи об этом
- Для бизнес-пользователей (прогноз загрузки) используй профессиональный тон

Примеры использования инструментов:
- "Сколько отелей в базе?" → get_statistics
- "Какая загрузка сейчас?" → get_statistics
- "Где остановиться в Листвянке?" → search_hotels(location="Листвянка")
- "Какие события в марте?" → search_events(query="события", month=3)
- "Какая погода?" → get_weather()
- "Прогноз загрузки на неделю" → forecast_occupancy()"""


def _dedup_tool_call_ids(messages: list) -> list:
    """Перегенерировать все tool_call_id уникальными значениями (Mistral fix)."""
    id_map: dict[str, str] = {}
    counter = [0]

    def _new_id(old_id: str) -> str:
        if old_id not in id_map:
            counter[0] += 1
            id_map[old_id] = f"call_{uuid.uuid4().hex[:12]}"
        return id_map[old_id]

    result = []
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            new_tc = [{**tc, "id": _new_id(tc["id"])} for tc in msg.tool_calls]
            new_kwargs = {}
            for k, v in (msg.additional_kwargs or {}).items():
                if k == "tool_calls":
                    new_kwargs[k] = [
                        {**rc, "id": _new_id(rc.get("id", ""))} for rc in v
                    ]
                else:
                    new_kwargs[k] = v
            result.append(AIMessage(
                content=msg.content or "",
                tool_calls=new_tc,
                additional_kwargs=new_kwargs,
            ))
        elif isinstance(msg, ToolMessage):
            new_tcid = id_map.get(msg.tool_call_id, msg.tool_call_id)
            result.append(ToolMessage(content=msg.content, tool_call_id=new_tcid))
        else:
            result.append(msg)
    return result


async def call_model(state: AgentState) -> Command[Literal["tools", "__end__"]]:
    """Node: Вызов LLM. Маршрутизация через Command."""
    messages = state["messages"]
    
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=_build_system_prompt())] + list(messages)
    
    messages = _dedup_tool_call_ids(messages)
    llm_with_tools = get_llm_with_tools()
    
    try:
        response = await llm_with_tools.ainvoke(messages)
        logger.info(f"[LLM] Response: {response.content[:100] if response.content else 'tool_call'}...")
        
        has_tools = hasattr(response, "tool_calls") and response.tool_calls
        if has_tools and state.get("tool_calls_count", 0) < AGENT_MAX_TOOL_CALLS:
            return Command(update={"messages": [response]}, goto="tools")
        
        return Command(update={"messages": [response]}, goto="__end__")
    except Exception as e:
        err_str = str(e)
        if "Duplicate tool call id" in err_str:
            logger.warning("[LLM] Mistral duplicate ID — retrying without tool history")
            clean = [m for m in messages if not isinstance(m, (ToolMessage, )) 
                     and not (isinstance(m, AIMessage) and getattr(m, "tool_calls", None))]
            tool_results = [m for m in messages if isinstance(m, ToolMessage)]
            if tool_results:
                summary = "; ".join(r.content[:200] for r in tool_results)
                clean.append(HumanMessage(content=f"[Результаты инструментов]: {summary}"))
            try:
                response = await llm_with_tools.ainvoke(clean)
                return Command(update={"messages": [response]}, goto="__end__")
            except Exception as e2:
                logger.error(f"[LLM] Retry also failed: {e2}")
        logger.error(f"[LLM] Error: {e}")
        error_msg = AIMessage(content="Извините, произошла ошибка при обработке запроса. Попробуйте позже.")
        return Command(update={"messages": [error_msg]}, goto="__end__")


async def call_tools(state: AgentState) -> Command[Literal["model"]]:
    """Node: Выполнение вызванных tools. Всегда возвращает в model."""
    last_message = state["messages"][-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return Command(
            update={"tool_calls_count": state.get("tool_calls_count", 0)},
            goto="model",
        )
    
    results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        logger.info(f"[Tool] Executing: {tool_name}({tool_args})")
        
        tool_func = TOOLS_BY_NAME.get(tool_name)
        if not tool_func:
            result = f"Неизвестный инструмент: {tool_name}"
        else:
            try:
                result = await tool_func.ainvoke(tool_args)
            except Exception as e:
                logger.error(f"[Tool] Error in {tool_name}: {e}")
                try:
                    import asyncio
                    result = await asyncio.to_thread(tool_func.invoke, tool_args)
                except Exception as e2:
                    logger.error(f"[Tool] Sync fallback error: {e2}")
                    result = f"Инструмент {tool_name} временно недоступен."
        
        results.append(ToolMessage(content=str(result), tool_call_id=tool_id))
    
    new_count = state.get("tool_calls_count", 0) + len(results)
    return Command(
        update={"messages": results, "tool_calls_count": new_count},
        goto="model",
    )


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def build_agent_graph() -> StateGraph:
    """Построить граф агента.
    
    Маршрутизация через Command внутри узлов:
    - call_model → tools (если есть tool_calls) или __end__
    - call_tools → model (всегда)
    """
    graph = StateGraph(AgentState)
    
    graph.add_edge(START, "model")
    graph.add_node("model", call_model)
    graph.add_node("tools", call_tools)
    
    return graph


from langgraph.checkpoint.memory import MemorySaver

_agent_graph = None
_compiled_agent = None
_checkpointer = MemorySaver()

_MAX_SESSIONS = 100
_SESSION_TTL = 3600


def _cleanup_checkpointer():
    """Remove old sessions from MemorySaver to prevent OOM."""
    if not hasattr(_checkpointer, 'storage'):
        return
    storage = _checkpointer.storage
    if len(storage) > _MAX_SESSIONS:
        keys = list(storage.keys())
        to_remove = len(keys) - _MAX_SESSIONS
        for key in keys[:to_remove]:
            del storage[key]
        logger.info(f"MemorySaver cleanup: removed {to_remove} old sessions")


def get_agent():
    """Получить скомпилированный агент с checkpointer (singleton)."""
    global _agent_graph, _compiled_agent
    
    if _compiled_agent is None:
        _agent_graph = build_agent_graph()
        _compiled_agent = _agent_graph.compile(checkpointer=_checkpointer)
        logger.info("[Agent] LangGraph agent compiled with MemorySaver checkpointer")
    
    return _compiled_agent


# =============================================================================
# PUBLIC API
# =============================================================================

class MainAgent:
    """
    Главный LangGraph агент для туристической аналитики.
    
    Использование:
        agent = MainAgent()
        response = await agent.chat("Где остановиться в Листвянке?")
    """
    
    def __init__(self):
        self._agent = None
        self._graph = None
    
    def _ensure_initialized(self):
        """Ленивая инициализация агента (с checkpointer)."""
        if self._agent is None:
            self._agent = get_agent()
            logger.info("[MainAgent] Initialized with checkpointer")
    
    async def chat(
        self,
        message: str,
        history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> tuple[str, list[str]]:
        """
        Отправить сообщение агенту.
        
        Args:
            message: Сообщение пользователя
            history: История (игнорируется при наличии session_id — checkpointer хранит)
            session_id: ID сессии для LangGraph checkpointer (thread_id)
            
        Returns:
            tuple[str, list[str]]: (ответ агента, список использованных tools)
        """
        self._ensure_initialized()
        _cleanup_checkpointer()
        
        messages = [HumanMessage(content=message)]
        
        config = {"recursion_limit": AGENT_RECURSION_LIMIT}
        if session_id:
            config["configurable"] = {"thread_id": session_id}
        
        tools_used = []
        
        try:
            result = await self._agent.ainvoke(
                {"messages": messages, "tool_calls_count": 0},
                config=config,
            )
            
            # Собираем использованные tools
            for msg in result["messages"]:
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tools_used.append(tc["name"])
            
            # Последнее сообщение — ответ
            final_message = result["messages"][-1]
            response = final_message.content if hasattr(final_message, "content") else str(final_message)
            
            return response, list(set(tools_used))
            
        except Exception as e:
            logger.error(f"[MainAgent] Error: {e}")
            return "Извините, произошла ошибка при обработке запроса. Попробуйте позже.", []
    
    async def stream(
        self,
        message: str,
        session_id: str | None = None,
    ):
        """Стриминг ответа агента через astream.

        Yields:
            dict с ключами type/content/tool для SSE.
        """
        self._ensure_initialized()
        _cleanup_checkpointer()

        config = {"recursion_limit": AGENT_RECURSION_LIMIT}
        if session_id:
            config["configurable"] = {"thread_id": session_id}

        tools_used: list[str] = []

        async for event in self._agent.astream_events(
            {"messages": [HumanMessage(content=message)], "tool_calls_count": 0},
            config=config,
            version="v2",
        ):
            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {"type": "token", "content": chunk.content}
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tools_used.append(tool_name)
                yield {"type": "tool_start", "tool": tool_name}
            elif kind == "on_tool_end":
                yield {"type": "tool_end", "tool": event.get("name", "")}

        yield {"type": "done", "tools": tools_used}
    
    def get_graph_mermaid(self) -> str:
        """Получить Mermaid-диаграмму графа."""
        self._ensure_initialized()
        # get_graph() вызывается на скомпилированном агенте
        return self._agent.get_graph().draw_mermaid()
    
    def get_graph_png(self) -> bytes:
        """Получить PNG-изображение графа."""
        self._ensure_initialized()
        return self._agent.get_graph().draw_mermaid_png()
    
    def save_graph_png(self, path: str = "agent_graph.png"):
        """Сохранить граф как PNG."""
        png_data = self.get_graph_png()
        with open(path, "wb") as f:
            f.write(png_data)
        logger.info(f"[MainAgent] Graph saved to {path}")


# Глобальный экземпляр
main_agent = MainAgent()
