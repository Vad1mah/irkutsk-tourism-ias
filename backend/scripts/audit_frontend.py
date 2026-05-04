"""Полный аудит фронтенда: проход по всем страницам с скриншотами и
сбором проблем (английский в UI, низкий контраст, нерабочие кнопки,
ошибки в консоли).

Запуск:
    & "C:/Users/Admin/Desktop/Diplom/backend/venv/Scripts/python.exe" \\
      C:/Users/Admin/Desktop/Diplom/backend/scripts/audit_frontend.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, ConsoleMessage

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = Path("C:/Users/Admin/Desktop/Diplom/.screenshots/audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = OUT_DIR / "report.json"

BASE = "http://localhost:5173"
ROUTES = [
    ("home",          "/",                 "Главная (B2B-командный центр)"),
    ("analytics",     "/analytics",        "Аналитика рынка"),
    ("forecast",      "/forecast",         "Прогноз спроса"),
    ("events",        "/events",           "События и спрос"),
    ("map",           "/map",              "Региональная карта"),
    ("about",         "/about",            "О системе"),
    ("hotel-detail",  "/hotels/220_101hotels", "Карточка объекта (отель «Ангара»)"),
    ("chat",          "/chat",             "AI-чат"),
]

VIEWPORT = {"width": 1600, "height": 1000}

ENGLISH_FRAGMENTS = [
    "Occupancy", "Average Daily", "Daily Rate",
    "Pickup", "Pace", "Revenue", "Forecast",
]


def collect_text_fragments(page: Page) -> list[dict]:
    """Достаёт видимый текст с тегами (без атрибутов) для проверки на язык."""
    return page.evaluate("""() => {
        const all = document.querySelectorAll('body *');
        const out = [];
        for (const el of all) {
            const tag = el.tagName.toLowerCase();
            if (['script', 'style', 'noscript', 'svg', 'path'].includes(tag)) continue;
            // только листовые элементы с прямым текстом
            const direct = Array.from(el.childNodes)
                .filter(n => n.nodeType === 3)
                .map(n => n.textContent.trim())
                .filter(s => s.length > 0)
                .join(' ');
            if (direct) {
                out.push({ tag, text: direct.slice(0, 200) });
            }
        }
        return out;
    }""")


def find_english_in_page(fragments: list[dict]) -> list[dict]:
    found = []
    for f in fragments:
        for marker in ENGLISH_FRAGMENTS:
            if marker in f["text"]:
                found.append({**f, "marker": marker})
                break
    return found


def check_low_contrast(page: Page) -> list[dict]:
    """Поиск элементов с низким контрастом текст/фон."""
    return page.evaluate("""() => {
        function hexToRgb(hex) {
            const m = hex.match(/^#([0-9a-f]{3,8})$/i);
            return null;
        }
        function parseColor(c) {
            const m = c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d\\.]+))?\\)/);
            if (!m) return null;
            return { r: +m[1], g: +m[2], b: +m[3], a: m[4] !== undefined ? +m[4] : 1 };
        }
        function relLum({r,g,b}) {
            const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
            return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b);
        }
        function effectiveBg(el) {
            let cur = el;
            while (cur && cur !== document.body) {
                const c = parseColor(getComputedStyle(cur).backgroundColor);
                if (c && c.a > 0.5) return c;
                cur = cur.parentElement;
            }
            const bodyBg = parseColor(getComputedStyle(document.body).backgroundColor);
            return bodyBg || { r: 0, g: 0, b: 0, a: 1 };
        }
        const out = [];
        const seen = new Set();
        for (const el of document.querySelectorAll('body *')) {
            if (['SCRIPT','STYLE','NOSCRIPT','SVG','PATH'].includes(el.tagName)) continue;
            const direct = Array.from(el.childNodes)
                .filter(n => n.nodeType === 3 && n.textContent.trim().length > 1)
                .map(n => n.textContent.trim()).join(' ');
            if (!direct) continue;
            const cs = getComputedStyle(el);
            const fg = parseColor(cs.color);
            if (!fg) continue;
            const bg = effectiveBg(el);
            const L1 = relLum(fg);
            const L2 = relLum(bg);
            const ratio = (Math.max(L1,L2) + 0.05) / (Math.min(L1,L2) + 0.05);
            if (ratio < 4.5) {
                const key = direct.slice(0,80);
                if (seen.has(key)) continue;
                seen.add(key);
                const rect = el.getBoundingClientRect();
                if (rect.width < 4 || rect.height < 4) continue;
                out.push({
                    text: direct.slice(0, 120),
                    ratio: +ratio.toFixed(2),
                    fg: cs.color,
                    bg: `rgb(${bg.r},${bg.g},${bg.b})`,
                    fontSize: cs.fontSize,
                });
            }
        }
        return out.slice(0, 50);
    }""")


def find_dev_comments(fragments: list[dict]) -> list[dict]:
    """Маркеры комментариев разработчика, проникших в UI."""
    markers = [
        "замечание комиссии", "TODO", "FIXME", "WIP",
        "субагент", "TEMP", "PLACEHOLDER",
    ]
    out = []
    for f in fragments:
        low = f["text"].lower()
        for m in markers:
            if m.lower() in low:
                out.append({**f, "dev_marker": m})
                break
    return out


def collect_buttons(page: Page) -> list[dict]:
    """Кнопки с пустым/непонятным текстом и без aria-label."""
    return page.evaluate("""() => {
        const out = [];
        for (const btn of document.querySelectorAll('button')) {
            const visText = (btn.innerText || '').trim();
            const aria = btn.getAttribute('aria-label') || '';
            const title = btn.getAttribute('title') || '';
            const disabled = btn.disabled;
            const rect = btn.getBoundingClientRect();
            if (rect.width < 4 || rect.height < 4) continue;
            out.push({
                text: visText.slice(0, 60),
                aria: aria.slice(0, 60),
                title: title.slice(0, 60),
                disabled,
                size: `${Math.round(rect.width)}x${Math.round(rect.height)}`,
            });
        }
        return out;
    }""")


def audit_route(page: Page, slug: str, path: str, title: str, errors_log: list[dict]) -> dict:
    print(f"\n[{slug}] {path} — {title}")

    console_errors: list[dict] = []
    page_errors: list[str] = []

    def on_console(msg: ConsoleMessage):
        if msg.type in ("error", "warning"):
            console_errors.append({
                "type": msg.type,
                "text": msg.text[:300],
                "location": getattr(msg, "location", {}) or {},
            })

    def on_pageerror(err):
        page_errors.append(str(err)[:300])

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)

    response = page.goto(BASE + path, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    page.wait_for_timeout(1500)

    fragments = collect_text_fragments(page)
    english = find_english_in_page(fragments)
    dev_comments = find_dev_comments(fragments)
    contrast = check_low_contrast(page)
    buttons = collect_buttons(page)

    full_path = OUT_DIR / f"{slug}_full.png"
    page.screenshot(path=str(full_path), full_page=True)

    visible_path = OUT_DIR / f"{slug}_viewport.png"
    page.screenshot(path=str(visible_path), full_page=False)

    print(f"  status: {response.status if response else 'no response'}")
    print(f"  text fragments: {len(fragments)}")
    print(f"  english markers: {len(english)}")
    print(f"  dev comments: {len(dev_comments)}")
    print(f"  low contrast (<4.5): {len(contrast)}")
    print(f"  buttons: {len(buttons)}")
    print(f"  console errors: {len(console_errors)}, page errors: {len(page_errors)}")

    page.remove_listener("console", on_console)
    page.remove_listener("pageerror", on_pageerror)

    return {
        "slug": slug,
        "path": path,
        "title": title,
        "status": response.status if response else None,
        "text_fragments_count": len(fragments),
        "english_markers": english[:30],
        "dev_comments": dev_comments,
        "low_contrast": contrast[:25],
        "buttons": buttons[:40],
        "console_errors": console_errors[:20],
        "page_errors": page_errors,
        "screenshots": {
            "full": str(full_path),
            "viewport": str(visible_path),
        },
    }


def main() -> None:
    started = datetime.now()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, locale="ru-RU")
        page = ctx.new_page()

        report = {
            "started_at": started.isoformat(),
            "viewport": VIEWPORT,
            "base": BASE,
            "routes": [],
        }

        for slug, path, title in ROUTES:
            try:
                r = audit_route(page, slug, path, title, report.get("routes", []))
            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}")
                r = {
                    "slug": slug,
                    "path": path,
                    "title": title,
                    "error": f"{type(e).__name__}: {e}",
                }
            report["routes"].append(r)

        browser.close()

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")
    print(f"Screenshots: {OUT_DIR}")


if __name__ == "__main__":
    main()
