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
  const noise = []
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    // A handled 4xx still logs to the console; that is the app working.
    if (/Failed to load resource/.test(msg.text())) noise.push(msg.text())
    else errors.push(msg.text())
  })
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
      // The white chrome must reach every edge of the viewport.
      shellGutter: (() => {
        const shell = document.querySelector('nav')?.parentElement
        if (!shell) return 'no shell'
        const box = shell.getBoundingClientRect()
        const gaps = []
        if (box.left > 0) gaps.push(`left ${Math.round(box.left)}px`)
        if (box.top > 0) gaps.push(`top ${Math.round(box.top)}px`)
        if (box.right < window.innerWidth - 1) {
          gaps.push(`right ${Math.round(window.innerWidth - box.right)}px`)
        }
        return gaps.length ? gaps.join(', ') : null
      })(),
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

  // Contrast, measured from what actually rendered rather than from the
  // palette table. This is the check that catches a dark-surface token used on
  // a light tinted card.
  const lowContrast = await page.evaluate(() => {
    const luminance = (rgb) => {
      const [r, g, b] = rgb.map((value) => {
        const channel = value / 255
        return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    const parse = (color) => {
      const match = color.match(/rgba?\(([^)]+)\)/)
      if (!match) return null
      const parts = match[1].split(',').map(Number)
      return { rgb: parts.slice(0, 3), alpha: parts.length > 3 ? parts[3] : 1 }
    }
    const backdrop = (node) => {
      for (let el = node; el; el = el.parentElement) {
        const parsed = parse(getComputedStyle(el).backgroundColor)
        if (parsed && parsed.alpha > 0.5) return parsed.rgb
      }
      return [255, 255, 255]
    }

    const findings = []
    for (const el of document.querySelectorAll('*')) {
      if (el.children.length) continue
      const text = el.textContent?.trim()
      if (!text) continue
      const style = getComputedStyle(el)
      if (style.visibility === 'hidden' || style.display === 'none') continue
      const fg = parse(style.color)
      if (!fg) continue

      // Muted text is blended, not exempt: skipping low-opacity elements would
      // let the checker pass by excluding exactly what it should measure.
      const bg = backdrop(el)
      const alpha = fg.alpha * parseFloat(style.opacity || '1')
      const blended = fg.rgb.map((channel, i) => alpha * channel + (1 - alpha) * bg[i])

      const [lighter, darker] = [luminance(blended), luminance(bg)].sort((a, b) => b - a)
      const ratio = (lighter + 0.05) / (darker + 0.05)
      const size = parseFloat(style.fontSize)
      const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 600)
      const floor = large ? 3 : 4.5
      if (ratio < floor) {
        findings.push({
          text: text.slice(0, 32),
          ratio: ratio.toFixed(2),
          size,
          floor,
          alpha: alpha.toFixed(2),
        })
      }
    }
    return findings.slice(0, 4)
  })
  for (const finding of lowContrast) {
    report(
      'fail',
      path,
      `contrast ${finding.ratio}:1 (needs ${finding.floor}, alpha ${finding.alpha}) on "${finding.text}"`,
    )
  }

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
  // The shell is full-bleed, so the body must match it — a stray page-grey
  // gutter appearing on overscroll is a regression.
  if (probe.bodyBg !== 'rgb(255, 255, 255)') {
    report('warn', path, `body background ${probe.bodyBg}, expected the shell white`)
  }
  if (probe.shellGutter) {
    report('fail', path, `shell does not reach the window edge (${probe.shellGutter})`)
  }
  if (probe.panelBg && probe.panelBg !== 'rgb(0, 0, 0)') report('warn', path, `panel background ${probe.panelBg}, expected #000000`)

  for (const error of errors) report('fail', path, `console: ${error.slice(0, 140)}`)
  for (const item of noise.slice(0, 2)) {
    report('warn', path, `request failed (handled): ${item.slice(0, 90)}`)
  }

  return probe
}

/**
 * Behaviour a DOM-only test cannot reach: real focus, real scrolling, real
 * media queries.
 */
async function keyboardWalk(page, route) {
  const reachable = []
  const ringless = []

  for (let i = 0; i < 30; i++) {
    await page.keyboard.press('Tab')
    const focused = await page.evaluate(() => {
      const el = document.activeElement
      if (!el || el === document.body) return null
      const visible = (node) => {
        const style = getComputedStyle(node)
        return style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0
      }
      // A composite control may draw the ring on its wrapper.
      const ring = visible(el) || (el.parentElement ? visible(el.parentElement) : false)
      const name =
        el.textContent?.trim() ||
        el.getAttribute('aria-label') ||
        el.getAttribute('placeholder') ||
        ''
      return { tag: el.tagName.toLowerCase(), label: name.slice(0, 28), ring }
    })
    if (!focused) break
    reachable.push(focused.label || focused.tag)
    if (!focused.ring) {
      ringless.push(`${focused.tag}${focused.label ? ` "${focused.label}"` : ''}`)
    }
  }

  if (reachable.length < 8) {
    report('fail', route, `only ${reachable.length} elements reachable by Tab`)
  }
  // An invisible focus ring is an accessibility failure, not a style choice.
  for (const element of ringless.slice(0, 3)) {
    report('fail', route, `no focus ring on ${element}`)
  }
}

