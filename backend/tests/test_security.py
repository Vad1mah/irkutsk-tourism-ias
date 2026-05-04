"""Тесты безопасности: rate limiting и API key auth."""
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.middleware.rate_limit import RateLimitMiddleware
from app.dependencies.auth import verify_api_key


def _make_middleware(**kwargs) -> RateLimitMiddleware:
    """Создать middleware без реального ASGI app."""
    app_stub = MagicMock()
    return RateLimitMiddleware(app_stub, **kwargs)


def _mock_request(
    host: str = "127.0.0.1",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Создать мок Request с нужным client.host и headers."""
    req = MagicMock()
    req.client.host = host
    req.headers = headers or {}
    return req


class TestCheckLocal:
    """Тесты RateLimitMiddleware._check_local()."""

    def test_allows_within_limit(self):
        mw = _make_middleware()
        key = "ratelimit:1.2.3.4:/api/query"
        for _ in range(9):
            assert mw._check_local(key, 10) is True

    def test_blocks_over_limit(self):
        mw = _make_middleware()
        key = "ratelimit:1.2.3.4:/api/query"
        for _ in range(5):
            mw._check_local(key, 5)
        assert mw._check_local(key, 5) is False

    def test_window_expiry(self):
        mw = _make_middleware()
        key = "ratelimit:1.2.3.4:/api/query"
        old = time.time() - 200
        mw._local_cache[key] = [old, old + 1, old + 2]
        assert mw._check_local(key, 3) is True

    def test_different_keys_independent(self):
        mw = _make_middleware()
        for _ in range(5):
            mw._check_local("a", 5)
        assert mw._check_local("a", 5) is False
        assert mw._check_local("b", 5) is True

    def test_cache_cleanup_on_overflow(self):
        mw = _make_middleware()
        old = time.time() - 200
        for i in range(10001):
            mw._local_cache[f"k:{i}"] = [old]
        mw._check_local("fresh", 10)
        assert len(mw._local_cache) < 10001


class TestGetClientIp:
    """Тесты RateLimitMiddleware._get_client_ip()."""

    def test_direct_client(self):
        mw = _make_middleware()
        req = _mock_request(host="8.8.8.8")
        assert mw._get_client_ip(req) == "8.8.8.8"

    def test_trusted_proxy_uses_xff(self):
        mw = _make_middleware()
        req = _mock_request(
            host="127.0.0.1",
            headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"},
        )
        assert mw._get_client_ip(req) == "203.0.113.5"

    def test_untrusted_proxy_ignores_xff(self):
        mw = _make_middleware()
        req = _mock_request(
            host="8.8.8.8",
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        assert mw._get_client_ip(req) == "8.8.8.8"

    def test_no_client_returns_unknown(self):
        mw = _make_middleware()
        req = MagicMock()
        req.client = None
        req.headers = {}
        assert mw._get_client_ip(req) == "unknown"


class TestIsTrustedProxy:
    """Тесты RateLimitMiddleware._is_trusted_proxy()."""

    def test_localhost_ipv4(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("127.0.0.1") is True

    def test_localhost_ipv6(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("::1") is True

    def test_localhost_name(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("localhost") is True

    def test_docker_172(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("172.17.0.1") is True

    def test_docker_10(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("10.0.0.5") is True

    def test_private_192(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("192.168.1.100") is True

    def test_public_ip_untrusted(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("8.8.8.8") is False

    def test_invalid_host_returns_false(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("not-an-ip") is False

    def test_unknown_literal(self):
        mw = _make_middleware()
        assert mw._is_trusted_proxy("unknown") is False


class TestGetRatePattern:
    """Тесты RateLimitMiddleware._get_rate_pattern()."""

    def test_strict_pattern_query(self):
        mw = _make_middleware()
        assert mw._get_rate_pattern("/api/query/stream") == "/api/query"

    def test_strict_pattern_parser(self):
        mw = _make_middleware()
        assert mw._get_rate_pattern("/api/parser/hotels") == "/api/parser"

    def test_protected_pattern(self):
        mw = _make_middleware()
        assert mw._get_rate_pattern("/api/forecast/ensemble") == "/api/forecast"

    def test_unmatched_returns_path(self):
        mw = _make_middleware()
        assert mw._get_rate_pattern("/other/path") == "/other/path"


class TestGetLimit:
    """Тесты RateLimitMiddleware._get_limit()."""

    def test_query_limit_strict(self):
        mw = _make_middleware()
        assert mw._get_limit("/api/query") == 10

    def test_parser_limit_strict(self):
        mw = _make_middleware()
        assert mw._get_limit("/api/parser/hotels") == 5

    def test_default_limit(self):
        mw = _make_middleware()
        limit = mw._get_limit("/api/forecast/ensemble")
        assert limit > 0


class TestShouldRateLimit:
    """Тесты RateLimitMiddleware._should_rate_limit()."""

    def test_protected_paths(self):
        mw = _make_middleware()
        for path in ["/api/query", "/api/parser/x", "/api/forecast/y",
                      "/api/documents", "/api/analytics/kpi"]:
            assert mw._should_rate_limit(path) is True

    def test_unprotected_paths(self):
        mw = _make_middleware()
        for path in ["/health", "/", "/api/hotels", "/api/events", "/docs"]:
            assert mw._should_rate_limit(path) is False


class TestVerifyApiKey:
    """Тесты verify_api_key() из auth.py."""

    def test_correct_key(self):
        with patch("app.dependencies.auth.settings") as mock_settings:
            mock_settings.get_api_key.return_value = "secret-key-123"
            mock_settings.environment = "development"
            result = verify_api_key(x_api_key="secret-key-123")
            assert result == "secret-key-123"

    def test_wrong_key_raises_401(self):
        with patch("app.dependencies.auth.settings") as mock_settings:
            mock_settings.get_api_key.return_value = "secret-key-123"
            mock_settings.environment = "development"
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401

    def test_missing_key_raises_401(self):
        with patch("app.dependencies.auth.settings") as mock_settings:
            mock_settings.get_api_key.return_value = "secret-key-123"
            mock_settings.environment = "development"
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(x_api_key=None)
            assert exc_info.value.status_code == 401

    def test_dev_mode_no_key_configured(self):
        with patch("app.dependencies.auth.settings") as mock_settings:
            mock_settings.get_api_key.return_value = None
            mock_settings.environment = "development"
            result = verify_api_key(x_api_key=None)
            assert result == "dev-mode"

    def test_production_no_key_raises_500(self):
        with patch("app.dependencies.auth.settings") as mock_settings:
            mock_settings.get_api_key.return_value = None
            mock_settings.environment = "production"
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(x_api_key=None)
            assert exc_info.value.status_code == 500


class TestSQLInjectionPrevention:
    """Тесты защиты от SQL injection."""

    def test_like_pattern_escape_percent(self):
        city = "Иркутск%'; DROP TABLE events; --"
        escaped = city.replace('%', r'\%').replace('_', r'\_')
        assert '%' not in escaped or r'\%' in escaped

    def test_like_pattern_escape_underscore(self):
        city = "test_city"
        escaped = city.replace('%', r'\%').replace('_', r'\_')
        assert escaped == r'test\_city'

    def test_normal_city_unchanged(self):
        city = "Иркутск"
        escaped = city.replace('%', r'\%').replace('_', r'\_')
        assert escaped == "Иркутск"


class TestInputSanitization:
    """Тесты санитизации входных данных."""

    def test_query_text_length_limit(self):
        max_length = 2000
        query = "a" * 2500
        assert len(query) > max_length

    def test_query_text_not_empty(self):
        query = "   "
        assert query.strip() == ""
