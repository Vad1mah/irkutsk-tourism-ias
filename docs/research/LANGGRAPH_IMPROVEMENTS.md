# Улучшение LangGraph агентов

> **Статус: улучшения реализованы.** Command паттерн, расширенный State и структурированный вывод внедрены в main_agent.py и forecast_agent.py (25.03.2026). Визуализация графа доступна для документации.

## Текущее состояние

### main_agent.py
- `StateGraph` + `TypedDict` (AgentState)
- Conditional branching через `should_continue()`
- 5 инструментов: search_hotels, search_events, get_weather, forecast_occupancy, get_statistics
- Основной LLM: **Mistral Large**; альтернативы: GigaChat, Groq и др.

### forecast_agent.py
- Линейный пайплайн: collect_data → run_models → analyze_factors → generate_explanation
- `TypedDict` (ForecastState) с 15+ полями
- Использует Prophet, NeuralProphet, XGBoost
- Fallback-механизмы при ошибке LLM

### main_agent.py (tools)
- Инструменты и Pydantic-схемы для bind_tools определены в `main_agent.py` (отдельный `agent_tools.py` удалён)
- Handlers: execute_search_*, execute_get_weather, execute_forecast_occupancy и др.

## Эталонный паттерн (executory_formula.ipynb)

Ключевые элементы:
1. `Command` для контроля потока (вместо conditional edges)
2. `DocState(MessagesState)` — расширение MessagesState
3. Pydantic модели для структурированного вывода (`PydanticOutputParser`)
4. RAG пайплайн: extract → split → build_index → extract_data
5. Явная типизация переходов: `Command[Literal["__end__", "next_node"]]`
6. Визуализация графа: `PngDrawer` для отладки

## План улучшений

### 1. Переход на Command паттерн (main_agent.py)

```python
# Было:
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    ...

# Станет:
def call_model(state: AgentState) -> Command[Literal["tools", "__end__"]]:
    response = await llm.ainvoke(messages)
    if response.tool_calls:
        return Command(update={"messages": [response]}, goto="tools")
    return Command(update={"messages": [response]}, goto="__end__")
```

Преимущества:
- Явное управление потоком в каждом узле
- Проще отлаживать
- Лучше видно логику маршрутизации

### 2. Расширение State (forecast_agent.py)

```python
class ForecastState(MessagesState):
    district: str
    days_ahead: int
    history: list[dict]
    weather_data: dict
    forecasts: dict[str, list[dict]]
    best_model: str
    explanation: str
    error: Optional[str]
    last_reason: Annotated[Optional[str], operator.add]  # Для отладки
```

### 3. Структурированный вывод через Pydantic

```python
class ForecastResult(BaseModel):
    occupancy: float = Field(description="Прогноз загрузки (%)")
    confidence: float = Field(description="Уверенность модели")
    factors: list[str] = Field(description="Факторы влияния")
    recommendation: str = Field(description="Рекомендация")

parser = PydanticOutputParser(pydantic_object=ForecastResult)
chain = prompt | llm | parser
```

### 4. Визуализация графа для отладки

```python
from langchain_core.runnables.graph_png import PngDrawer
drawer = PngDrawer()
drawer.draw(app.get_graph(), "agent_graph.png")
```

### 5. Conditional routing в forecast_agent

```python
def run_models(state: ForecastState) -> Command[Literal["analyze_factors", "__end__"]]:
    if not state["history"] or len(state["history"]) < 14:
        return Command(
            update={"error": "Недостаточно данных"},
            goto="__end__"
        )
    # ... запуск моделей ...
    return Command(update={"forecasts": results}, goto="analyze_factors")
```

## Приоритет реализации (статус)

1. ✅ Command паттерн в main_agent — реализован, упрощает отладку
2. ✅ Структурированный вывод — Pydantic модели для tool responses
3. ✅ Расширение State — TypedDict с полной типизацией
4. ✅ Визуализация графа — доступна через `app.get_graph().draw_mermaid()`