async function interactions(browser, { analysisId }) {
  const result = `/analysis/${analysisId}`
  const context = await browser.newContext({ viewport: VIEWPORT })
  const page = await context.newPage()

  // Walk both a form screen and a read-only screen: only one has inputs, and
  // the inputs are where focus rings actually go missing.
  for (const route of ['/analyze', result]) {
    await page.goto(BASE + route, { waitUntil: 'networkidle' })
    await keyboardWalk(page, route)
  }

  // The header turns to glass only once the page scrolls past 24px.
  await page.goto(BASE + result, { waitUntil: 'networkidle' })
  const header = () =>
    page.evaluate(() => getComputedStyle(document.querySelector('header')).backdropFilter)
  const before = await header()
  await page.evaluate(() => window.scrollTo(0, 200))
  await page.waitForTimeout(200)
  const after = await header()
  if (before !== 'none') report('fail', result, `header is glass before scrolling (${before})`)
  if (!after.includes('blur')) report('fail', result, `header did not become glass on scroll (${after})`)
  await page.screenshot({ path: join(OUT, 'header-stuck.png') })
  await context.close()

  // prefers-reduced-motion must collapse transitions, not be ignored.
  // Durations collapse to 0.01ms, which computes as "1e-05s" — parse rather
  // than compare against the string "0s".
  const reduced = await browser.newContext({ viewport: VIEWPORT, reducedMotion: 'reduce' })
  const quiet = await reduced.newPage()
  await quiet.goto(BASE + result, { waitUntil: 'networkidle' })
  const durations = await quiet.evaluate(() =>
    [...document.querySelectorAll('button, a')]
      .map((el) => getComputedStyle(el).transitionDuration)
      .map((value) => Math.max(...value.split(',').map((part) => parseFloat(part) || 0)))
      .filter((seconds) => seconds > 0.05),
  )
  if (durations.length) {
    report('fail', result, `${durations.length} transitions survive prefers-reduced-motion`)
  }
  await reduced.close()
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

  // Error and empty states have only ever been asserted in happy-dom. They are
  // what a judge sees if something breaks on camera, so look at them.
  for (const [name, path] of [
    ['error-analysis', '/analysis/00000000-0000-0000-0000-000000000000'],
    ['error-work-order', '/work-orders/00000000-0000-0000-0000-000000000000'],
  ]) {
    const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 })
    const page = await context.newPage()
    const probe = await visit(page, name, path)
    // An error state still has to be a designed screen, not a blank panel.
    if (probe.textNodes < 300) {
      report('fail', path, `error state is nearly empty (${probe.textNodes} chars)`)
    }
    const hasRecovery = await page.evaluate(() =>
      Boolean([...document.querySelectorAll('button')].find((b) => /coba lagi|muat ulang/i.test(b.textContent ?? ''))),
    )
    if (!hasRecovery) report('fail', path, 'error state offers no retry')
    await context.close()
  }

  await interactions(browser, await discover())

  // Narrow viewport: the rail collapses to icons, tables scroll inside
  // themselves. Navigation and the engine-mode signal must survive.
  const narrow = await browser.newContext({ viewport: { width: 900, height: 900 } })
  const page = await narrow.newPage()
  const route = `/analysis/${analysisId}`
  await visit(page, 'result-900', route)

  const rail = await page.evaluate(() => {
    const nav = document.querySelector('nav')
    if (!nav) return { present: false }
    const box = nav.getBoundingClientRect()
    return {
      present: box.width > 0 && box.height > 0,
      width: Math.round(box.width),
      links: [...nav.querySelectorAll('a')].map(
        (a) => a.getAttribute('title') || a.textContent?.trim() || '',
      ),
      engineMode: Boolean(
        nav.querySelector('[aria-label^="Mesin analisis"]') ||
          nav.textContent?.includes('Mesin analisis'),
      ),
    }
  })

  if (!rail.present) {
    report('fail', `${route} @900`, 'navigation disappears at narrow widths')
  } else {
    if (rail.links.length !== 3) {
      report('fail', `${route} @900`, `expected 3 nav destinations, found ${rail.links.length}`)
    }
    if (rail.width > 96) {
      report('warn', `${route} @900`, `rail is ${rail.width}px, expected a ~64px icon strip`)
    }
    // Presenting stub output as model output is the one unrecoverable mistake,
    // so the engine-mode signal may never be dropped by a breakpoint.
    if (!rail.engineMode) {
      report('fail', `${route} @900`, 'engine-mode indicator is missing from the rail')
    }
  }

  await narrow.close()
} finally {
  await browser.close()
}

const failures = findings.filter((f) => f.level === 'fail')
console.log(
  `\n${findings.length === 0 ? 'clean' : `${failures.length} failing, ${findings.length - failures.length} warning`} — shots in scripts/.shots/`,
)
process.exit(failures.length ? 1 : 0)
