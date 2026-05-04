"""Тест AI-чата: отправка сообщения и проверка ответа в UI."""
from __future__ import annotations
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots/audit")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="ru-RU")
    page = ctx.new_page()

    console_log: list[str] = []
    network_calls: list[str] = []
    page.on("console", lambda m: console_log.append(f"{m.type}: {m.text[:200]}"))
    page.on("request", lambda r: network_calls.append(f"{r.method} {r.url[:120]}") if "/api/" in r.url else None)

    page.goto("http://localhost:5173/chat", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)

    page.screenshot(path=str(OUT / "chat_before.png"), full_page=False)

    inp = page.locator("textarea, input[type='text']").first
    inp.click()
    inp.fill("Динамика спроса на Ольхоне")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "chat_typed.png"), full_page=False)

    submit = None
    for sel in [
        "button[type='submit']",
        "button[aria-label*='отправ' i]",
        "form button:not([disabled])",
    ]:
        loc = page.locator(sel).first
        if loc.count() > 0:
            submit = loc
            print(f"submit selector: {sel}")
            break

    if submit:
        submit.click()
    else:
        inp.press("Enter")
        print("submit by Enter")

    page.wait_for_timeout(5000)
    page.screenshot(path=str(OUT / "chat_sent_5s.png"), full_page=True)
    page.wait_for_timeout(25000)
    page.screenshot(path=str(OUT / "chat_sent_30s.png"), full_page=True)
    page.wait_for_timeout(30000)
    page.screenshot(path=str(OUT / "chat_sent_60s.png"), full_page=True)
    page.wait_for_timeout(30000)
    page.screenshot(path=str(OUT / "chat_sent_90s.png"), full_page=True)

    print("\n=== API calls ===")
    for c in network_calls[-30:]:
        print(" ", c)

    errors = [c for c in console_log if c.startswith("error")]
    print(f"\n=== console errors: {len(errors)} ===")
    for e in errors[:10]:
        print(" ", e)

    chat_text = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('main *, [class*=chat] *, [class*=message] *'))
            .map(el => Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).filter(Boolean).join(' '))
            .filter(s=>s.length>0).slice(-30).join('\\n');
    }""")
    print("\n=== last text on page ===")
    print(chat_text[-2000:])

    browser.close()
