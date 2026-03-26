"""
Массовое тестирование LLM на разных температурах.

Проверяет:
- Выбор правильного tool
- Фактическую точность (даты, названия)
- Отсутствие галлюцинаций (выдуманные адреса, цены)
- Соответствие промпту
"""

import asyncio
import json
import re
import httpx
from dataclasses import dataclass
from datetime import datetime


BASE_URL = "http://localhost:8000"
TEMPERATURES = [0.1, 0.2, 0.3, 0.5, 0.7]


@dataclass
class TestCase:
    """Тестовый кейс."""
    name: str
    query: str
    expected_tool: str
    # Проверки
    must_contain: list[str] = None  # Должно содержать
    must_not_contain: list[str] = None  # НЕ должно содержать (галлюцинации)
    date_check: str = None  # Проверка даты (regex)
    fact_check: dict = None  # Проверка фактов {ключ: значение}


# =============================================================================
# ТЕСТОВЫЕ КЕЙСЫ
# =============================================================================

TEST_CASES = [
    # --- GENERAL QUESTIONS ---
    TestCase(
        name="Приветствие",
        query="Привет!",
        expected_tool="GeneralQuestion",
        must_contain=["помо"],  # "помочь" или "помогу"
        must_not_contain=["ул.", "от 2000", "от 3000"],
    ),
    TestCase(
        name="Что умеешь",
        query="Что ты умеешь?",
        expected_tool="GeneralQuestion",
        must_contain=["отел"],  # упоминание возможностей
    ),
    
    # --- HOTELS ---
    TestCase(
        name="Отели Листвянка",
        query="Где остановиться в Листвянке?",
        expected_tool="SearchHotels",
        must_contain=["листвянк", "отел"],
        must_not_contain=[
            "ул. Набережная",  # Выдуманный адрес
            "ул. Горького",
            "от 2000 руб",  # Выдуманные цены если нет в данных
            "от 3500 руб",
        ],
    ),
    TestCase(
        name="Отели Хужир",
        query="Посоветуй отели в Хужире",
        expected_tool="SearchHotels",
        must_contain=["хужир", "ольхон"],
        must_not_contain=["ул. Байкальская", "проспект"],
    ),
    TestCase(
        name="Недорогие отели",
        query="Недорогие отели на Байкале",
        expected_tool="SearchHotels",
        must_contain=["отел"],
    ),
    
    # --- EVENTS ---
    TestCase(
        name="Концерты февраль",
        query="Какие концерты в феврале?",
        expected_tool="SearchEvents",
        must_contain=["концерт"],  # "февраль" или "февраля"
        date_check=r"202[5-6]",  # Год должен быть актуальным
    ),
    TestCase(
        name="Фестивали",
        query="Какие фестивали будут в этом году?",
        expected_tool="SearchEvents",
        must_not_contain=["2022", "2023", "2024"],  # Не старые даты
    ),
    TestCase(
        name="События выходные",
        query="Что интересного на выходных?",
        expected_tool="SearchEvents",
    ),
    
    # --- WEATHER ---
    TestCase(
        name="Погода Иркутск",
        query="Какая погода в Иркутске?",
        expected_tool="GetWeather",
        must_contain=["температур", "°C", "иркутск"],
    ),
    TestCase(
        name="Погода Листвянка",
        query="Погода в Листвянке сейчас",
        expected_tool="GetWeather",
        must_contain=["листвянк"],
    ),
    TestCase(
        name="Погода для поездки",
        query="Стоит ли сейчас ехать на Байкал, какая там погода?",
        expected_tool="GetWeather",
    ),
    
    # --- EDGE CASES (галлюцинации) ---
    TestCase(
        name="Адрес отеля",
        query="Какой адрес у отеля в Листвянке?",
        expected_tool="SearchHotels",
        must_not_contain=[
            "ул.",  # Не должен выдумывать улицы
            "д.",
            "дом",
            "№",
        ],
    ),
    TestCase(
        name="Цена номера",
        query="Сколько стоит номер в отеле на Байкале?",
        expected_tool="SearchHotels",
        must_not_contain=[
            "от 1000",
            "от 2000",
            "от 3000",
            "руб/сутки",
        ],
    ),
    
    # --- MIXED / COMPLEX ---
    TestCase(
        name="Комплексный вопрос",
        query="Хочу на выходные на Байкал, что посоветуешь?",
        expected_tool="SearchHotels",  # или GeneralQuestion
    ),
]


# =============================================================================
# ТЕСТИРОВАНИЕ
# =============================================================================

async def set_temperature(client: httpx.AsyncClient, temp: float) -> bool:
    """Устанавливает температуру через рестарт (упрощённо через env)."""
    # В реальности нужно менять .env и рестартить
    # Здесь просто проверяем что сервер работает
    try:
        r = await client.get(f"{BASE_URL}/api/query/llm-info")
        return r.status_code == 200
    except Exception:
        return False


