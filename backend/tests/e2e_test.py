#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E тесты для API.

Запуск:
    cd backend
    python tests/e2e_test.py
"""
import asyncio
import httpx
import os
import sys
import io

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OK = "[OK]"
FAIL = "[FAIL]"

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")

async def run_e2e_tests():
    """Запуск всех E2E тестов."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = []

        # Test 1: Health
        print("\n1. Health Check")
        try:
            resp = await client.get(f"{BASE_URL}/health")
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   DB: {data.get('db_backend')}, Connected: {data.get('db_connected')}")
            results.append(("Health", ok))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Health", False))

        # Test 2: KPI Analytics
        print("\n2. KPI Analytics")
        try:
            resp = await client.get(f"{BASE_URL}/api/analytics/kpi")
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            print(f"   Status: {OK if ok else FAIL}")
            if ok:
                print(f"   Hotels: {data.get('total_hotels')}, Events: {data.get('total_events')}")
                print(f"   Occupancy: {data.get('avg_occupancy')}%")
            results.append(("KPI", ok))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("KPI", False))

        # Test 3: Hotels API
        print("\n3. Hotels API")
        try:
            resp = await client.get(f"{BASE_URL}/api/hotels?limit=5")
            ok = resp.status_code == 200
            data = resp.json() if ok else []
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Hotels returned: {len(data)}")
            results.append(("Hotels", ok))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Hotels", False))

        # Test 4: Events API
        print("\n4. Events API")
        try:
            resp = await client.get(f"{BASE_URL}/api/events?limit=5")
            ok = resp.status_code == 200
            data = resp.json() if ok else []
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Events returned: {len(data)}")
            results.append(("Events", ok))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Events", False))

        # Test 5: Prophet Forecast
        print("\n5. Prophet Forecast")
        try:
            resp = await client.post(
                f"{BASE_URL}/api/forecast",
                json={"district": "Иркутский", "days_ahead": 7}
            )
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            forecasts = data.get("forecast", [])
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Forecast points: {len(forecasts)}")
            if forecasts:
                print(f"   First: {forecasts[0].get('date')} - {forecasts[0].get('occupancy')}%")
            results.append(("Prophet Forecast", ok and len(forecasts) > 0))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Prophet Forecast", False))

        # Test 6: Ensemble Forecast
        print("\n6. Ensemble Forecast")
        try:
            resp = await client.get(
                f"{BASE_URL}/api/forecast/ensemble",
                params={"district": "Иркутский", "days_ahead": 7}
            )
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            ensemble = data.get("ensemble", [])
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Ensemble points: {len(ensemble)}")
            print(f"   Weights: {data.get('weights')}")
            results.append(("Ensemble Forecast", ok and len(ensemble) > 0))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Ensemble Forecast", False))

        # Test 7: Weather Forecast
        print("\n7. Weather Forecast")
        try:
            resp = await client.get(f"{BASE_URL}/api/forecast/weather?days=3")
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            forecasts = data.get("forecasts", [])
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Weather days: {len(forecasts)}")
            results.append(("Weather", ok))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Weather", False))

        # Test 8: AI Query
        print("\n8. AI Query (get_statistics)")
        try:
            resp = await client.post(
                f"{BASE_URL}/api/query",
                json={"text": "How many hotels in database?"}
            )
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Answer length: {len(answer)} chars")
            print(f"   Tools used: {sources}")
            results.append(("AI Query", ok and len(answer) > 0))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("AI Query", False))

        # Test 9: Scheduler Status
        print("\n9. Scheduler Status")
        try:
            resp = await client.get(
                f"{BASE_URL}/api/parser/scheduler/status",
                headers={"X-API-Key": API_KEY},
            )
            ok = resp.status_code == 200
            data = resp.json() if ok else {}
            jobs = data.get("jobs", [])
            print(f"   Status: {OK if ok else FAIL}")
            print(f"   Jobs: {len(jobs)}")
            results.append(("Scheduler", ok))
        except Exception as e:
            print(f"   {FAIL} Error: {e}")
            results.append(("Scheduler", False))

        # Summary
        print("\n" + "=" * 50)
        passed = sum(1 for _, ok in results if ok)
        total = len(results)
        print(f"RESULTS: {passed}/{total} tests passed")
        print("=" * 50)

        for name, ok in results:
            print(f"  {OK if ok else FAIL} {name}")

        return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_e2e_tests())
    sys.exit(0 if success else 1)
