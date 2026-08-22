import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { RunProgress } from './RunProgress'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  cleanup()
})

function tick(seconds: number) {
  act(() => {
    vi.advanceTimersByTime(seconds * 1000)
  })
}

describe('RunProgress — the two-minute wait', () => {
  // POST /analyses blocks with no progress endpoint, so this is an estimate.
  // Saying so is the point; a fake progress bar would be a lie on camera.
  it('labels the pipeline as an estimate, not telemetry', () => {
    render(<RunProgress step={3} readingCount={0} />)
    expect(screen.getByText('Perkiraan tahap')).toBeTruthy()
    expect(screen.getByText(/mencerminkan pipeline, bukan telemetri/)).toBeTruthy()
  })

  it('names each stage and whether it is deterministic or the model', () => {
    render(<RunProgress step={3} readingCount={0} />)
    expect(screen.getByText('Deteksi anomali')).toBeTruthy()
    expect(screen.getByText('Menyusun diagnosis')).toBeTruthy()
    expect(screen.getAllByText('deterministik').length).toBeGreaterThan(0)
    expect(screen.getAllByText('DeepSeek').length).toBe(2)
  })

  it('marks stages that are not built as unavailable rather than pretending', () => {
    render(<RunProgress step={3} readingCount={0} />)
    expect(screen.getByText('Klasifikasi defect QC')).toBeTruthy()
    // classifier, mapping, decide.py — three stages that do not exist yet
    expect(screen.getAllByText('belum tersedia')).toHaveLength(3)
  })

  it('counts elapsed time only once the engine call starts', () => {
    const { rerender } = render(<RunProgress step={1} readingCount={12} />)
    tick(5)
    expect(screen.getByText('0s')).toBeTruthy()
    rerender(<RunProgress step={3} readingCount={12} />)
    tick(3)
    expect(screen.getByText('8s')).toBeTruthy()
  })

  it('hides the upload step when there are no readings to send', () => {
    render(<RunProgress step={3} readingCount={0} />)
    expect(screen.queryByText(/pembacaan sensor/)).toBeNull()
  })

  it('shows the upload step with its real count', () => {
    render(<RunProgress step={1} readingCount={22} />)
    expect(screen.getByText('Mengunggah 22 pembacaan sensor')).toBeTruthy()
  })

  it('degrades to "masih berjalan" past the client timeout instead of stalling at 99%', () => {
    render(<RunProgress step={3} readingCount={0} />)
    tick(121)
    expect(screen.getByText('masih berjalan…')).toBeTruthy()
    expect(screen.queryByText('121s')).toBeNull()
  })

  it('states the synchronous-scope claim while the user waits', () => {
    render(<RunProgress step={3} readingCount={0} />)
    expect(
      screen.getByText(/tidak ada auto-tuning, background job, maupun loop umpan balik otomatis/i),
    ).toBeTruthy()
  })
})
