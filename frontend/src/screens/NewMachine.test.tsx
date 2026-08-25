import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { CAPABILITIES, calls, renderRoute, stubRoutes } from '../test/harness'
import { NewMachineScreen } from './NewMachine'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const asset = {
  id: 'a1', factory_id: 'f', name: 'CNC-02', asset_type: 'cnc-mill',
  criticality: 'high', location: 'Lini A', status: 'active', specs: { max_temp_c: 85 },
}

function render(routes: Record<string, unknown> = {}) {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/assets': asset,
    '/api/v1/assets/a1/models': { asset_id: 'a1', product: 'cnc-mill', bank_path: '/banks/cnc-mill.pt', images_used: 2 },
    '/api/v1/assets/a1/readings/import': { count: 20, errors: [], readings: [] },
    '/api/v1/assets/a1/baseline': { asset_id: 'a1', tags: { bearing_temp_c: 20 }, points_used: 20, readings_available: 20 },
    ...routes,
  })
  return renderRoute('/machines/new', '/machines/new', <NewMachineScreen />)
}

function fill() {
  fireEvent.change(screen.getByLabelText('Nama'), { target: { value: 'CNC-02' } })
  fireEvent.change(screen.getByLabelText('Tipe'), { target: { value: 'cnc-mill' } })
  fireEvent.change(screen.getByLabelText('Kritikalitas'), { target: { value: 'high' } })
  fireEvent.change(screen.getByLabelText('Lokasi'), { target: { value: 'Lini A' } })
}

/** `which` picks the dropzone: 0 = sensor history CSV, 1 = reference images. */
function drop(files: File[], which = 1) {
  const input = document.querySelectorAll('input[type="file"]')[which] as HTMLInputElement
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  fireEvent.change(input)
}

const image = (name: string) => new File(['x'], name, { type: 'image/png' })

describe('Mesin baru', () => {
  it('will not submit without a name', () => {
    render()
    const button = screen.getByRole('button', { name: /Daftarkan mesin/ }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Nama'), { target: { value: 'CNC-02' } })
    expect(button.disabled).toBe(false)
  })

  it('registers the machine with its specs, typed as numbers not strings', async () => {
    render()
    fill()
    fireEvent.click(screen.getByRole('button', { name: /Tambah spesifikasi/ }))
    fireEvent.change(screen.getByLabelText('Nama spesifikasi 1'), { target: { value: 'max_temp_c' } })
    fireEvent.change(screen.getByLabelText('Nilai spesifikasi 1'), { target: { value: '85' } })
    // a row with no name is half-typed, not a spec
    fireEvent.click(screen.getByRole('button', { name: /Tambah spesifikasi/ }))
    fireEvent.change(screen.getByLabelText('Nilai spesifikasi 2'), { target: { value: 'ignored' } })

    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))
    await screen.findByText('Mesin terdaftar')
    const sent = calls.find((c) => c.method === 'POST')!.body as Record<string, any>
    expect(sent).toMatchObject({
      name: 'CNC-02', asset_type: 'cnc-mill', criticality: 'high', location: 'Lini A',
      external_id: null, specs_json: { max_temp_c: 85 },
    })
  })

  it('trains the visual model from the reference images, keyed by machine type', async () => {
    render()
    fill()
    drop([image('good-1.png'), image('good-2.png')])
    expect(screen.getByText('2 citra siap dilatih')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))
    await screen.findByText('Mesin terdaftar')
    const training = calls.find((c) => c.url.includes('/models'))!
    expect(training.method).toBe('POST')
    expect((training.body as FormData).getAll('files')).toHaveLength(2)
    expect((training.body as FormData).get('product')).toBe('cnc-mill')
    expect(screen.getByText(/terlatih dari 2 citra referensi/)).toBeTruthy()
  })

  it('imports the history, then learns the baseline from it', async () => {
    render()
    fill()
    drop([new File(['tag,value,unit,recorded_at\n'], 'history.csv', { type: 'text/csv' })], 0)
    expect(screen.getByText('history.csv')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))
    await screen.findByText('Mesin terdaftar')
    const importCall = calls.findIndex((c) => c.url.includes('/readings/import'))
    const fitCall = calls.findIndex((c) => c.url.includes('/baseline'))
    expect(importCall).toBeGreaterThan(-1)
    // order matters: the baseline is fitted from what the import just stored
    expect(fitCall).toBeGreaterThan(importCall)
    expect(screen.getByText(/terpasang dari 20 pembacaan · bearing_temp_c \(20\)/)).toBeTruthy()
  })

  it('says the baseline is absent when no history was given', async () => {
    render()
    fill()
    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))
    await screen.findByText('Mesin terdaftar')
    expect(calls.some((c) => c.url.includes('/baseline'))).toBe(false)
    expect(screen.getByText(/belum ada — deteksi memakai pagar IQR per batch/)).toBeTruthy()
  })

  it('reports history too thin to learn from, without calling it a failure', async () => {
    render({
      '/api/v1/assets/a1/baseline': { asset_id: 'a1', tags: {}, points_used: 0, readings_available: 3 },
    })
    fill()
    drop([new File(['tag,value,unit,recorded_at\n'], 'thin.csv', { type: 'text/csv' })], 0)
    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))
    await screen.findByText('Mesin terdaftar')
    expect(screen.getByText(/histori terlalu sedikit untuk dipelajari/)).toBeTruthy()
  })

  it('skips training when no reference image was given, and says so', async () => {
    render()
    fill()
    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))
    await screen.findByText('Mesin terdaftar')
    expect(calls.some((c) => c.url.includes('/models'))).toBe(false)
    expect(screen.getByText(/belum ada — mesin tetap bisa dianalisis/)).toBeTruthy()
  })

  it('keeps the machine when only the training fails, and retries just the training', async () => {
    const broken = {
      ok: false,
      status: 422,
      headers: new Headers(),
      json: async () => ({
        error: { code: 'VALIDATION_ERROR', message: 'ai_engine_unavailable', details: [], request_id: 'req-9' },
      }),
    }
    render({ '/api/v1/assets/a1/models': broken })
    fill()
    drop([image('good-1.png')])
    fireEvent.click(screen.getByRole('button', { name: /Daftarkan mesin/ }))

    // the machine is registered — the screen must not report the whole thing failed
    expect(await screen.findByText('Mesin terdaftar')).toBeTruthy()
    expect(screen.getByText(/Mesin sudah tersimpan; hanya pelatihan model yang gagal/)).toBeTruthy()

    const before = calls.filter((c) => c.url.includes('/models')).length
    fireEvent.click(screen.getByRole('button', { name: /Coba lagi/ }))
    await waitFor(() =>
      expect(calls.filter((c) => c.url.includes('/models')).length).toBe(before + 1),
    )
    // retrying training must not create a second machine
    expect(calls.filter((c) => c.url.endsWith('/api/v1/assets')).length).toBe(1)
  })
})
