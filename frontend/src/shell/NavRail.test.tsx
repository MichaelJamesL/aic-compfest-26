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

describe('NavRail', () => {
  it('offers exactly three destinations', () => {
    render()
    const links = screen.getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/setup',
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

  it('marks the current destination as active', () => {
    render()
    // Class membership, not substring: the inactive item carries `hover:bg-ink/5`.
    const classes = (title: string) => screen.getByTitle(title).className.split(' ')
    expect(classes('Analisis')).toContain('bg-ink')
    expect(classes('Setup')).not.toContain('bg-ink')
    expect(classes('Analisis')).toContain('text-shell')
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
