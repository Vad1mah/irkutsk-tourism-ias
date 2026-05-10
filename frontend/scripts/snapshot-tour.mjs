// Полный тур по UI приложения — Playwright Chromium.
// Снимает ~34 скриншота по всем страницам и под-режимам.
// Usage: cd frontend && node scripts/snapshot-tour.mjs
//
// Каждый шаг обёрнут в try/catch — один битый шаг не валит весь тур.
import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'
import path from 'path'

const BASE = process.env.SCREENSHOT_BASE || 'http://localhost:5173'
const API = process.env.API_BASE || 'http://localhost:8000'
const OUT = path.resolve('..', 'docs', 'screenshots', '2026-05-11', 'ui')
const HOTEL_ID = process.env.HOTEL_ID || '607_101hotels'
const VIEWPORT = { width: 1440, height: 900 }
const DPR = 2

await mkdir(OUT, { recursive: true })

console.log(`[i] base=${BASE}  out=${OUT}`)
console.log(`[i] viewport=${VIEWPORT.width}x${VIEWPORT.height}@${DPR}x  hotel_id=${HOTEL_ID}`)

const browser = await chromium.launch({ headless: true })

async function makeContext() {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: DPR,
    locale: 'ru-RU',
  })
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('pribaikalie_theme', 'dark')
      const r = document.documentElement
      r.classList.remove('light')
      r.classList.add('dark')
    } catch {}
  })
  return ctx
}

async function settle(page, extraMs = 1500) {
  await page.waitForLoadState('domcontentloaded').catch(() => {})
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {})
  await page.waitForTimeout(extraMs)
}

async function snap(page, name, opts = {}) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, ...opts })
  console.log(`[+] ${name}`)
}

async function snapElement(page, selector, name) {
  try {
    const el = await page.locator(selector).first()
    const file = path.join(OUT, name)
    await el.screenshot({ path: file })
    console.log(`[+] ${name} (${selector})`)
  } catch (e) {
    console.log(`[!] snapElement skipped ${name}: ${e.message}`)
  }
}

async function safeClick(page, locator, label) {
  try {
    await locator.click({ timeout: 5000 })
    console.log(`[~] clicked: ${label}`)
    return true
  } catch (e) {
    console.log(`[!] click skipped (${label}): ${e.message}`)
    return false
  }
}

async function withPage(fn) {
  const ctx = await makeContext()
  const page = await ctx.newPage()
  page.on('pageerror', err => console.log(`[pageerror] ${err.message}`))
  try {
    await fn(page)
  } catch (e) {
    console.log(`[!!] context-level error: ${e.message}`)
  } finally {
    await ctx.close()
  }
}

// ───────────────────────────────────────────────────────────────────────────
//   00 + 01 — Layout sidebar + Home
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/`)
  await settle(page, 3000)
  await snapElement(page, 'aside', '00_layout_sidebar.png')
  await snap(page, '01_home.png', { fullPage: true })
})

// ───────────────────────────────────────────────────────────────────────────
//   02 — Chat (пустой + 3 SSE-ответа)
// ───────────────────────────────────────────────────────────────────────────
const CHAT_PROMPTS = [
  { name: '02_chat_response_revpar.png',
    q: 'Сравни RevPAR Иркутского и Ольхонского районов за последние 30 дней' },
  { name: '02_chat_response_events_impact.png',
    q: 'Топ-5 событий по влиянию на загрузку в Иркутском районе' },
  { name: '02_chat_response_forecast.png',
    q: 'Прогноз загрузки Ольхонского района на 14 дней' },
]

await withPage(async page => {
  await page.goto(`${BASE}/chat`)
  await settle(page, 2000)
  await snap(page, '02_chat_empty.png', { fullPage: false })
})

for (const { name, q } of CHAT_PROMPTS) {
  await withPage(async page => {
    await page.goto(`${BASE}/chat`)
    await settle(page, 1500)

    const input = page.locator('input[type="text"], textarea').first()
    await input.click()
    await input.fill(q)
    await page.keyboard.press('Enter')

    console.log(`[i] ${name}: waiting for SSE response (up to 120s)...`)
    try {
      await page.waitForFunction(() => {
        const text = document.body.innerText
        // ждём assistant-сообщение длиной 200+ символов БЕЗ "Думаю..." индикатора
        const hasAnswer = text.length > 1500 && /район|загрузк|занят|событ|прогноз|RevPAR|ADR|номер/i.test(text)
        const stillStreaming = /Думаю\.\.\.|Анализирую\.\.\.|Печатаю\.\.\./.test(text)
        return hasAnswer && !stillStreaming
      }, { timeout: 120_000 })
      await page.waitForTimeout(2500) // дожать последние chunks
    } catch (e) {
      console.log(`[!] SSE wait timeout for ${name}, capturing whatever is on screen`)
    }

    // Скролл вниз чтобы было видно последнее сообщение
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.waitForTimeout(500)
    await snap(page, name, { fullPage: true })
  })
}

// ───────────────────────────────────────────────────────────────────────────
//   03 — Analytics (4 таба + drill-down)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/analytics?district=Иркутский`)
  await settle(page, 3500)
  await snap(page, '03_analytics_regions.png', { fullPage: true })

  // Drill-down: клик на первую строку RMS-таблицы
  try {
    await page.locator('table tbody tr').first().click({ timeout: 5000 })
    await page.waitForTimeout(2000)
    await snap(page, '03_analytics_regions_drilldown.png', { fullPage: true })
  } catch (e) {
    console.log(`[!] drilldown skipped: ${e.message}`)
  }
})

