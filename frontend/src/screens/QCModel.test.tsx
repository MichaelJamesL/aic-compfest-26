import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { CAPABILITIES, calls, renderRoute, stubRoutes } from '../test/harness'
import { QCModelScreen } from './QCModel'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const assets = [
  { id: 'a1', factory_id: 'f', name: 'CNC-02', asset_type: 'cnc-mill', criticality: 'high', location: null, status: 'active', specs: {} },
]

function render(models: unknown = [], routes: Record<string, unknown> = {}) {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/assets': assets,
    '/api/v1/models': models,
    '/api/v1/assets/a1/models': { asset_id: 'a1', product: 'metal-nut-4lug', bank_path: '/b.pt', images_used: 2, flagged_in_training: 0 },
    ...routes,
  })
  return renderRoute('/qc-model', '/qc-model', <QCModelScreen />)
}

function drop(files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  fireEvent.change(input)
}

const image = (name: string) => new File(['x'], name, { type: 'image/png' })

describe('Model QC — train from photos of good units', () => {
  it('will not train without a machine and images', async () => {
    render()
    const button = await screen.findByRole('button', { name: /Latih model/ })
    expect((button as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Mesin'), { target: { value: 'a1' } })
    expect((button as HTMLButtonElement).disabled).toBe(true)

    drop([image('good.png')])
    expect((button as HTMLButtonElement).disabled).toBe(false)
  })

  it('names the product explicitly, defaulting to the machine type', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Mesin'), { target: { value: 'a1' } })
    drop([image('a.png'), image('b.png')])
    fireEvent.click(screen.getByRole('button', { name: /Latih model/ }))

    await waitFor(() => expect(calls.some((c) => c.url.includes('/a1/models'))).toBe(true))
    const sent = calls.find((c) => c.url.includes('/a1/models'))!.body as FormData
    expect(sent.get('product')).toBe('cnc-mill')
    expect(sent.getAll('files')).toHaveLength(2)
    expect(await screen.findByText(/dilatih dari 2 citra/)).toBeTruthy()
  })

  it('sends the product that was typed, not the machine type', async () => {
    render()
    fireEvent.change(await screen.findByLabelText('Mesin'), { target: { value: 'a1' } })
    fireEvent.change(screen.getByLabelText('Produk'), { target: { value: 'metal-nut-4lug' } })
    drop([image('a.png')])
    fireEvent.click(screen.getByRole('button', { name: /Latih model/ }))

    await waitFor(() => expect(calls.some((c) => c.url.includes('/a1/models'))).toBe(true))
    expect((calls.find((c) => c.url.includes('/a1/models'))!.body as FormData).get('product'))
      .toBe('metal-nut-4lug')
  })

  it('warns that training replaces a model the product already has', async () => {
    render([{ product: 'cnc-mill', size_bytes: 1024, trained_at: '2026-08-25T12:00:00Z' }])
    expect(await screen.findByText('cnc-mill')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Mesin'), { target: { value: 'a1' } })
    expect(await screen.findByText(/Melatih ulang menggantinya/)).toBeTruthy()
  })

  it('says what having no model costs', async () => {
    render()
    expect(await screen.findByText(/citra QC tidak diperiksa/)).toBeTruthy()
  })

  it('warns when the model flags its own reference images', async () => {
    render([], { '/api/v1/assets/a1/models': {
      asset_id: 'a1', product: 'cnc-mill', bank_path: '/b.pt', images_used: 8, flagged_in_training: 6,
    } })
    fireEvent.change(await screen.findByLabelText('Mesin'), { target: { value: 'a1' } })
    drop([image('a.png')])
    fireEvent.click(screen.getByRole('button', { name: /Latih model/ }))

    // a bank fitted on defective references marks everything defective, silently
    const warning = await screen.findByText(/Latih ulang dengan citra unit yang benar-benar bagus/)
    // interpolated numbers split the text node, so match on the rendered content
    expect(warning.textContent).toMatch(/menandai 6 dari 8 citra referensinya sendiri/)
  })
})
