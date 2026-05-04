"""Re-take Chat, About, HotelDetail screenshots after fixes."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots")

PAGES = [
    ("chat_v2", "/chat", "AI-агент"),
    ("about_v2", "/about", "О системе"),
    ("hotel_detail_v2", "/hotels/220_101hotels", "Карточка объекта (Ангара)"),
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
            page.wait_for_timeout(3000)
            page.screenshot(path=str(OUT / f"{slug}.png"), full_page=True)
            print(f"  saved -> {OUT / (slug + '.png')}", flush=True)
        browser.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
