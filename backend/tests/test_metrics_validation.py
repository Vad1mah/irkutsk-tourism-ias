"""
Тестовый сценарий для валидации метрик AI-агента.

Метрики:
1. Hallucination rate - галлюцинации адресов/цен/дат
2. Tool selection accuracy - правильность выбора инструмента
3. Tone adaptation accuracy - адаптация тона по сегменту
4. Response relevance - релевантность ответа

Запуск:
    cd backend
    python -m pytest tests/test_metrics_validation.py -v -s
    
Или напрямую:
    cd backend
    python tests/test_metrics_validation.py
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """Тестовый сценарий."""
    
    id: str
    query: str
    expected_tool: str  # Ожидаемый tool
    segment: str  # "tourist" или "business"
    hallucination_checks: list[str] = field(default_factory=list)  # Паттерны галлюцинаций
    tone_keywords: list[str] = field(default_factory=list)  # Ключевые слова тона


@dataclass
class TestResult:
    """Результат теста."""
    
    test_id: str
    query: str
    response: str
    tools_used: list[str]
    expected_tool: str
    tool_correct: bool
    hallucinations_found: list[str]
    hallucination_rate: float  # 0.0 - 1.0
    tone_correct: bool
    tone_keywords_found: list[str]
    response_time_ms: float


# Тестовые сценарии для B2C (туристы)
TOURIST_TESTS = [
    TestCase(
        id="T1",
        query="Где остановиться в Листвянке?",
        expected_tool="SearchHotels",
        segment="tourist",
        hallucination_checks=[
            r"ул\.\s*\w+",  # Выдуманные улицы
            r"д\.\s*\d+",  # Номера домов
            r"\d{3,4}\s*руб",  # Цены без источника
        ],
        tone_keywords=["рекомендую", "подойдёт", "выбор", "отдых", "советую"],
    ),
    TestCase(
        id="T2",
        query="Какие события в Иркутске в феврале?",
        expected_tool="SearchEvents",
        segment="tourist",
        hallucination_checks=[
            r"202[0-4]",  # Старые даты
            r"будет проходить.*\d{4}",  # Неверный год
        ],
        tone_keywords=["рекомендую", "посетить", "интересно", "событие"],
    ),
    TestCase(
        id="T3",
        query="Какая погода сейчас на Байкале?",
        expected_tool="GetWeather",
        segment="tourist",
        hallucination_checks=[],  # Погода из API — не галлюцинация
        tone_keywords=["сейчас", "температура", "погода"],
    ),
    TestCase(
        id="T4",
        query="Куда поехать на выходные с семьёй?",
        expected_tool="SearchHotels",
        segment="tourist",
        hallucination_checks=[
            r"ул\.\s*\w+",
            r"от\s*\d+\s*руб",  # Если нет в данных
        ],
        tone_keywords=["рекомендую", "семь", "подойдёт", "отдых"],
    ),
    TestCase(
        id="T5",
        query="Привет! Что ты умеешь?",
        expected_tool="GeneralQuestion",
        segment="tourist",
        hallucination_checks=[],
        tone_keywords=["помочь", "могу", "отели", "событ", "погод"],
    ),
]

# Тестовые сценарии для B2B (бизнес)
BUSINESS_TESTS = [
    TestCase(
        id="B1",
        query="Прогноз загрузки Иркутского района на 14 дней",
        expected_tool="ForecastOccupancy",
        segment="business",
        hallucination_checks=[],  # Прогноз из модели
        tone_keywords=["прогноз", "загрузк", "анализ", "рекоменд", "оптимиз"],
    ),
    TestCase(
        id="B2",
        query="Какая ожидается загрузка в Ольхонском районе?",
        expected_tool="ForecastOccupancy",
        segment="business",
        hallucination_checks=[],
        tone_keywords=["прогноз", "загрузк", "район", "период"],
    ),
    TestCase(
        id="B3",
        query="Анализ загрузки для моего отеля в Слюдянке",
        expected_tool="ForecastOccupancy",
        segment="business",
        hallucination_checks=[],
        tone_keywords=["прогноз", "анализ", "загрузк", "рекоменд"],
    ),
]

# Все тесты
ALL_TESTS = TOURIST_TESTS + BUSINESS_TESTS


def _check_hallucinations(response: str, patterns: list[str]) -> list[str]:
    """Проверяет наличие паттернов галлюцинаций в ответе."""
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        if matches:
            found.extend(matches)
    return found


def _check_tone_keywords(response: str, keywords: list[str]) -> list[str]:
    """Проверяет наличие ключевых слов тона в ответе."""
    found = []
    response_lower = response.lower()
    for keyword in keywords:
        if keyword.lower() in response_lower:
            found.append(keyword)
    return found


async def run_single_test(test: TestCase) -> TestResult:
    """Запускает один тест."""
    import sys
    import os
    
    # Добавляем путь к backend
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app.services.llm_service import llm_service
    
    # Инициализируем сервис если нужно
    if llm_service._client is None:
        llm_service.init()
    
    start_time = datetime.now()
    
    try:
        response, tools_used = await llm_service.generate_response_with_tools(test.query)
    except Exception as e:
        logger.error(f"Error in test {test.id}: {e}")
        return TestResult(
            test_id=test.id,
            query=test.query,
            response=f"ERROR: {e}",
            tools_used=[],
            expected_tool=test.expected_tool,
            tool_correct=False,
            hallucinations_found=["ERROR"],
            hallucination_rate=1.0,
            tone_correct=False,
            tone_keywords_found=[],
            response_time_ms=0,
        )
    
    elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
    
    # Проверка tool selection
    tool_correct = test.expected_tool in tools_used
    
    # Проверка галлюцинаций
    hallucinations = _check_hallucinations(response, test.hallucination_checks)
    hallucination_rate = len(hallucinations) / max(len(test.hallucination_checks), 1) if test.hallucination_checks else 0.0
    
    # Проверка тона
    tone_keywords_found = _check_tone_keywords(response, test.tone_keywords)
    tone_correct = len(tone_keywords_found) >= len(test.tone_keywords) // 2 if test.tone_keywords else True
    
    return TestResult(
        test_id=test.id,
        query=test.query,
        response=response[:500] + "..." if len(response) > 500 else response,
        tools_used=tools_used,
        expected_tool=test.expected_tool,
        tool_correct=tool_correct,
        hallucinations_found=hallucinations,
        hallucination_rate=hallucination_rate,
        tone_correct=tone_correct,
        tone_keywords_found=tone_keywords_found,
        response_time_ms=elapsed_ms,
    )


async def run_all_tests() -> dict[str, Any]:
    """Запускает все тесты и возвращает агрегированные метрики."""
    logger.info("=" * 60)
    logger.info("ВАЛИДАЦИЯ МЕТРИК AI-АГЕНТА")
    logger.info(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    results: list[TestResult] = []
    
    for test in ALL_TESTS:
        logger.info(f"\n[{test.id}] {test.query[:50]}...")
        result = await run_single_test(test)
        results.append(result)
        
        # Логируем результат
        status = "✅" if result.tool_correct and result.hallucination_rate == 0 else "❌"
        logger.info(f"  Tool: {result.tools_used} (expected: {result.expected_tool}) - {'✓' if result.tool_correct else '✗'}")
        logger.info(f"  Hallucinations: {result.hallucinations_found if result.hallucinations_found else 'None'}")
        logger.info(f"  Tone keywords: {result.tone_keywords_found}")
        logger.info(f"  Time: {result.response_time_ms:.0f}ms")
        logger.info(f"  Status: {status}")
    
    # Агрегированные метрики
    total = len(results)
    tool_accuracy = sum(1 for r in results if r.tool_correct) / total
    hallucination_rate = sum(r.hallucination_rate for r in results) / total
    tone_accuracy = sum(1 for r in results if r.tone_correct) / total
    avg_response_time = sum(r.response_time_ms for r in results) / total
    
    # Метрики по сегментам
    tourist_results = [r for r, t in zip(results, ALL_TESTS) if t.segment == "tourist"]
    business_results = [r for r, t in zip(results, ALL_TESTS) if t.segment == "business"]
    
    tourist_tool_acc = sum(1 for r in tourist_results if r.tool_correct) / len(tourist_results) if tourist_results else 0
    business_tool_acc = sum(1 for r in business_results if r.tool_correct) / len(business_results) if business_results else 0
    
    metrics = {
        "date": datetime.now().isoformat(),
        "total_tests": total,
        "metrics": {
            "tool_selection_accuracy": round(tool_accuracy * 100, 1),
            "hallucination_rate": round(hallucination_rate * 100, 1),
            "tone_adaptation_accuracy": round(tone_accuracy * 100, 1),
            "avg_response_time_ms": round(avg_response_time, 0),
        },
        "by_segment": {
            "tourist": {
                "tests": len(tourist_results),
                "tool_accuracy": round(tourist_tool_acc * 100, 1),
            },
            "business": {
                "tests": len(business_results),
                "tool_accuracy": round(business_tool_acc * 100, 1),
            },
        },
        "targets": {
            "tool_selection_accuracy": ">90%",
            "hallucination_rate": "<5%",
            "tone_adaptation_accuracy": ">90%",
        },
        "results": [
            {
                "test_id": r.test_id,
                "tool_correct": r.tool_correct,
                "hallucinations": r.hallucinations_found,
                "tone_correct": r.tone_correct,
            }
            for r in results
        ],
    }
    
    # Итоговый отчёт
    logger.info("\n" + "=" * 60)
    logger.info("ИТОГОВЫЕ МЕТРИКИ")
    logger.info("=" * 60)
    logger.info(f"Tool Selection Accuracy: {metrics['metrics']['tool_selection_accuracy']}% (target: >90%)")
    logger.info(f"Hallucination Rate: {metrics['metrics']['hallucination_rate']}% (target: <5%)")
    logger.info(f"Tone Adaptation Accuracy: {metrics['metrics']['tone_adaptation_accuracy']}% (target: >90%)")
    logger.info(f"Avg Response Time: {metrics['metrics']['avg_response_time_ms']}ms")
    logger.info("-" * 60)
    logger.info(f"Tourist segment: {metrics['by_segment']['tourist']['tool_accuracy']}% tool accuracy")
    logger.info(f"Business segment: {metrics['by_segment']['business']['tool_accuracy']}% tool accuracy")
    logger.info("=" * 60)
    
    # Оценка
    all_passed = (
        metrics["metrics"]["tool_selection_accuracy"] >= 90
        and metrics["metrics"]["hallucination_rate"] <= 5
        and metrics["metrics"]["tone_adaptation_accuracy"] >= 90
    )
    
    if all_passed:
        logger.info("🎉 ВСЕ МЕТРИКИ В ПРЕДЕЛАХ ЦЕЛЕВЫХ ЗНАЧЕНИЙ!")
    else:
        logger.info("⚠️ Некоторые метрики требуют улучшения")
    
    return metrics


async def save_metrics_report(metrics: dict[str, Any], filepath: str = "tests/metrics_report.json"):
    """Сохраняет отчёт о метриках в JSON."""
    import os
    
    # Создаём директорию если нужно
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\nОтчёт сохранён: {filepath}")


if __name__ == "__main__":
    import sys
    import os
    
    # Добавляем путь к backend для импортов
    backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, backend_path)
    
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv(os.path.join(backend_path, ".env"))
    
    # Запускаем тесты
    metrics = asyncio.run(run_all_tests())
    
    # Сохраняем отчёт
    asyncio.run(save_metrics_report(metrics, os.path.join(backend_path, "tests/metrics_report.json")))
