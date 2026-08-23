import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { ErrorBoundary } from './ErrorBoundary'

function Explode(): never {
  throw new Error('capabilities is not defined')
}

let consoleError: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  // React logs the caught error itself; keep the test output readable.
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => {
  consoleError.mockRestore()
  cleanup()
})

describe('ErrorBoundary', () => {
  it('passes children through when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>Hasil analisis</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('Hasil analisis')).toBeTruthy()
  })

  /**
   * A component throwing used to blank the whole page — `StatusCard` reading an
   * unexpected response did exactly that. On an unedited recording a blank page
   * ends the take.
   */
  it('shows a designed screen instead of a blank page', () => {
    render(
      <ErrorBoundary>
        <Explode />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('heading', { name: 'Ada yang gagal dimuat' })).toBeTruthy()
    expect(screen.getByText(/Data yang sudah tersimpan tidak terpengaruh/)).toBeTruthy()
  })

  it('surfaces the message so the failure is diagnosable on camera', () => {
    render(
      <ErrorBoundary>
        <Explode />
      </ErrorBoundary>,
    )
    expect(screen.getByText('capabilities is not defined')).toBeTruthy()
    expect(consoleError).toHaveBeenCalled()
  })

  it('offers a reload and a route back into the app', () => {
    render(
      <ErrorBoundary>
        <Explode />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('button', { name: 'Muat ulang' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Kembali ke Analisis' })).toBeTruthy()
  })
})
