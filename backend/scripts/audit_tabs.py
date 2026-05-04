"""Расширенный аудит: проход по табам и состояниям внутри страниц."""
from __future__ import annotations
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots/audit")
BASE = "http://localhost:5173"
VIEWPORT = {"width": 1600, "height": 1000}


SCENARIOS = [
    # (slug, path, [список табов или click-actions])
    ("forecast", "/forecast", ["Прогноз", "Модели", "Сезонность"]),
    ("map",      "/map",      ["Карта отелей", "Обзор районов", "Сезонная карта", "Сравнение"]),
]


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport=VIEWPORT, locale="ru-RU")
    page = ctx.new_page()

    for slug, path, tabs in SCENARIOS:
        page.goto(BASE + path, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2500)
        for tab in tabs:
            try:
                btn = page.locator("button", has_text=tab).first
                if btn.count() > 0:
                    btn.click()
                    page.wait_for_timeout(2500)
                    safe = tab.replace(" ", "_")
                    fname = OUT / f"{slug}__{safe}.png"
                    page.screenshot(path=str(fname), full_page=True)
                    print(f"  saved: {fname}")
                else:
                    print(f"  NOT FOUND: {tab}")
            except Exception as e:
                print(f"  ERR {tab}: {e}")

    # Также пройдёмся по Events с фильтром по району
    page.goto(BASE + "/events", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2500)
    page.screenshot(path=str(OUT / "events_all.png"), full_page=True)

    # И HotelDetail full scroll
    page.goto(BASE + "/hotels/220_101hotels", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2500)
    page.screenshot(path=str(OUT / "hotel-detail_full2.png"), full_page=True)

    # About
    page.goto(BASE + "/about", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT / "about_full2.png"), full_page=True)

    browser.close()

print("done")
