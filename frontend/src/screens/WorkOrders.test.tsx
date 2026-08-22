import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { CAPABILITIES, calls, renderRoute, stubRoutes } from '../test/harness'
import { WorkOrdersScreen } from './WorkOrders'
import { WorkOrderDetailScreen } from './WorkOrderDetail'
import { setIdentity } from '../api/client'
import type { WorkOrder } from '../api/types'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  setIdentity('demo-engineer')
})

const order = (over: Partial<WorkOrder> = {}): WorkOrder => ({
  id: 'wo-1',
  factory_id: 'f',
  asset_id: 'a1',
  analysis_id: 'run-1',
  title: 'Ganti insert dan verifikasi runout',
  description: 'Torque melewati ambang SOP.',
  priority: 'high',
  status: 'draft',
  details_json: {
    title: 'Ganti insert',
    steps: ['Isolasi mesin', 'Ganti insert'],
    parts: ['TNMG160408'],
    est_duration_h: 3,
    required_skills: ['mekanik'],
    safety_notes: ['Lockout/tagout sebelum bekerja'],
  },
  created_at: '2026-08-22T20:38:09',
  updated_at: '2026-08-22T20:38:09',
  ...over,
})

describe('Work order list', () => {
  it('labels priority and status in words, not colour alone', async () => {
    stubRoutes({ '/config/capabilities': CAPABILITIES, '/api/v1/work-orders': [order()] })
    renderRoute('/work-orders', '/work-orders', <WorkOrdersScreen />)
    expect(await screen.findByText('Tinggi')).toBeTruthy()
    expect(screen.getByText('Draft')).toBeTruthy()
  })

  it('explains where work orders come from when there are none', async () => {
    stubRoutes({ '/config/capabilities': CAPABILITIES, '/api/v1/work-orders': [] })
    renderRoute('/work-orders', '/work-orders', <WorkOrdersScreen />)
    expect(await screen.findByText(/Work order dibuat dari hasil analisis/)).toBeTruthy()
  })
})

describe('Work order detail', () => {
  function render(status: WorkOrder['status'] = 'draft') {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders/wo-1/approve': order({ status: 'pending_approval' }),
      '/api/v1/work-orders': [order({ status })],
    })
    return renderRoute('/work-orders/wo-1', '/work-orders/:id', <WorkOrderDetailScreen />)
  }

  it('shows the SOP steps, parts, skills and safety notes', async () => {
    render()
    expect(await screen.findByText('Isolasi mesin')).toBeTruthy()
    expect(screen.getByText('TNMG160408')).toBeTruthy()
    expect(screen.getByText('mekanik')).toBeTruthy()
    expect(screen.getByText('Lockout/tagout sebelum bekerja')).toBeTruthy()
    expect(screen.getByText('3 jam')).toBeTruthy()
  })

  it('states the full autonomy boundary on the action bar', async () => {
    render()
    expect(
      await screen.findByText(
        /AI mengusulkan dan menyiapkan; coordinator menyetujui; teknisi mengeksekusi; AI memverifikasi bukti\./,
      ),
    ).toBeTruthy()
  })

  it('submits a draft for approval', async () => {
    render('draft')
    fireEvent.click(await screen.findByRole('button', { name: 'Ajukan persetujuan' }))
    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith('/approve') && c.method === 'POST')).toBe(true),
    )
  })

  // DEFECTS.md#wo-approve: nothing can reach `approved`. The UI must say why
  // rather than offering a button that silently 409s.
  it('disables approve and reject at pending_approval and names the backend gap', async () => {
    render('pending_approval')
    const approve = (await screen.findByRole('button', { name: 'Setujui' })) as HTMLButtonElement
    const reject = screen.getByRole('button', { name: 'Tolak' }) as HTMLButtonElement
    expect(approve.disabled).toBe(true)
    expect(reject.disabled).toBe(true)
    expect(screen.getByText(/pending_approval → approved/)).toBeTruthy()
    expect(screen.getByText(/DEFECTS.md#wo-approve/)).toBeTruthy()
  })

  it('tells a non-coordinator that approval is not theirs to give', async () => {
    setIdentity('demo-technician')
    render('pending_approval')
    const approve = await screen.findByRole('button', { name: 'Setujui' })
    expect(approve.getAttribute('title')).toMatch(/Hanya coordinator/)
  })

  it('marks a rejected order as terminal on the state track', async () => {
    render('rejected')
    const track = await screen.findByLabelText('Status work order')
    // The happy path is greyed and the terminal state is appended to it.
    expect(within(track).getByText('Ditolak')).toBeTruthy()
    expect(within(track).queryByText('Selesai')).toBeTruthy()
  })
})
