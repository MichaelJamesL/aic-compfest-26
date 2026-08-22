/**
 * Visual pass over every screen at the recording viewport.
 *
 * happy-dom does no layout, so the unit tests cannot catch a broken grid, a
 * clipped card, or a panel that scrolls sideways. This does.
 *
 *   node scripts/browser-pass.mjs [baseUrl]
 *
 * Needs the app on :5173 and the backend on :8000. Writes PNGs to
 * scripts/.shots/ (git-ignored) and fails the process on any hard finding.
 */
import { chromium } from 'playwright'
import { mkdirSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const BASE = process.argv[2] ?? 'http://localhost:5173'
const API = process.env.API_URL ?? 'http://localhost:8000'
const OUT = join(dirname(fileURLToPath(import.meta.url)), '.shots')

// The demo is recorded at 1440×900.
const VIEWPORT = { width: 1440, height: 900 }

async function discover() {
  const orders = await fetch(`${API}/api/v1/work-orders`).then((r) => r.json())
  const order = orders[0]
  if (!order) throw new Error('No work order to inspect — seed the backend first.')
  return { workOrderId: order.id, analysisId: order.analysis_id }
}

const findings = []
function report(level, route, message) {
  findings.push({ level, route, message })
  const mark = level === 'fail' ? '✗' : '!'
  console.log(`${mark} ${route.padEnd(42)} ${message}`)
}

async function visit(page, name, path) {
  const errors = []
  page.on('console', (msg) => msg.type() === 'error' && errors.push(msg.text()))
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto(BASE + path, { waitUntil: 'networkidle' })
  await page.waitForTimeout(250)

  const probe = await page.evaluate(() => {
    const doc = document.documentElement
    const body = document.body
    // Anything wider than the viewport that is not inside an intentional
    // horizontal scroller is a layout bug.
    const wide = [...document.querySelectorAll('*')]
      .filter((el) => {
        if (el.scrollWidth <= el.clientWidth + 1) return false
        const style = getComputedStyle(el)
        // `auto`/`scroll` is an intentional scroller; `hidden` is intentional
        // clipping (a truncated label). Neither is a layout bug.
        return !['auto', 'scroll', 'hidden'].includes(style.overflowX)
      })
      .slice(0, 3)
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]}`)

    const panel = document.querySelector('main')?.parentElement
    return {
      pageScrollsSideways: doc.scrollWidth > doc.clientWidth + 1,
      overflowing: wide,
      bodyBg: getComputedStyle(body).backgroundColor,
      panelBg: panel ? getComputedStyle(panel).backgroundColor : null,
      panelRadius: panel ? getComputedStyle(panel).borderRadius : null,
      font: getComputedStyle(body).fontFamily,
      headingCount: document.querySelectorAll('h1').length,
      textNodes: document.body.innerText.length,
      // Nothing may render an empty box with no content.
      emptyCards: [...document.querySelectorAll('section')].filter(
        (el) => el.innerText.trim().length === 0,
      ).length,
      // Text clipped by `truncate` is legal but usually unintended — a label
      // that does not fit is a design problem, so surface it as a warning.
      clipped: [...document.querySelectorAll('*')]
        .filter((el) => {
          if (el.children.length) return false
          if (el.scrollWidth <= el.clientWidth + 1) return false
          return getComputedStyle(el).overflowX === 'hidden'
        })
        .slice(0, 4)
        .map((el) => el.textContent?.trim().slice(0, 30) ?? ''),
    }
  })

  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true })
  // A fullPage capture parks sticky elements at the first viewport's bottom,
  // which misrepresents them. Capture the viewport too.
  await page.screenshot({ path: join(OUT, `${name}-viewport.png`) })

  if (probe.pageScrollsSideways) report('fail', path, 'page scrolls horizontally at 1440')
  for (const text of probe.clipped) report('warn', path, `text clipped: "${text}"`)
  if (probe.overflowing.length) {
    report('fail', path, `content overflows without a scroller: ${probe.overflowing.join(', ')}`)
  }
  if (probe.headingCount !== 1) report('fail', path, `expected exactly one h1, found ${probe.headingCount}`)
  if (probe.emptyCards) report('fail', path, `${probe.emptyCards} empty card(s) rendered`)
  if (probe.textNodes < 200) report('fail', path, `page looks blank (${probe.textNodes} chars of text)`)
  if (!probe.font.includes('Plus Jakarta Sans')) report('fail', path, `wrong font: ${probe.font}`)
  if (probe.bodyBg !== 'rgb(229, 229, 229)') report('warn', path, `body background ${probe.bodyBg}, expected #E5E5E5`)
  if (probe.panelBg && probe.panelBg !== 'rgb(0, 0, 0)') report('warn', path, `panel background ${probe.panelBg}, expected #000000`)

  for (const error of errors) report('fail', path, `console: ${error.slice(0, 140)}`)

  return probe
}

const browser = await chromium.launch()
try {
  rmSync(OUT, { recursive: true, force: true })
  mkdirSync(OUT, { recursive: true })

  const { workOrderId, analysisId } = await discover()
  const routes = [
    ['setup', '/setup'],
    ['analyze', '/analyze'],
    ['result', `/analysis/${analysisId}`],
    ['compare', `/analysis/${analysisId}/compare?with=${analysisId}`],
    ['work-orders', '/work-orders'],
    ['work-order-detail', `/work-orders/${workOrderId}`],
    ['execute', `/work-orders/${workOrderId}/execute`],
    ['report', `/work-orders/${workOrderId}/report`],
  ]

  for (const [name, path] of routes) {
    const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 })
    const page = await context.newPage()
    await visit(page, name, path)
    await context.close()
  }

  // Narrow viewport: the rail collapses, tables scroll inside themselves.
  const narrow = await browser.newContext({ viewport: { width: 900, height: 900 } })
  const page = await narrow.newPage()
  await visit(page, 'result-900', `/analysis/${analysisId}`)
  await narrow.close()
} finally {
  await browser.close()
}

const failures = findings.filter((f) => f.level === 'fail')
console.log(
  `\n${findings.length === 0 ? 'clean' : `${failures.length} failing, ${findings.length - failures.length} warning`} — shots in scripts/.shots/`,
)
process.exit(failures.length ? 1 : 0)
