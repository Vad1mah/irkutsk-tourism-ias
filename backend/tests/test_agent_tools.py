"""Unit тесты для agent_tools.

Запуск:
    cd backend
    pytest tests/test_agent_tools.py -v
"""
from datetime import date


class TestAllToolsRegistration:
    """Тесты регистрации tools."""

    def test_all_tools_has_get_statistics(self):
        """Test that get_statistics is registered in ALL_TOOLS."""
        from app.services.main_agent import ALL_TOOLS

        tool_names = [t.name for t in ALL_TOOLS]
        assert "get_statistics" in tool_names

    def test_all_tools_has_revenue_metrics(self):
        """B2B: get_revenue_metrics зарегистрирован (RevPAR/ADR/Occupancy)."""
        from app.services.main_agent import ALL_TOOLS

        tool_names = [t.name for t in ALL_TOOLS]
        assert "get_revenue_metrics" in tool_names

    def test_all_tools_count(self):
        """Ожидаем минимум 6 tools (после B2B-рефокуса)."""
        from app.services.main_agent import ALL_TOOLS

        assert len(ALL_TOOLS) >= 6

    def test_tools_by_name_dict(self):
        """Test TOOLS_BY_NAME mapping включает все 6 B2B-tools."""
        from app.services.main_agent import TOOLS_BY_NAME

        assert "get_statistics" in TOOLS_BY_NAME
        assert "search_hotels" in TOOLS_BY_NAME
        assert "search_events" in TOOLS_BY_NAME
        assert "get_weather" in TOOLS_BY_NAME
        assert "forecast_occupancy" in TOOLS_BY_NAME
        assert "get_revenue_metrics" in TOOLS_BY_NAME


class TestSystemPrompt:
    """Тесты для системного промпта."""

    def test_system_prompt_has_examples(self):
        from app.services.main_agent import _build_system_prompt

        prompt = _build_system_prompt()
        assert "get_statistics" in prompt
        assert "search_hotels" in prompt

    def test_system_prompt_has_rules(self):
        from app.services.main_agent import _build_system_prompt

        prompt = _build_system_prompt()
        assert "русском" in prompt.lower()

    def test_system_prompt_has_today_date(self):
        from app.services.main_agent import _build_system_prompt

        prompt = _build_system_prompt()
        today = date.today().strftime("%d.%m.%Y")
        assert today in prompt


class TestToolDefinitions:
    """Тесты определений tools."""

    def test_get_statistics_is_async_tool(self):
        """Test that get_statistics is async StructuredTool."""
        from app.services.main_agent import get_statistics

        # StructuredTool с coroutine
        assert hasattr(get_statistics, 'coroutine')
        assert get_statistics.coroutine is not None

    def test_search_hotels_docstring(self):
        """search_hotels: B2B-формулировка про реестр объектов размещения."""
        from app.services.main_agent import search_hotels

        assert search_hotels.description is not None
        desc = search_hotels.description.lower()
        assert "размещени" in desc or "реестр" in desc or "объект" in desc

    def test_search_events_docstring(self):
        """Test that search_events has proper docstring."""
        from app.services.main_agent import search_events

        assert search_events.description is not None
        assert "событий" in search_events.description.lower() or "event" in search_events.description.lower()

    def test_get_weather_is_async_tool(self):
        """Test that get_weather is async StructuredTool."""
        from app.services.main_agent import get_weather

        assert hasattr(get_weather, 'coroutine')
        assert get_weather.coroutine is not None

    def test_forecast_occupancy_is_async_tool(self):
        """Test that forecast_occupancy is async StructuredTool."""
        from app.services.main_agent import forecast_occupancy

        assert hasattr(forecast_occupancy, 'coroutine')
        assert forecast_occupancy.coroutine is not None


class TestAgentState:
    """Тесты для AgentState."""

    def test_agent_state_has_messages(self):
        """Test that AgentState has messages field."""
        from app.services.main_agent import AgentState

        # AgentState должен иметь поле messages
        assert "messages" in AgentState.__annotations__

    def test_agent_state_has_tool_calls_count(self):
        """Test that AgentState has tool_calls_count field."""
        from app.services.main_agent import AgentState

        assert "tool_calls_count" in AgentState.__annotations__


class TestMainAgent:
    """Тесты для MainAgent класса."""

    def test_main_agent_can_be_created(self):
        """Test that MainAgent can be created."""
        from app.services.main_agent import MainAgent

        agent = MainAgent()
        assert agent is not None

    def test_main_agent_has_chat_method(self):
        """Test that MainAgent has chat method."""
        from app.services.main_agent import MainAgent

        agent = MainAgent()
        assert hasattr(agent, "chat")
        assert callable(agent.chat)

    def test_main_agent_has_ensure_initialized(self):
        """Test that MainAgent has _ensure_initialized method."""
        from app.services.main_agent import MainAgent

        agent = MainAgent()
        assert hasattr(agent, "_ensure_initialized")


class TestB2BFocus:
    """B2B-курс: после рефокуса 06.04.2026 промпты и tools — про отельеров,
    администрацию, исследователей. Туристические формулировки — мёртвый курс."""

    def test_main_agent_prompt_b2b_role(self):
        """Главный промпт фиксирует роль B2B-аналитика."""
        from app.services.main_agent import _build_system_prompt

        prompt = _build_system_prompt().lower()
        assert "b2b" in prompt or "аналитик" in prompt
        assert "отельер" in prompt or "размещени" in prompt

    def test_main_agent_prompt_b2b_segments_named(self):
        """Главный промпт явно перечисляет три B2B-сегмента."""
        from app.services.main_agent import _build_system_prompt

        prompt = _build_system_prompt().lower()
        assert "отельер" in prompt
        assert "администраци" in prompt
        assert "исследовател" in prompt

    def test_llm_service_prompt_b2b_role(self):
        """RAG-промпт в llm_service фиксирует B2B-роль и три сегмента."""
        from app.services.llm_service import _build_system_prompt

        prompt = _build_system_prompt().lower()
        assert "b2b" in prompt or "отельер" in prompt
        assert "администраци" in prompt
        assert "исследовател" in prompt

    def test_get_revenue_metrics_is_async_tool(self):
        """get_revenue_metrics — async StructuredTool."""
        from app.services.main_agent import get_revenue_metrics

        assert hasattr(get_revenue_metrics, "coroutine")
        assert get_revenue_metrics.coroutine is not None

    def test_get_revenue_metrics_docstring_mentions_rms_metrics(self):
        """В описании tool явно фигурируют RevPAR / ADR / Occupancy."""
        from app.services.main_agent import get_revenue_metrics

        desc = get_revenue_metrics.description
        assert desc is not None
        desc_lower = desc.lower()
        assert "revpar" in desc_lower
        assert "adr" in desc_lower
        assert "occupancy" in desc_lower or "загрузк" in desc_lower
