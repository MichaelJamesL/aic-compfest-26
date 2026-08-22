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

function render(list: unknown = assets) {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/assets': list,
    '/business-context': (init: RequestInit | undefined) => JSON.parse(String(init?.body)),
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
      'Konteks bisnis',
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

  it('marks QC upload as unavailable rather than pretending it works', async () => {
    render()
    const zone = await screen.findByText(/Unggah batch citra produk/)
    expect(screen.getByText(/backend belum menerima berkas gambar/)).toBeTruthy()
    expect(zone.closest('button')?.disabled).toBe(true)
  })

  it('tracks input completeness as fields are filled', async () => {
    render()
    await screen.findByText('Kelengkapan input')
    fireEvent.change(screen.getByLabelText('Jadwal produksi'), {
      target: { value: 'Sen-Sab 2 shift' },
    })
    await waitFor(() =>
      expect(screen.queryByText(/^Jadwal produksi — kedalaman keputusan berkurang/)).toBeNull(),
    )
  })

  it('sends the complete business context, since the endpoint replaces rather than patches', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    fireEvent.change(screen.getByLabelText('Jadwal produksi'), { target: { value: 'Sen-Sab' } })
    fireEvent.change(screen.getByLabelText('Stok sparepart'), { target: { value: 'insert TNMG, seal' } })
    fireEvent.click(screen.getByRole('button', { name: /Jalankan analisis/ }))

    await waitFor(() => expect(calls.some((c) => c.url.includes('/business-context'))).toBe(true))
    const sent = calls.find((c) => c.url.includes('/business-context'))!.body as Record<string, unknown>
    // API.md gotcha 2: omitted fields are written as null, so all six go every time.
    expect(Object.keys(sent).sort()).toEqual([
      'operator_report',
      'production_schedule',
      'sparepart_eta',
      'spareparts',
      'technicians_available',
    ].sort())
    expect(sent.spareparts).toEqual(['insert TNMG', 'seal'])
    expect(sent.operator_report).toBeNull()
  })

  it('navigates to the result once the run returns', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Pilih mesin'), { target: { value: 'a1' } })
    fireEvent.click(screen.getByRole('button', { name: /Jalankan analisis/ }))
    await waitFor(() => expect(screen.getByText('navigated away')).toBeTruthy())
  })

  it('sends the user to Setup when no machine is registered', async () => {
    render([])
    expect(await screen.findByText(/Belum ada mesin terdaftar/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Buka Setup' })).toBeTruthy()
  })
})
