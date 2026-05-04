"""Роутер для AI-агента с поддержкой tools и SSE streaming."""
import asyncio
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
import logging

from app.models.schemas import QueryRequest, QueryResponse
from app.dependencies import (
    LLMServiceDep,
    ChromaServiceDep,
    verify_api_key,
)
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

_STREAM_COUNTER_KEY = "query:active_streams"
_STREAM_TTL_SECONDS = 600  # автосброс зависших
_MAX_CONCURRENT_STREAMS = 3


async def increment_active_stream() -> int:
    """Атомарно увеличить счётчик активных SSE-стримов (Redis INCR)."""
    if cache_service.client is None:
        return 0
    val = await cache_service.client.incr(_STREAM_COUNTER_KEY)
    await cache_service.client.expire(_STREAM_COUNTER_KEY, _STREAM_TTL_SECONDS)
    return int(val)


async def decrement_active_stream() -> int:
    """Атомарно уменьшить счётчик активных SSE-стримов (Redis DECR)."""
    if cache_service.client is None:
        return 0
    val = await cache_service.client.decr(_STREAM_COUNTER_KEY)
    if val < 0:
        await cache_service.client.set(_STREAM_COUNTER_KEY, 0)
        return 0
    return int(val)


async def get_active_streams() -> int:
    """Получить текущее значение счётчика активных SSE-стримов."""
    if cache_service.client is None:
        return 0
    val = await cache_service.client.get(_STREAM_COUNTER_KEY)
    return int(val or 0)


@router.post("", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    llm: LLMServiceDep,
    chroma: ChromaServiceDep,
    mode: Literal["tools", "rag"] = Query("tools", description="Режим: 'tools' (агент с tools) или 'rag' (RAG)"),
):
    """
    Обработка запроса к AI-агенту.

    Args:
        request: Запрос с текстом вопроса
        mode: Режим работы — 'tools' (по умолчанию) или 'rag'

    Returns:
        Ответ AI с источниками/tools
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Текст запроса не может быть пустым")

    if not chroma.is_initialized:
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен. Попробуйте позже."
        )

    try:
        query = request.text.strip()

        if mode == "tools":
            answer, tools_used = await llm.generate_response_with_tools(
                query, session_id=request.session_id,
            )
            return QueryResponse(answer=answer, sources=tools_used)
        else:
            # RAG режим (legacy)
            answer, sources = await llm.generate_response(query)
            return QueryResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка обработки запроса. Попробуйте позже."
        )


@router.post("/stream")
async def stream_query(request: QueryRequest, chroma: ChromaServiceDep):
    """SSE streaming: токены AI-ответа в реальном времени."""
    if not request.text or not request.text.strip():
        raise HTTPException(400, "Текст запроса не может быть пустым")

    if not chroma.is_initialized:
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен. Попробуйте позже."
        )

    current = await get_active_streams()
    if current >= _MAX_CONCURRENT_STREAMS:
        raise HTTPException(429, "Too many concurrent streams")

    from app.services.main_agent import main_agent

    async def event_generator():
        await increment_active_stream()
        agen = main_agent.stream(
            message=request.text.strip(),
            session_id=request.session_id,
        )
        try:
            while True:
                try:
                    event = await asyncio.wait_for(agen.__anext__(), timeout=120)
                except StopAsyncIteration:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            logger.warning("SSE stream timeout (120s)")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Превышено время ожидания ответа'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Внутренняя ошибка обработки запроса'}, ensure_ascii=False)}\n\n"
        finally:
            await decrement_active_stream()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def query_health(chroma: ChromaServiceDep):
    """Проверка состояния AI-агента."""
    return {
        "status": "ok",
        "chroma_initialized": chroma.is_initialized,
        "documents_count": chroma.get_collection_count(),
    }


@router.get("/llm-info", dependencies=[Depends(verify_api_key)])
async def get_llm_info(llm: LLMServiceDep):
    """
    Информация о текущем LLM провайдере.

    Returns:
        Информация о провайдере, модели, настройках
    """
    return llm.get_provider_info()


@router.post("/test-llm", dependencies=[Depends(verify_api_key)])
async def test_llm(
    llm: LLMServiceDep,
    prompt: str = "Привет! Кратко расскажи о Байкале.",
):
    """
    Тест LLM без RAG контекста.

    Args:
        prompt: Тестовый промпт

    Returns:
        Ответ LLM и метаданные
    """
    try:
        response = await llm.generate_simple(prompt)
        return {
            "status": "ok",
            "prompt": prompt,
            "response": response,
            "provider": llm.get_provider_info(),
        }
    except Exception as e:
        logger.error(f"LLM test error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="LLM service unavailable")
