import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { CAPABILITIES, calls, renderRoute, stubRoutes } from '../test/harness'
import { AnalyzeScreen } from './Analyze'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const assets = [
  { id: 'a1', name: 'CNC-02', asset_type: 'cnc-mill', criticality: 'high', location: null, status: 'active', specs: {}, factory_id: 'f' },
]

const emptyContext = { production_schedule: null, inventory: [], technicians: [] }

function render(list: unknown = assets, context: unknown = emptyContext) {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/assets': list,
    '/api/v1/business-context': context,
    '/condition': { asset_id: 'a1', condition: 'ok' },
     '/api/v1/assets/a1/qc-batches': { id: 'qc-1', asset_id: 'a1', factory_id: 'f', count: 2, defect_count: 0, defect_rate: 0, images: [], created_at: '2026-08-23T00:00:00' },
     '/analyses': { id: 'run-1', status: 'succeeded', result: null, engine_mode: 'offline_stub', error_code: null, error_message: null, health_score: 78, priority: 'medium' },
  })
  return renderRoute('/analyze', '/analyze', <AnalyzeScreen />)
}

describe('Analyze — the single input form', () => {
  it('offers every input the FR lists, in pipeline order', async () => {
    render()
    await screen.findByText('Kelengkapan input')
    // Scoped to headings: the same names also appear in the completeness panel.
    const sections = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent)
    expect(sections).toEqual([
      'Mesin',
      'Data sensor',
      'Citra QC',
      'Kondisi manual',
    ])
    // The completeness panel is a card, so it is an h3 alongside the sections.
    expect(screen.getByRole('heading', { level: 3, name: 'Kelengkapan input' })).toBeTruthy()
  })

  // FINAL_IDEA.md §15 "Adopsi" — fixed wording, must not be paraphrased.
  it('carries the partial-input sentence verbatim', async () => {
    render()
    expect(
      await screen.findByText(
        /Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin lengkap input, makin dalam keputusannya\./,
      ),
    ).toBeTruthy()
  })

  it('disables the run button until a machine is chosen, and never for missing input', async () => {
    render()
    const button = await screen.findByRole('button', { name: /Jalankan analisis/ })
    expect((button as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    // Every other input is still empty — the point of partial-input analysis.
    expect((button as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps QC upload disabled until a machine is chosen', async () => {
    render()
    const zone = await screen.findByText(/Unggah batch citra produk/)
    expect(zone.closest('button')?.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    expect(zone.closest('button')?.disabled).toBe(false)
  })

  it('uploads QC images and includes the returned batch in analysis', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    const zone = screen.getByText(/Unggah batch citra produk/)
    const input = zone.parentElement!.parentElement!.querySelector('input[type="file"]')!
    fireEvent.change(input, {
      target: { files: [new File(['image'], 'part.png', { type: 'image/png' })] },
    })

    await waitFor(() => expect(calls.some((call) => call.url.includes('/qc-batches'))).toBe(true))
    const upload = calls.find((call) => call.url.includes('/qc-batches'))!
    expect(upload.method).toBe('POST')
    expect(upload.body).toBeInstanceOf(FormData)
    expect(await screen.findByText(/Batch QC tersimpan/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Jalankan analisis/ }))
    await waitFor(() => expect(calls.some((call) => call.url.includes('/analyses'))).toBe(true))
    const analysis = calls.find((call) => call.url.includes('/analyses'))!.body as Record<string, unknown>
    expect(analysis.qc_batch_id).toBe('qc-1')
  })

  it('states what each missing input costs, specifically', async () => {
    render()
    await screen.findByText('Kelengkapan input')
    // Not a repeated generic sentence — each input names its own consequence.
    expect(
      screen.getByText(/jendela maintenance tidak bisa dioptimalkan, hanya diprioritaskan/),
    ).toBeTruthy()
    expect(screen.getByText(/ETA tidak bisa jadi blocker penjadwalan/)).toBeTruthy()
  })

  it('scores the factory-wide context it did not collect itself', async () => {
    render(assets, {
      production_schedule: { work_time: { monday: { start: '06:00:00', end: '14:00:00' } } },
      inventory: [],
      technicians: [],
    })
    await screen.findByText('Kelengkapan input')
    await waitFor(() =>
      expect(screen.queryByText(/jendela maintenance tidak bisa dioptimalkan/)).toBeNull(),
    )
    // Still missing, and still named with its cost.
    expect(screen.getByText(/ETA tidak bisa jadi blocker penjadwalan/)).toBeTruthy()
  })

  it('does not claim maintenance history, which this form does not collect', async () => {
    render()
    await screen.findByText('Kelengkapan input')
    expect(screen.queryByText('Histori maintenance')).toBeNull()
  })

  it('leaves the factory-wide context alone and only writes the machine condition', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    fireEvent.change(screen.getByPlaceholderText(/Getaran meningkat/), {
      target: { value: 'chatter sejak shift malam' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Jalankan analisis/ }))

    await waitFor(() => expect(calls.some((c) => c.url.includes('/analyses'))).toBe(true))
    expect(calls.some((c) => c.method === 'PUT' && c.url.includes('/business-context'))).toBe(false)
    const condition = calls.find((c) => c.url.includes('/condition'))!.body as Record<string, unknown>
    expect(condition.condition).toBe('chatter sejak shift malam')
  })

  it('navigates to the result once the run returns', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    fireEvent.click(screen.getByRole('button', { name: /Jalankan analisis/ }))
    await waitFor(() => expect(screen.getByText('navigated away')).toBeTruthy())
  })

  it('offers no dead controls in the header', async () => {
    render()
    await screen.findByText('Kelengkapan input')
    // Search, settings and notifications were decoration copied from the
    // reference; a control that does nothing is worse than an absent one.
    expect(screen.queryByRole('searchbox')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Pengaturan' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Notifikasi' })).toBeNull()
  })

  it('sends the user to Setup when no machine is registered', async () => {
    render([])
    expect(await screen.findByText(/Belum ada mesin terdaftar/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Buka Setup' })).toBeTruthy()
  })
})
