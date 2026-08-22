import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { renderRoute } from '../test/harness'
import { SetupScreen } from './Setup'
import { AnalyzeScreen } from './Analyze'
import { AnalysisResultScreen } from './AnalysisResult'
import { WorkOrdersScreen } from './WorkOrders'
import { WorkOrderDetailScreen } from './WorkOrderDetail'
import { ExecuteScreen } from './Execute'
import { CompareScreen } from './Compare'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

/** A request that never settles, so the screen stays in its loading state. */
function stubPending() {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise(() => {})),
  )
}

// Element factories rather than elements: these are arguments to `it.each`,
// not a rendered list.
const screens = [
  ['Setup', '/setup', '/setup', () => <SetupScreen />],
  ['Analisis baru', '/analyze', '/analyze', () => <AnalyzeScreen />],
  ['Hasil analisis', '/analysis/x', '/analysis/:id', () => <AnalysisResultScreen />],
  ['Work order', '/work-orders', '/work-orders', () => <WorkOrdersScreen />],
  ['Work order detail', '/work-orders/x', '/work-orders/:id', () => <WorkOrderDetailScreen />],
  ['Eksekusi', '/work-orders/x/execute', '/work-orders/:id/execute', () => <ExecuteScreen />],
  ['Perbandingan', '/analysis/x/compare', '/analysis/:id/compare', () => <CompareScreen />],
] as const

describe('loading states', () => {
  // The four-state rule in SCREENS.md: every screen ships empty, loading,
  // error and partial. Loading was the one none of the tests touched.
  it.each(screens)('%s shows a skeleton while its data is in flight', (_name, path, pattern, element) => {
    stubPending()
    renderRoute(path, pattern, element())
    const loaders = screen.getAllByRole('status')
    expect(loaders.length).toBeGreaterThan(0)
    expect(loaders[0].getAttribute('aria-label')).toBe('Memuat')
  })

  it.each(screens)('%s never shows an error or empty state while still loading', (_n, path, pattern, element) => {
    stubPending()
    renderRoute(path, pattern, element())
    expect(screen.queryByText('Coba lagi')).toBeNull()
    expect(screen.queryByText(/Belum ada dokumen/)).toBeNull()
    expect(screen.queryByText(/Belum ada mesin terdaftar/)).toBeNull()
  })

  it('keeps the shell usable while a screen loads', () => {
    stubPending()
    renderRoute('/analysis/x', '/analysis/:id', <AnalysisResultScreen />)
    // Navigation and the engine-mode card must not wait on screen data.
    expect(screen.getByRole('link', { name: /Analisis/ })).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy()
  })
})
