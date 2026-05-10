// Screenshot generation for ВКР figures 13-18
// Usage: cd frontend && node scripts/screenshots.mjs
import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'
import path from 'path'

const BASE = process.env.SCREENSHOT_BASE || 'http://localhost:5173'
const OUT = path.resolve('..', '.screenshots')
const VIEWPORT = { width: 1440, height: 900 }
const DPR = 2

await mkdir(OUT, { recursive: true })

console.log(`[i] base=${BASE}  out=${OUT}  viewport=${VIEWPORT.width}x${VIEWPORT.height}@${DPR}x`)

const browser = await chromium.launch({ headless: true })

async function makeContext(theme) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: DPR,
    locale: 'ru-RU',
  })
  await ctx.addInitScript(t => {
    try {
      localStorage.setItem('pribaikalie_theme', t)
      const r = document.documentElement
      r.classList.remove('dark', 'light')
      r.classList.add(t)
    } catch {}
  }, theme)
  return ctx
}

async function settle(page, extraMs = 1500) {
  await page.waitForLoadState('domcontentloaded').catch(() => {})
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(extraMs)
}

async function snap(page, name, opts = {}) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, ...opts })
  console.log(`[+] ${name}`)
  return file
}

async function snapElement(page, selector, name) {
  const el = await page.locator(selector).first()
  const file = path.join(OUT, name)
  await el.screenshot({ path: file })
  console.log(`[+] ${name} (element ${selector})`)
  return file
}

// ─── Fig 13: Sidebar ────────────────────────────────────────────────────────
{
  const ctx = await makeContext('dark')
  const page = await ctx.newPage()
  await page.goto(`${BASE}/`)
  await settle(page, 2000)
  await snapElement(page, 'aside', 'figure_13_navigation.png')
  await ctx.close()
}

// ─── Fig 14: Themes (dark + light, side by side later) ─────────────────────
for (const theme of ['dark', 'light']) {
  const ctx = await makeContext(theme)
  const page = await ctx.newPage()
  await page.goto(`${BASE}/analytics?district=Иркутский`)
  await settle(page, 2500)
  await snap(page, `figure_14_themes_${theme}.png`, { fullPage: true })
  await ctx.close()
}

// ─── Fig 15: Analytics dashboard (regions tab, dark) ───────────────────────
{
  const ctx = await makeContext('dark')
  const page = await ctx.newPage()
  await page.goto(`${BASE}/analytics?district=Иркутский`)
  await settle(page, 2500)
  await snap(page, 'figure_15_analytics.png', { fullPage: true })
  await ctx.close()
}

// ─── Fig 16: Forecast expert (Модели + ансамбль + AI-объяснение) ───────────
{
  const ctx = await makeContext('dark')
  const page = await ctx.newPage()
  await page.goto(`${BASE}/forecast?district=Иркутский&days=14`)
  await settle(page, 3000)

  // Switch to "Модели" (expert) view
  await page.getByRole('button', { name: 'Модели' }).first().click()
  await page.waitForTimeout(2500) // Recharts re-render

  // Click "Получить объяснение" if visible
  try {
    const btn = page.getByRole('button', { name: /получить объяснение|обновить/i })
    if (await btn.count()) {
      await btn.first().click()
      // wait until "Анализ..." loader disappears OR explanation text appears
      await page.waitForFunction(() => {
        const t = document.body.innerText
        return !/Анализ\.{3}/i.test(t) && /(прогноз|модел|ансамбл|RMSE|тренд)/i.test(t)
      }, { timeout: 60_000 }).catch(() => {})
      await page.waitForTimeout(1500)
    }
  } catch (e) {
    console.log('[!] explain step skipped:', e.message)
  }

  await snap(page, 'figure_16_forecast.png', { fullPage: true })
  await ctx.close()
}

// ─── Fig 17: Yandex Map ────────────────────────────────────────────────────
{
  const ctx = await makeContext('dark')
  const page = await ctx.newPage()
  await page.goto(`${BASE}/map`)
  await settle(page, 4000) // Yandex tiles slow
  await page.waitForTimeout(3000) // extra for placemarks
  await snap(page, 'figure_17_map.png', { fullPage: false })
  await ctx.close()
}

// ─── Fig 18: Chat with B2B query ───────────────────────────────────────────
{
  const ctx = await makeContext('dark')
  const page = await ctx.newPage()
  await page.goto(`${BASE}/chat`)
  await settle(page, 1500)

  const QUERY = 'Сравни RevPAR Иркутского и Ольхонского районов за последние 30 дней'

  // Find text input — Chat uses <input> at the bottom
  const input = page.locator('input[type="text"], textarea').first()
  await input.click()
  await input.fill(QUERY)
  await page.keyboard.press('Enter')

  console.log('[i] waiting for AI response (up to 90s)...')
  // Wait for assistant message with substantial content
  try {
    await page.waitForFunction(() => {
      // Look for assistant message containers (markdown-rendered)
      const proseEls = Array.from(document.querySelectorAll('.prose, [class*="prose"], article'))
      const text = proseEls.map(e => e.innerText || '').join(' ')
      return text.length > 250 && /RevPAR|загрузк|тариф|район/i.test(text)
    }, { timeout: 120_000 })
    await page.waitForTimeout(2000)
  } catch (e) {
    console.log('[!] AI wait timeout — capturing whatever is on screen:', e.message)
  }

  // Scroll input into view (chat usually auto-scrolls)
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.waitForTimeout(500)

  await snap(page, 'figure_18_chat.png', { fullPage: false })
  await ctx.close()
}

await browser.close()
console.log('\n[✓] All screenshots saved to', OUT)
