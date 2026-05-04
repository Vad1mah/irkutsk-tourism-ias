"""Тестирование LLM-провайдеров на function calling.

Прогоняет один и тот же tool-aware запрос через разные провайдеры
и фиксирует: инициализация / tool selection / финальный синтез / время.

Запуск:
    & "C:\\Users\\Admin\\Desktop\\Diplom\\backend\\venv\\Scripts\\python.exe" \\
      C:/Users/Admin/Desktop/Diplom/backend/scripts/test_llm_providers.py [provider1 provider2 ...]

Без аргументов прогоняет все доступные (gigachat исключён по умолчанию).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=Warning)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(BACKEND_ROOT / ".env")

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

ALL_PROVIDERS = ["mistral", "groq", "deepseek", "openrouter", "gemini"]


@tool
def get_district_occupancy(district: str, days_ahead: int = 7) -> str:
    """Возвращает прогноз загрузки гостиничного фонда по району.

    Args:
        district: Название района Иркутской области (например, 'Иркутский', 'Ольхонский').
        days_ahead: На сколько дней вперёд нужен прогноз (1-30).
    """
    return (
        f"Прогноз для {district} на {days_ahead} дней: "
        f"средняя Occupancy=42.8%, RevPAR=2510 ₽, ADR=5860 ₽."
    )


@tool
def get_top_events(district: str, limit: int = 3) -> str:
    """Возвращает топ-N событий по влиянию на спрос на размещение.

    Args:
        district: Район Иркутской области.
        limit: Количество событий (1-10).
    """
    return (
        f"Топ-{limit} событий для {district}: "
        f"1) Фестиваль хоров «Мы вместе» (12 мая, impact +6.5%); "
        f"2) Концерт Игоря Старкова (13 мая, impact +4.2%); "
        f"3) Майские праздники (9 мая, impact +12.1%)."
    )


TEST_TOOLS = [get_district_occupancy, get_top_events]

QUERY = (
    "Дай прогноз загрузки по Иркутскому району на 7 дней "
    "и три ключевых события, которые повлияют на спрос."
)

SYSTEM = (
    "Ты — B2B-аналитик гостиничного рынка. "
    "Используй инструменты для получения данных. "
    "Не выдумывай числа — только из tool-результатов. "
    "Финальный ответ давай в одном-двух абзацах."
)


def _build_llm(provider: str):
    """Возвращает (llm_with_tools, model_name) или поднимает исключение."""
    if provider == "mistral":
        from langchain_mistralai import ChatMistralAI
        model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        llm = ChatMistralAI(
            model=model,
            api_key=os.environ["MISTRAL_API_KEY"],
            temperature=0.1,
            top_p=0.9,
        )
        return llm.bind_tools(TEST_TOOLS), model

    if provider == "groq":
        from langchain_openai import ChatOpenAI
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatOpenAI(
            model=model,
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
            temperature=0.1,
        )
        return llm.bind_tools(TEST_TOOLS), model

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        llm = ChatOpenAI(
            model=model,
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            temperature=0.1,
        )
        return llm.bind_tools(TEST_TOOLS), model

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
        llm = ChatOpenAI(
            model=model,
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            temperature=0.1,
        )
        return llm.bind_tools(TEST_TOOLS), model

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("langchain_google_genai не установлен") from exc
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(
            model=model,
            api_key=os.environ["GEMINI_API_KEY"],
            temperature=0.1,
        )
        return llm.bind_tools(TEST_TOOLS), model

    raise ValueError(f"Unknown provider: {provider}")


async def _run_tool_loop(llm_with_tools, query: str) -> dict[str, Any]:
    """Простейший loop: model -> tools -> model. Не больше двух итераций."""
    tools_by_name = {t.name: t for t in TEST_TOOLS}
    messages: list = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=query),
    ]

    tools_used: list[str] = []
    iteration = 0
    while iteration < 3:
        iteration += 1
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            content = response.content if isinstance(response.content, str) else str(response.content)
            return {
                "answer": content,
                "tools_used": tools_used,
                "iterations": iteration,
            }

        for tc in tool_calls:
            tools_used.append(tc["name"])
            tool_func = tools_by_name.get(tc["name"])
            if tool_func is None:
                tool_result = f"unknown tool {tc['name']}"
            else:
                tool_result = tool_func.invoke(tc["args"])
            from langchain_core.messages import ToolMessage
            messages.append(ToolMessage(content=str(tool_result), tool_call_id=tc["id"]))

    return {
        "answer": "(превышен лимит итераций tool-loop)",
        "tools_used": tools_used,
        "iterations": iteration,
    }


async def test_provider(provider: str) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"PROVIDER: {provider}")
    print('='*60)
    started = time.time()
    try:
        llm_with_tools, model = _build_llm(provider)
        print(f"  model       : {model}")
        result = await _run_tool_loop(llm_with_tools, QUERY)
        elapsed = time.time() - started
        print(f"  iterations  : {result['iterations']}")
        print(f"  tools_used  : {result['tools_used']}")
        print(f"  elapsed     : {elapsed:.2f}s")
        print(f"  answer      : {result['answer'][:400]}")
        return {
            "provider": provider,
            "model": model,
            "ok": bool(result["answer"].strip()),
            "tools_used": result["tools_used"],
            "iterations": result["iterations"],
            "elapsed": round(elapsed, 2),
            "answer_len": len(result["answer"]),
            "answer_preview": result["answer"][:200],
        }
    except Exception as exc:
        elapsed = time.time() - started
        print(f"  ERROR ({type(exc).__name__}): {exc}")
        return {
            "provider": provider,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:300],
            "elapsed": round(elapsed, 2),
        }


async def main() -> None:
    if len(sys.argv) > 1:
        providers = sys.argv[1:]
    else:
        providers = [p for p in ALL_PROVIDERS if p != "gigachat"]

    print(f"Testing providers: {providers}")
    results: list[dict[str, Any]] = []
    for p in providers:
        results.append(await test_provider(p))

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        info = f"{r['provider']:<12} {status:<5} {r.get('elapsed', '?'):>6}s"
        if r.get("ok"):
            info += f" tools={r['tools_used']} iters={r['iterations']} answer={r['answer_len']} chars"
        else:
            info += f" {r.get('error', '')[:120]}"
        print(info)


if __name__ == "__main__":
    asyncio.run(main())
