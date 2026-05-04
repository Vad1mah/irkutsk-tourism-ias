"""Быстрый ре-снимок ключевых страниц после правок."""
from __future__ import annotations
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path("C:/Users/Admin/Desktop/Diplom/.screenshots/audit")
BASE = "http://localhost:5173"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="ru-RU")
    page = ctx.new_page()

    pages = [
        ("home_v2", "/"),
        ("forecast_v2", "/forecast"),
        ("map_v2", "/map"),
    ]
    for name, path in pages:
        page.goto(BASE + path, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        print(f"saved: {name}.png")

    browser.close()
