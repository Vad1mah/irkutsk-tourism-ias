"""Take full-page screenshots of all B2B-app pages via Playwright."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots")
OUT.mkdir(exist_ok=True)

PAGES = [
    ("home", "/", "Командный центр"),
    ("analytics", "/analytics", "Аналитика рынка"),
    ("forecast", "/forecast", "Прогноз спроса"),
    ("events", "/events", "События и спрос"),
    ("map", "/map", "Региональная карта"),
    ("about", "/about", "О системе"),
    ("chat", "/chat", "AI-агент (по прямой ссылке)"),
    ("hotel_detail", "/hotels/baikalska_zemlya_101hotels", "Карточка объекта"),
]

def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page = context.new_page()
        results = []
        for slug, path, title in PAGES:
            url = f"http://localhost:5173{path}"
            print(f"[{slug}] {title} -> {url}", flush=True)
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2500)
                screenshot_path = OUT / f"{slug}.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                results.append((slug, "OK", str(screenshot_path), page.title()))
            except Exception as e:
                results.append((slug, f"FAIL: {type(e).__name__}: {e}", "", ""))
                print(f"  ERROR: {e}", flush=True)
        browser.close()

        print("")
        print("=== SUMMARY ===")
        for slug, status, fp, ttl in results:
            print(f"  {slug}: {status} | title={ttl}")
        bad = [r for r in results if r[1] != "OK"]
        return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main())