const ANALYTICS_TABS = [
  { btn: /сезонност/i, file: '03_analytics_seasonality.png' },
  { btn: /событ/i,     file: '03_analytics_events.png' },
  { btn: /сегмент/i,   file: '03_analytics_segments.png' },
]
for (const { btn, file } of ANALYTICS_TABS) {
  await withPage(async page => {
    await page.goto(`${BASE}/analytics?district=Иркутский`)
    await settle(page, 2500)
    const ok = await safeClick(page, page.getByRole('button', { name: btn }).first(), `tab ${btn}`)
    if (ok) await page.waitForTimeout(3000)
    await snap(page, file, { fullPage: true })
  })
}

// ───────────────────────────────────────────────────────────────────────────
//   04 — Events (календарь + фильтр + impact + modal)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/events`)
  await settle(page, 3000)
  await snap(page, '04_events_calendar.png', { fullPage: true })

  // Клик на первый badge-фильтр (тип)
  try {
    const badges = page.locator('button').filter({ hasText: /^(Концерт|Театр|Выставк|Фестивал|Спектакл)/ })
    const count = await badges.count()
    if (count > 0) {
      await badges.first().click({ timeout: 3000 })
      await page.waitForTimeout(1500)
      await snap(page, '04_events_filter_concert.png', { fullPage: true })
    } else {
      console.log('[!] no event-type badges found')
    }
  } catch (e) {
    console.log(`[!] events filter skipped: ${e.message}`)
  }
})

await withPage(async page => {
  await page.goto(`${BASE}/events`)
  await settle(page, 3000)
  // Скролл до графа impact (обычно ниже календаря)
  try {
    await page.evaluate(() => {
      const el = document.querySelector('[class*="impact"], [data-section="impact"]')
        || [...document.querySelectorAll('h2,h3')].find(h => /влиян|impact/i.test(h.innerText))
      if (el) el.scrollIntoView({ block: 'start' })
    })
    await page.waitForTimeout(2000)
  } catch {}
  await snap(page, '04_events_impact_chart.png', { fullPage: true })
})

await withPage(async page => {
  await page.goto(`${BASE}/events`)
  await settle(page, 3000)
  // Клик на первую карточку события (article или .card)
  try {
    const card = page.locator('article, [data-event-card], button:has-text("Подробнее")').first()
    await card.click({ timeout: 5000 })
    await page.waitForTimeout(1500)
    await snap(page, '04_events_modal.png', { fullPage: false })
  } catch (e) {
    console.log(`[!] event modal skipped: ${e.message}`)
  }
})

// ───────────────────────────────────────────────────────────────────────────
//   05 — Map (общая, лето, зима, маркер, пустая дата)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/map`)
  await settle(page, 6000) // Yandex tiles + KPI banner
  await page.waitForTimeout(3000)
  await snap(page, '05_map_all_seasons.png', { fullPage: false })
})

for (const [seasonName, file] of [['Лето', '05_map_summer.png'], ['Зима', '05_map_winter.png']]) {
  await withPage(async page => {
    await page.goto(`${BASE}/map`)
    await settle(page, 5000)
    const ok = await safeClick(page, page.getByRole('button', { name: new RegExp(seasonName, 'i') }).first(), `season ${seasonName}`)
    if (ok) await page.waitForTimeout(3500)
    await snap(page, file, { fullPage: false })
  })
}

await withPage(async page => {
  await page.goto(`${BASE}/map`)
  await settle(page, 6000)
  await page.waitForTimeout(2000)
  // Клик в центр карты — часто попадает на placemark кластер
  try {
    const mapBox = await page.locator('.ymaps-2-1-79-map, [class*="ymaps"]').first().boundingBox()
    if (mapBox) {
      await page.mouse.click(mapBox.x + mapBox.width / 2, mapBox.y + mapBox.height / 2)
      await page.waitForTimeout(1500)
    }
  } catch (e) {
    console.log(`[!] map click skipped: ${e.message}`)
  }
  await snap(page, '05_map_marker_pinned.png', { fullPage: false })
})

await withPage(async page => {
  await page.goto(`${BASE}/map?date=2000-01-01`)
  await settle(page, 5000)
  await snap(page, '05_map_empty_date_banner.png', { fullPage: false })
})

