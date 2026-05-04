"""Re-take screenshots after UI fixes (Home, Analytics, Map, HotelDetail, Events)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots")

PAGES = [
    ("home_v3", "/", "Home (KPI)"),
    ("analytics_v3", "/analytics", "Analytics (RMS-таблица)"),
    ("map_v3", "/map", "Map (заголовок)"),
    ("hotel_detail_v3", "/hotels/220_101hotels", "HotelDetail (динамика цен)"),
    ("events_v3", "/events", "Events (фильтр региона)"),
]

def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page = context.new_page()
        for slug, path, title in PAGES:
            url = f"http://localhost:5173{path}"
            print(f"[{slug}] {title} -> {url}", flush=True)
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(OUT / f"{slug}.png"), full_page=True)
        browser.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
