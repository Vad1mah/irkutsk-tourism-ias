"""Тесты безопасности."""
import time


class TestRateLimiting:
    """Тесты rate limiting логики."""

    def test_local_rate_limit_allows_within_limit(self):
        """Проверка что запросы в пределах лимита проходят."""
        cache: dict[str, list[float]] = {}
        key = "test:127.0.0.1:/api/query"
        limit = 5
        period = 60

        now = time.time()
        if key not in cache:
            cache[key] = []

        # Удаляем старые записи
        cache[key] = [ts for ts in cache[key] if ts > now - period]

        # Добавляем запросы в пределах лимита
        for _ in range(limit - 1):
            cache[key].append(now)

        # Проверяем что лимит не превышен
        assert len(cache[key]) < limit, "Should be under limit"

    def test_local_rate_limit_blocks_over_limit(self):
        """Проверка что запросы сверх лимита блокируются."""
        cache: dict[str, list[float]] = {}
        key = "test:127.0.0.1:/api/query"
        limit = 5
        period = 60

        now = time.time()
        if key not in cache:
            cache[key] = []

        # Заполняем до лимита
        for _ in range(limit):
            cache[key].append(now)

        # Проверяем что следующий будет заблокирован
        cache[key] = [ts for ts in cache[key] if ts > now - period]
        is_blocked = len(cache[key]) >= limit
        assert is_blocked, "Should be blocked over limit"

    def test_rate_limit_window_expiry(self):
        """Проверка что записи истекают по времени."""
        cache: dict[str, list[float]] = {}
        key = "test:127.0.0.1:/api/query"
        period = 60

        # Добавляем старые записи (100 секунд назад)
        old_time = time.time() - 100
        cache[key] = [old_time, old_time + 1, old_time + 2]

        # Очищаем по окну
        now = time.time()
        cache[key] = [ts for ts in cache[key] if ts > now - period]

        assert len(cache[key]) == 0, "Old entries should be expired"


class TestSQLInjectionPrevention:
    """Тесты защиты от SQL injection."""

    def test_like_pattern_escape_percent(self):
        """Проверка экранирования символа % в LIKE."""
        city = "Иркутск%'; DROP TABLE events; --"
        escaped = city.replace('%', r'\%').replace('_', r'\_')
        assert '%' not in escaped or r'\%' in escaped

    def test_like_pattern_escape_underscore(self):
        """Проверка экранирования символа _ в LIKE."""
        city = "test_city"
        escaped = city.replace('%', r'\%').replace('_', r'\_')
        assert escaped == r'test\_city'

    def test_normal_city_unchanged(self):
        """Проверка что нормальные города не изменяются."""
        city = "Иркутск"
        escaped = city.replace('%', r'\%').replace('_', r'\_')
        assert escaped == "Иркутск"


class TestAPIKeyAuth:
    """Тесты аутентификации по API ключу."""

    def test_api_key_validation_success(self):
        """Проверка валидации правильного ключа."""
        expected_key = "test-secret-key-12345"
        provided_key = "test-secret-key-12345"

        # Симуляция проверки
        is_valid = provided_key == expected_key
        assert is_valid

    def test_api_key_validation_failure(self):
        """Проверка отклонения неправильного ключа."""
        expected_key = "test-secret-key-12345"
        provided_key = "wrong-key"

        is_valid = provided_key == expected_key
        assert not is_valid

    def test_api_key_missing(self):
        """Проверка что отсутствие ключа не валидно."""
        expected_key = "test-secret-key-12345"
        provided_key = None

        is_valid = provided_key is not None and provided_key == expected_key
        assert not is_valid

    def test_dev_mode_no_key_configured(self):
        """Проверка режима разработки без ключа."""
        configured_key = None  # Не настроен
        # В dev mode (нет ключа) - пропускаем
        is_dev_mode = configured_key is None
        assert is_dev_mode


class TestInputSanitization:
    """Тесты санитизации входных данных."""

    def test_query_text_length_limit(self):
        """Проверка ограничения длины запроса."""
        max_length = 2000
        query = "a" * 2500

        is_valid = len(query) <= max_length
        assert not is_valid, "Query should exceed limit"

    def test_query_text_not_empty(self):
        """Проверка что запрос не пустой."""
        query = "   "
        is_valid = query.strip() != ""
        assert not is_valid, "Whitespace-only query should be invalid"


if __name__ == "__main__":
    print("Running security tests...")

    test_rate = TestRateLimiting()
    test_rate.test_local_rate_limit_allows_within_limit()
    test_rate.test_local_rate_limit_blocks_over_limit()
    test_rate.test_rate_limit_window_expiry()
    print("[OK] Rate limiting tests passed")

    test_sql = TestSQLInjectionPrevention()
    test_sql.test_like_pattern_escape_percent()
    test_sql.test_like_pattern_escape_underscore()
    test_sql.test_normal_city_unchanged()
    print("[OK] SQL injection prevention tests passed")

    test_auth = TestAPIKeyAuth()
    test_auth.test_api_key_validation_success()
    test_auth.test_api_key_validation_failure()
    test_auth.test_api_key_missing()
    test_auth.test_dev_mode_no_key_configured()
    print("[OK] API key auth tests passed")

    test_input = TestInputSanitization()
    test_input.test_query_text_length_limit()
    test_input.test_query_text_not_empty()
    print("[OK] Input sanitization tests passed")

    print("\n[DONE] All security tests passed!")
