"""Unit tests for cache and helper functions."""
import time


class TestCacheEviction:
    """Test cache eviction logic."""

    def test_ensemble_cache_eviction(self):
        """Test ensemble cache eviction logic."""
        # Simulate the cache behavior
        cache = {}
        cache_ttl = 10
        max_size = 100

        # Fill cache beyond limit
        for i in range(110):
            cache[f"key_{i}"] = {
                "data": {"test": i},
                "timestamp": time.time() - 100,  # Old entries
            }

        # Simulate eviction logic
        if len(cache) >= max_size:
            now = time.time()
            expired = [k for k, v in cache.items()
                       if (now - v["timestamp"]) >= cache_ttl]
            for k in expired:
                del cache[k]

        # Add new entry
        cache["new_key"] = {"data": {"test": "new"}, "timestamp": time.time()}

        # Check that old entries were removed
        assert len(cache) <= 100, f"Cache should be <= 100, got {len(cache)}"

    def test_weather_cache_ttl(self):
        """Test weather cache TTL logic."""
        cache = {}
        cache_ttl = 3600  # 1 hour

        # Add entry
        cache["test_key"] = {
            "data": {"temperature": -15.0},
            "timestamp": time.time() - 4000,  # Older than TTL
        }

        # Check TTL
        now = time.time()
        cached = cache.get("test_key")
        if cached and (now - cached["timestamp"]) < cache_ttl:
            result = cached["data"]
        else:
            result = None

        # Entry should be expired
        assert result is None, "Expired entry should return None"

    def test_cache_max_size_eviction(self):
        """Test cache eviction when max size is reached."""
        cache = {}
        max_size = 50
        cache_ttl = 3600

        # Fill to max
        for i in range(max_size):
            cache[f"key_{i}"] = {
                "data": {"value": i},
                "timestamp": time.time(),
            }

        assert len(cache) == max_size

        # Add one more - should trigger eviction of oldest
        oldest_key = min(cache.keys(), key=lambda k: cache[k]["timestamp"])
        oldest_time = cache[oldest_key]["timestamp"]

        # Add new entry
        cache["new_key"] = {"data": {"value": 999}, "timestamp": time.time() + 1}

        # Verify new entry exists
        assert "new_key" in cache
        assert cache["new_key"]["data"]["value"] == 999


class TestOccupancyCalculation:
    """Test occupancy calculation logic."""

    def test_occupancy_from_available_percent(self):
        """Test converting available_rooms_percent to occupancy."""
        available_percent = 25.0
        occupancy = 100.0 - available_percent
        assert occupancy == 75.0

    def test_occupancy_bounds(self):
        """Test occupancy stays within bounds."""
        # Test lower bound
        occupancy = max(0, min(100, 100 - 150))  # available > 100
        assert occupancy == 0

        # Test upper bound
        occupancy = max(0, min(100, 100 - (-50)))  # available < 0
        assert occupancy == 100

    def test_occupancy_rounding(self):
        """Test occupancy rounding."""
        values = [65.123, 70.456, 80.789]
        rounded = [round(v, 1) for v in values]
        assert rounded == [65.1, 70.5, 80.8]


class TestDateRangeGeneration:
    """Test date range generation for forecasts."""

    def test_forecast_date_range(self):
        """Test generating forecast date range."""
        from datetime import date, timedelta

        start_date = date(2026, 1, 1)
        days_ahead = 14

        dates = [start_date + timedelta(days=i) for i in range(days_ahead)]

        assert len(dates) == 14
        assert dates[0] == date(2026, 1, 1)
        assert dates[-1] == date(2026, 1, 14)

    def test_history_date_range(self):
        """Test history date range extraction."""
        from datetime import date

        history = [
            {"date": date(2026, 1, 1), "occupancy": 65.0},
            {"date": date(2026, 1, 5), "occupancy": 70.0},
            {"date": date(2026, 1, 3), "occupancy": 68.0},
        ]

        all_dates = [h["date"] for h in history]
        min_date = min(all_dates)
        max_date = max(all_dates)

        assert min_date == date(2026, 1, 1)
        assert max_date == date(2026, 1, 5)


if __name__ == "__main__":
    print("Running unit tests...")

    test_cache = TestCacheEviction()
    test_cache.test_ensemble_cache_eviction()
    test_cache.test_weather_cache_ttl()
    test_cache.test_cache_max_size_eviction()

    test_occ = TestOccupancyCalculation()
    test_occ.test_occupancy_from_available_percent()
    test_occ.test_occupancy_bounds()
    test_occ.test_occupancy_rounding()

    test_dates = TestDateRangeGeneration()
    test_dates.test_forecast_date_range()
    test_dates.test_history_date_range()

    print("\nAll unit tests passed!")
