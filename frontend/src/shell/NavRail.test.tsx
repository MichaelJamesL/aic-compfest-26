import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { CAPABILITIES, renderRoute, stubRoutes } from '../test/harness'
import { NavRail } from './NavRail'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function render(engineOn = false) {
  stubRoutes({
    '/config/capabilities': {
      ...CAPABILITIES,
      capabilities: { ...CAPABILITIES.capabilities, ai_engine: engineOn },
    },
  })
  return renderRoute('/analyze', '/analyze', <NavRail />)
}

describe('brand', () => {
  it('shows the Siena wordmark with an accessible name', () => {
    render()
    // Both lockups are in the DOM; only one is displayed per breakpoint.
    const marks = screen.getAllByAltText('Siena')
    expect(marks).toHaveLength(2)
    // The light variants: the dark ones are for light surfaces and favicons.
    expect(marks.map((m) => m.getAttribute('src')).sort()).toEqual([
      '/logo-text-white.png',
      '/logo-white.png',
    ])
  })

  // The light variants clear 6.39:1 on the rail, so nothing sits behind them.
  // A plate would reintroduce a light block the design does not need.
  it('places the mark straight on the rail, with no plate behind it', () => {
    render()
    for (const mark of screen.getAllByAltText('Siena')) {
      expect(mark.parentElement!.className).not.toContain('bg-surface-card')
    }
  })

  it('carries the positioning line once, on the wide rail', () => {
    render()
    expect(screen.getByText('Intelligence, grounded in industry')).toBeTruthy()
  })
})

describe('NavRail', () => {
  it('offers exactly five destinations', () => {
    render()
    const links = screen.getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/setup',
      '/machines/new',
      '/business-context',
      '/analyze',
      '/work-orders',
    ])
  })

  /**
   * Below 1024 the rail collapses to icons — it is never removed. Labels are
   * hidden with `lg:inline`, so the accessible name has to come from `title`
   * as well, or the strip is unusable.
   */
  it('keeps an accessible name on every item once labels are hidden', () => {
    render()
    for (const label of ['Setup', 'Analisis', 'Work order']) {
      expect(screen.getByTitle(label)).toBeTruthy()
    }
  })

  it('never drops navigation at narrow widths', () => {
    const { container } = render()
    const nav = container.querySelector('nav')!
    // 64px strip that widens at lg — not `hidden`.
    expect(nav.className).toContain('w-16')
    expect(nav.className).toContain('lg:w-[232px]')
    expect(nav.className).not.toContain('hidden')
  })

  // A long results page must not scroll the navigation away.
  it('stays put while the page scrolls', () => {
    const { container } = render()
    const nav = container.querySelector('nav')!.className.split(' ')
    expect(nav).toContain('sticky')
    expect(nav).toContain('top-0')
    expect(nav).toContain('h-screen')
    // Its own content scrolls internally rather than pushing the rail taller.
    expect(nav).toContain('overflow-y-auto')
  })

  it('marks the current destination as active', () => {
    render()
    // Class membership, not substring: the inactive item carries `hover:bg-white/5`.
    const classes = (title: string) => screen.getByTitle(title).className.split(' ')
    // The rail is dark, so the active pill inverts to a light fill.
    expect(classes('Analisis')).toContain('bg-rail-content')
    expect(classes('Setup')).not.toContain('bg-rail-content')
    expect(classes('Analisis')).toContain('text-rail')
  })
})

describe('engine mode is never hidden', () => {
  it('shows the offline stub warning in both the card and the compact dot', async () => {
    render(false)
    expect(await screen.findByText('Mode offline (stub)')).toBeTruthy()
    expect(screen.getByLabelText('Mesin analisis: Mode offline (stub)')).toBeTruthy()
  })

  it('reports the live engine in both', async () => {
    render(true)
    expect(await screen.findByText('DeepSeek aktif')).toBeTruthy()
    expect(screen.getByLabelText('Mesin analisis: DeepSeek aktif')).toBeTruthy()
  })

  it('states the synchronous-scope claim', async () => {
    render()
    expect(
      await screen.findByText(/Tidak ada background job, auto-tuning, maupun loop umpan balik/i),
    ).toBeTruthy()
  })
})
