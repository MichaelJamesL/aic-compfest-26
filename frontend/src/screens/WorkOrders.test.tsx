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

  /**
   * A row that navigates has to look like it does before anyone hovers it:
   * hover is not an affordance on touch, and it does not show in a screenshot.
   */
  it('makes a navigating row visibly navigable', async () => {
    stubRoutes({ '/config/capabilities': CAPABILITIES, '/api/v1/work-orders': [order()] })
    const { container } = renderRoute('/work-orders', '/work-orders', <WorkOrdersScreen />)

    const title = await screen.findByRole('link', { name: 'Ganti insert dan verifikasi runout' })
    expect(title.getAttribute('href')).toBe('/work-orders/wo-1')
    // Underlined at rest, not only on hover.
    expect(title.className).toContain('underline')

    // The row itself reads as interactive, and the direction is shown.
    const row = title.closest('tr')!
    expect(row.className).toContain('hover:bg-surface-raised')
    expect(screen.getByRole('link', { name: 'Buka Ganti insert dan verifikasi runout' })).toBeTruthy()
    expect(container.querySelector('.sr-only')?.textContent).toBe('Buka')
  })
})

describe('Work order detail', () => {
  function render(status: WorkOrder['status'] = 'draft') {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders/wo-1/submit': order({ status: 'pending_approval' }),
      '/api/v1/work-orders/wo-1/approve': order({ status: 'approved' }),
      '/api/v1/work-orders/wo-1/reject': order({ status: 'rejected' }),
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

  // The AI proposes; a human decides. `submit` puts the draft in front of a
  // coordinator, and only then can it be approved.
  it('submits a draft for approval', async () => {
    render('draft')
    fireEvent.click(await screen.findByRole('button', { name: 'Ajukan persetujuan' }))
    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith('/submit') && c.method === 'POST')).toBe(true),
    )
    // Submitting is not approving.
    expect(calls.some((c) => c.url.endsWith('/approve'))).toBe(false)
  })

  it('lets a coordinator approve a pending work order', async () => {
    setIdentity('demo-manager')
    render('pending_approval')
    fireEvent.click(await screen.findByRole('button', { name: 'Setujui' }))
    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith('/approve') && c.method === 'POST')).toBe(true),
    )
  })

  it('requires a reason before a rejection can be sent', async () => {
    setIdentity('demo-manager')
    render('pending_approval')
    fireEvent.click(await screen.findByRole('button', { name: 'Tolak' }))

    const send = screen.getByRole('button', { name: 'Tolak work order' }) as HTMLButtonElement
    expect(send.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Alasan'), {
      target: { value: 'Sparepart belum datang.' },
    })
    expect((screen.getByRole('button', { name: 'Tolak work order' }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Tolak work order' }))

    await waitFor(() => {
      const call = calls.find((c) => c.url.endsWith('/reject'))
      expect(call?.body).toEqual({ reason: 'Sparepart belum datang.' })
    })
  })

  it('tells a non-coordinator that the decision is not theirs to make', async () => {
    setIdentity('demo-technician')
    render('pending_approval')
    const approve = (await screen.findByRole('button', { name: 'Setujui' })) as HTMLButtonElement
    const reject = screen.getByRole('button', { name: 'Tolak' }) as HTMLButtonElement
    expect(approve.disabled).toBe(true)
    expect(reject.disabled).toBe(true)
    expect(approve.getAttribute('title')).toMatch(/Hanya coordinator/)
  })

  it('shows why a rejected work order was rejected', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders': [
        order({
          status: 'rejected',
          details_json: { ...order().details_json, rejection_reason: 'Sparepart belum datang.' },
        }),
      ],
    })
    renderRoute('/work-orders/wo-1', '/work-orders/:id', <WorkOrderDetailScreen />)
    expect(await screen.findByText('Sparepart belum datang.')).toBeTruthy()
  })

  it('marks a rejected order as terminal on the state track', async () => {
    render('rejected')
    const track = await screen.findByLabelText('Status work order')
    // The happy path is greyed and the terminal state is appended to it.
    expect(within(track).getByText('Ditolak')).toBeTruthy()
    expect(within(track).queryByText('Selesai')).toBeTruthy()
  })
})