// ───────────────────────────────────────────────────────────────────────────
//   06 — Forecast (3 режима + compare + explain)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/forecast?district=Иркутский&days=14`)
  await settle(page, 4000)
  await snap(page, '06_forecast_simple_14d.png', { fullPage: true })
})

await withPage(async page => {
  await page.goto(`${BASE}/forecast?district=Иркутский&days=30`)
  await settle(page, 4000)
  await snap(page, '06_forecast_simple_30d.png', { fullPage: true })
})

await withPage(async page => {
  await page.goto(`${BASE}/forecast?district=Иркутский&days=14`)
  await settle(page, 4000)
  await safeClick(page, page.getByRole('button', { name: /^Модели$|expert/i }).first(), 'tab Модели')
  await page.waitForTimeout(3500)
  await snap(page, '06_forecast_expert_models.png', { fullPage: true })

  // Получить объяснение
  try {
    const btn = page.getByRole('button', { name: /получить объяснение|обновить/i })
    if (await btn.count()) {
      await btn.first().click({ timeout: 5000 })
      await page.waitForFunction(() => {
        const t = document.body.innerText
        return !/Анализ\.\.\./i.test(t) && /(тренд|сезонност|загрузк|RMSE|фактор)/i.test(t)
      }, { timeout: 60_000 }).catch(() => {})
      await page.waitForTimeout(2000)
      await snap(page, '06_forecast_expert_explain.png', { fullPage: true })
    }
  } catch (e) {
    console.log(`[!] explain skipped: ${e.message}`)
  }
})

await withPage(async page => {
  await page.goto(`${BASE}/forecast?district=Иркутский&days=14`)
  await settle(page, 3500)
  await safeClick(page, page.getByRole('button', { name: /сезонност/i }).first(), 'tab Сезонность')
  await page.waitForTimeout(3000)
  await snap(page, '06_forecast_seasonality.png', { fullPage: true })
})

await withPage(async page => {
  await page.goto(`${BASE}/forecast?district=Иркутский&days=14`)
  await settle(page, 3500)
  await safeClick(page, page.getByRole('button', { name: /сравнить район/i }).first(), 'tab Сравнить районы')
  await page.waitForTimeout(2000)
  // Попытаться выбрать ещё район
  try {
    const checkboxes = page.locator('input[type="checkbox"]')
    const n = await checkboxes.count()
    for (let i = 0; i < Math.min(n, 3); i++) {
      const cb = checkboxes.nth(i)
      const checked = await cb.isChecked().catch(() => false)
      if (!checked) await cb.check({ timeout: 2000 }).catch(() => {})
    }
    await page.waitForTimeout(4000)
  } catch {}
  await snap(page, '06_forecast_compare_districts.png', { fullPage: true })
})

// ───────────────────────────────────────────────────────────────────────────
//   07 — HotelDetail (overview + 30d forecast)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/hotels/${encodeURIComponent(HOTEL_ID)}`)
  await settle(page, 4500)
  await snap(page, '07_hotel_detail_overview.png', { fullPage: true })

  await safeClick(page, page.getByRole('button', { name: /^30/ }).first(), 'forecast 30d')
  await page.waitForTimeout(3500)
  await snap(page, '07_hotel_detail_forecast_30d.png', { fullPage: true })
})

// ───────────────────────────────────────────────────────────────────────────
//   08 — About (techstack, sources, limitations, parser-health)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${BASE}/about`)
  await settle(page, 3000)
  await snap(page, '08_about_techstack.png', { fullPage: false })

  // Раскрыть все <details>
  await page.evaluate(() => {
    document.querySelectorAll('details').forEach(d => { d.open = true })
  })
  await page.waitForTimeout(1000)
  await snap(page, '08_about_limitations_expanded.png', { fullPage: true })

  // Полная страница — даст и sources, и parser-health
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(500)
  await snap(page, '08_about_data_sources.png', { fullPage: true })

  // Спец-скриншот: scroll к секции парсеров и сделать viewport-shot
  try {
    await page.evaluate(() => {
      const el = [...document.querySelectorAll('h2,h3,h4')]
        .find(h => /парсер|здоров|health/i.test(h.innerText))
      if (el) el.scrollIntoView({ block: 'start' })
    })
    await page.waitForTimeout(1500)
    await snap(page, '08_about_parser_health.png', { fullPage: false })
  } catch (e) {
    console.log(`[!] parser-health section skipped: ${e.message}`)
  }
})

// ───────────────────────────────────────────────────────────────────────────
//   09 — Swagger UI и ReDoc (backend docs)
// ───────────────────────────────────────────────────────────────────────────
await withPage(async page => {
  await page.goto(`${API}/docs`)
  await settle(page, 4000)
  await snap(page, '09_swagger_ui.png', { fullPage: false })
})

await withPage(async page => {
  await page.goto(`${API}/redoc`)
  await settle(page, 5000)
  await snap(page, '09_redoc.png', { fullPage: false })
})

await browser.close()
console.log(`\n[✓] Tour complete. Output: ${OUT}`)
