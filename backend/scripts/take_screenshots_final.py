"""Final round of screenshots — verify all UI fixes."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots")

PAGES = [
    ("home_final", "/", "Home (B2B-командный центр)"),
    ("analytics_final", "/analytics", "Analytics (RMS-таблица + heatmap)"),
    ("forecast_final", "/forecast", "Forecast (ансамбль)"),
    ("events_final", "/events", "Events (фильтр по региону)"),
    ("map_final", "/map", "Map (Региональная карта)"),
    ("about_final", "/about", "About (B2B-сценарии)"),
    ("chat_final", "/chat", "AI-агент"),
    ("hotel_final", "/hotels/220_101hotels", "HotelDetail (Ангара)"),
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
