"""Unit тесты для agent_tools.

Запуск:
    cd backend
    pytest tests/test_agent_tools.py -v
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock


class TestAllToolsRegistration:
    """Тесты регистрации tools."""

    def test_all_tools_has_get_statistics(self):
        """Test that get_statistics is registered in ALL_TOOLS."""
        from app.services.main_agent import ALL_TOOLS

        tool_names = [t.name for t in ALL_TOOLS]
        assert "get_statistics" in tool_names

    def test_all_tools_count(self):
        """Test that we have expected number of tools."""
        from app.services.main_agent import ALL_TOOLS

        # Ожидаем минимум 5 tools
        assert len(ALL_TOOLS) >= 5

    def test_tools_by_name_dict(self):
        """Test TOOLS_BY_NAME mapping."""
        from app.services.main_agent import TOOLS_BY_NAME

        assert "get_statistics" in TOOLS_BY_NAME
        assert "search_hotels" in TOOLS_BY_NAME
        assert "search_events" in TOOLS_BY_NAME
        assert "get_weather" in TOOLS_BY_NAME
        assert "forecast_occupancy" in TOOLS_BY_NAME


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
        """Test that search_hotels has proper docstring."""
        from app.services.main_agent import search_hotels

        assert search_hotels.description is not None
        assert "отелей" in search_hotels.description.lower() or "hotel" in search_hotels.description.lower()

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
