import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { CAPABILITIES, renderRoute, stubRoutes } from '../test/harness'
import { SetupScreen } from './Setup'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const documents = [
  {
    id: 'd1', title: 'SOP-CNC-04.txt', kind: 'sop', filename: 'SOP-CNC-04.txt',
    size_bytes: 2048, ingestion_status: 'pending', ingestion_error: null,
  },
  {
    id: 'd2', title: 'HISTORI.txt', kind: 'log', filename: 'HISTORI.txt',
    size_bytes: 5_242_880, ingestion_status: 'ready', ingestion_error: null,
  },
  {
    id: 'd3', title: 'MANUAL.pdf', kind: 'manual', filename: 'MANUAL.pdf',
    size_bytes: 900, ingestion_status: 'failed', ingestion_error: 'No module named src',
  },
]

function render(docs: unknown = documents, assets: unknown = [{ id: 'a1', name: 'CNC-02' }]) {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/knowledge/documents': docs,
    '/api/v1/assets': assets,
  })
  return renderRoute('/setup', '/setup', <SetupScreen />)
}

describe('Setup', () => {
  it('offers the three knowledge inputs the FR requires', async () => {
    render()
    expect(await screen.findByText('Daftar mesin')).toBeTruthy()
    expect(screen.getByText('SOP & manual')).toBeTruthy()
    expect(screen.getByText('Histori maintenance')).toBeTruthy()
  })

  // A pending document is not in the corpus and cannot be cited. Making that
  // visible is load-bearing, not cosmetic. SCREENS.md §1.
  it('distinguishes the three ingestion states by label, not colour alone', async () => {
    render()
    expect(await screen.findByText('Belum diindeks')).toBeTruthy()
    expect(screen.getByText('Terindeks')).toBeTruthy()
    expect(screen.getByText('Gagal')).toBeTruthy()
  })

  it('warns that un-indexed documents will not appear as sources', async () => {
    render()
    expect(
      await screen.findByText(/belum masuk knowledge base dan tidak akan muncul/i),
    ).toBeTruthy()
  })

  it('offers Indeks for pending and Ulangi for failed, but nothing for ready', async () => {
    render()
    expect(await screen.findByText('Indeks')).toBeTruthy()
    expect(screen.getByText('Ulangi')).toBeTruthy()
    expect(screen.getAllByText('Indeks')).toHaveLength(1)
  })

  it('shows the failure reason on the failed row', async () => {
    render()
    const failed = await screen.findByTitle('No module named src')
    expect(failed.textContent).toBe('Gagal')
  })

  it('formats sizes in human units', async () => {
    render()
    expect(await screen.findByText('2 KB')).toBeTruthy()
    expect(screen.getByText('5.0 MB')).toBeTruthy()
  })

  it('tells the user what to do when there are no documents', async () => {
    render([])
    expect(await screen.findByText(/Unggah SOP dan histori agar analisis punya dasar/i)).toBeTruthy()
  })

  it('imports structured maintenance history and displays row errors', async () => {
    const view = render()
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/knowledge/documents': documents,
      '/api/v1/assets': [{ id: 'a1', name: 'CNC-02' }],
      '/api/v1/maintenance-records/import': {
        imported: 1,
        errors: [{ row: 3, reason: 'missing_action' }],
      },
    })
    const input = view.container.querySelector('input[accept=".csv,.xlsx"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['asset_id,action'], 'history.csv', { type: 'text/csv' })] } })
    expect(await screen.findByText(/1 catatan histori diimpor/)).toBeTruthy()
    expect(screen.getByText('Baris 3: missing_action')).toBeTruthy()
  })

  it('keeps a generic history document upload alongside structured import', async () => {
    const view = render()
    expect(view.container.querySelector('input[accept=".txt,.md,.csv,.json"]')).toBeTruthy()
    expect(screen.getByText('Unggah berkas histori')).toBeTruthy()
  })

  it('surfaces a load failure with a retry', async () => {
    stubRoutes({ '/config/capabilities': CAPABILITIES }, {})
    renderRoute('/setup', '/setup', <SetupScreen />)
    await waitFor(() => expect(screen.getByText('Coba lagi')).toBeTruthy())
  })
})