async def run_query(client: httpx.AsyncClient, query: str) -> dict:
    """Выполняет запрос к API."""
    try:
        r = await client.post(
            f"{BASE_URL}/api/query?mode=tools",
            json={"text": query},
            timeout=60.0,
        )
        if r.status_code == 200:
            return r.json()
        return {"error": f"Status {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def check_test_case(test: TestCase, result: dict) -> dict:
    """Проверяет результат теста."""
    checks = {
        "tool_correct": False,
        "must_contain": True,
        "must_not_contain": True,
        "date_check": True,
        "issues": [],
    }
    
    answer = result.get("answer", "").lower()
    sources = result.get("sources", [])
    
    # 1. Проверка tool
    if test.expected_tool in sources:
        checks["tool_correct"] = True
    else:
        checks["issues"].append(f"Tool: ожидался {test.expected_tool}, получен {sources}")
    
    # 2. Must contain
    if test.must_contain:
        for word in test.must_contain:
            if word.lower() not in answer:
                checks["must_contain"] = False
                checks["issues"].append(f"Отсутствует: '{word}'")
    
    # 3. Must NOT contain (галлюцинации)
    if test.must_not_contain:
        for word in test.must_not_contain:
            if word.lower() in answer:
                checks["must_not_contain"] = False
                checks["issues"].append(f"ГАЛЛЮЦИНАЦИЯ: '{word}'")
    
    # 4. Date check
    if test.date_check:
        if not re.search(test.date_check, answer):
            checks["date_check"] = False
            checks["issues"].append(f"Дата не найдена: {test.date_check}")
    
    # Общий результат
    checks["passed"] = all([
        checks["tool_correct"],
        checks["must_contain"],
        checks["must_not_contain"],
        checks["date_check"],
    ])
    
    return checks


async def run_tests_for_temperature(temp: float) -> dict:
    """Запускает все тесты для конкретной температуры."""
    print(f"\n{'='*60}")
    print(f"ТЕМПЕРАТУРА: {temp}")
    print(f"{'='*60}")
    
    results = {
        "temperature": temp,
        "total": len(TEST_CASES),
        "passed": 0,
        "failed": 0,
        "details": [],
    }
    
    async with httpx.AsyncClient() as client:
        for test in TEST_CASES:
            print(f"\n[{test.name}] {test.query[:50]}...")
            
            result = await run_query(client, test.query)
            
            if "error" in result:
                print(f"  ❌ ERROR: {result['error']}")
                results["failed"] += 1
                results["details"].append({
                    "name": test.name,
                    "passed": False,
                    "error": result["error"],
                })
                continue
            
            checks = check_test_case(test, result)
            
            if checks["passed"]:
                print(f"  ✅ PASS - Tool: {result.get('sources')}")
                results["passed"] += 1
            else:
                print(f"  ❌ FAIL - {checks['issues']}")
                results["failed"] += 1
            
            results["details"].append({
                "name": test.name,
                "query": test.query,
                "passed": checks["passed"],
                "tool_used": result.get("sources"),
                "expected_tool": test.expected_tool,
                "issues": checks["issues"],
                "answer_preview": result.get("answer", "")[:200],
            })
            
            # Небольшая пауза между запросами
            await asyncio.sleep(0.5)
    
    print(f"\n--- Итого temp={temp}: {results['passed']}/{results['total']} passed ---")
    return results


async def main():
    """Главная функция тестирования."""
    print("=" * 60)
    print("МАССОВОЕ ТЕСТИРОВАНИЕ LLM")
    print(f"Время: {datetime.now().isoformat()}")
    print(f"Тестов: {len(TEST_CASES)}")
    print("=" * 60)
    
    # Проверяем сервер
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{BASE_URL}/api/query/llm-info")
            info = r.json()
            print(f"LLM: {info.get('model')}, temp={info.get('temperature')}")
        except Exception as e:
            print(f"❌ Сервер недоступен: {e}")
            return
    
    # Запускаем тесты для текущей температуры
    # (Для разных температур нужно менять .env и рестартить)
    results = await run_tests_for_temperature(0.2)
    
    # Сохраняем результаты
    output_file = f"/Users/vad1mah/Downloads/Diplom/backend/tests/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 Результаты сохранены: {output_file}")
    
    # Вывод статистики
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Всего тестов: {results['total']}")
    print(f"Пройдено: {results['passed']} ({results['passed']/results['total']*100:.1f}%)")
    print(f"Провалено: {results['failed']}")
    
    # Детали провалов
    failed = [d for d in results["details"] if not d["passed"]]
    if failed:
        print("\n❌ ПРОВАЛЕННЫЕ ТЕСТЫ:")
        for f in failed:
            print(f"  - {f['name']}: {f.get('issues', f.get('error'))}")


if __name__ == "__main__":
    asyncio.run(main())
