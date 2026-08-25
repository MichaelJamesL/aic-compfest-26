import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { CAPABILITIES, calls, renderRoute, stubRoutes } from '../test/harness'
import { BusinessContextScreen } from './BusinessContext'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const saved = {
  production_schedule: { work_time: { monday: { start: '06:00:00', end: '14:00:00' } } },
  inventory: [
    { id: 'tnmg', name: 'insert TNMG', stock: 3, unit: 'pcs', min_stock: 2, eta: '2 hari', asset_ids: ['a1'] },
  ],
  technicians: [
    {
      name: 'Budi',
      role: 'mekanik',
      specialty: null,
      work_time: { monday: { start: '06:00:00', end: '14:00:00' } },
      occupied_time: { monday: [{ start: '08:00:00', end: '12:00:00' }] },
    },
  ],
}

const assets = [
  { id: 'a1', name: 'CNC-02', asset_type: 'cnc-mill', criticality: 'high', location: null, status: 'active', specs: {}, factory_id: 'f' },
  { id: 'a2', name: 'Pump 1', asset_type: 'pump', criticality: 'medium', location: null, status: 'active', specs: {}, factory_id: 'f' },
]

function render(context: unknown) {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/assets': assets,
    '/api/v1/business-context': (init: RequestInit | undefined) =>
      init?.method === 'PUT' ? JSON.parse(String(init.body)) : context,
  })
  return renderRoute('/business-context', '/business-context', <BusinessContextScreen />)
}

const empty = { production_schedule: null, inventory: [], technicians: [] }

async function save() {
  const before = calls.filter((c) => c.method === 'PUT').length
  fireEvent.click(screen.getByRole('button', { name: /Simpan konteks/ }))
  const puts = () => calls.filter((c) => c.method === 'PUT')
  await waitFor(() => expect(puts().length).toBe(before + 1))
  return puts().at(-1)!.body as Record<string, any>
}

describe('Konteks bisnis — factory-wide, set once', () => {
  it('loads what the factory already saved, times trimmed to what the control speaks', async () => {
    render(saved)
    expect((await screen.findByLabelText('Nama teknisi 1')).getAttribute('value')).toBe('Budi')
    expect(screen.getByLabelText('Produksi Senin mulai').getAttribute('value')).toBe('06:00')
    expect(screen.getByLabelText('Teknisi 1 sibuk Senin selesai').getAttribute('value')).toBe('12:00')
    expect(screen.getByLabelText('Nama sparepart 1').getAttribute('value')).toBe('insert TNMG')
  })

  it('sends only complete day pairs — a half-filled row is not a constraint', async () => {
    render(empty)
    fireEvent.change(await screen.findByLabelText('Produksi Senin mulai'), { target: { value: '06:00' } })
    fireEvent.change(screen.getByLabelText('Produksi Senin selesai'), { target: { value: '14:00' } })
    // Selasa only opens — no closing time, so it must not travel.
    fireEvent.change(screen.getByLabelText('Produksi Selasa mulai'), { target: { value: '06:00' } })

    const sent = await save()
    expect(Object.keys(sent.production_schedule.work_time)).toEqual(['monday'])
    expect(sent.production_schedule.work_time.monday).toEqual({ start: '06:00', end: '14:00' })
  })

  it('adds a technician, edits it, and keeps the roster it already had', async () => {
    render(saved)
    fireEvent.click(await screen.findByRole('button', { name: /Tambah teknisi/ }))
    fireEvent.change(screen.getByLabelText('Nama teknisi 2'), { target: { value: 'Sari' } })
    fireEvent.change(screen.getByLabelText('Spesialisasi teknisi 2'), { target: { value: 'panel listrik' } })
    fireEvent.change(screen.getByLabelText('Teknisi 2 kerja Jumat mulai'), { target: { value: '08:00' } })
    fireEvent.change(screen.getByLabelText('Teknisi 2 kerja Jumat selesai'), { target: { value: '16:00' } })
    // editing the one that was already there must not disturb the new one
    fireEvent.change(screen.getByLabelText('Peran teknisi 1'), { target: { value: 'senior mekanik' } })

    const sent = await save()
    expect(sent.technicians.map((t: any) => t.name)).toEqual(['Budi', 'Sari'])
    expect(sent.technicians[0].role).toBe('senior mekanik')
    expect(sent.technicians[0].occupied_time.monday).toEqual([{ start: '08:00', end: '12:00' }])
    expect(sent.technicians[1]).toMatchObject({
      specialty: 'panel listrik',
      role: 'teknisi',
      work_time: { friday: { start: '08:00', end: '16:00' } },
    })
  })

  it('removes a technician, and drops the ones never named', async () => {
    render(saved)
    fireEvent.click(await screen.findByRole('button', { name: /Tambah teknisi/ }))
    expect((await save()).technicians.map((t: any) => t.name)).toEqual(['Budi'])

    fireEvent.click(screen.getByRole('button', { name: 'Hapus teknisi 1' }))
    expect((await save()).technicians).toEqual([])
  })

  it('names a new spare part by its own name, and drops the ones never typed', async () => {
    render(empty)
    fireEvent.click(await screen.findByRole('button', { name: /Tambah sparepart/ }))
    fireEvent.click(screen.getByRole('button', { name: /Tambah sparepart/ }))
    fireEvent.change(screen.getByLabelText('Nama sparepart 1'), { target: { value: 'seal spindle' } })
    fireEvent.change(screen.getByLabelText('Stok sparepart 1'), { target: { value: '4' } })

    const sent = await save()
    expect(sent.inventory).toEqual([
      { id: 'seal-spindle', name: 'seal spindle', stock: 4, unit: 'pcs', min_stock: null, eta: null, asset_ids: [] },
    ])
  })

  it('links a part to several machines, and keeps the links it loaded', async () => {
    render(saved)
    const cnc = (await screen.findByLabelText('CNC-02 pakai sparepart 1')) as HTMLInputElement
    const pump = screen.getByLabelText('Pump 1 pakai sparepart 1') as HTMLInputElement
    expect([cnc.checked, pump.checked]).toEqual([true, false])

    fireEvent.click(pump)
    expect((await save()).inventory[0].asset_ids).toEqual(['a1', 'a2'])

    fireEvent.click(cnc)
    expect((await save()).inventory[0].asset_ids).toEqual(['a2'])
  })
})
