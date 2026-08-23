import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { CAPABILITIES, calls, renderRoute, stubRoutes } from '../test/harness'
import { ExecuteScreen } from './Execute'
import { ReportScreen } from './Report'
import { CompareScreen } from './Compare'
import { setIdentity } from '../api/client'
import type { AnalysisDetail, TechnicianResult, WorkOrder } from '../api/types'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  setIdentity('demo-engineer')
})

const workOrder: WorkOrder = {
  id: 'wo-1', factory_id: 'f', asset_id: 'a1', analysis_id: 'run-1',
  title: 'Ganti insert', description: '', priority: 'high', status: 'in_progress',
  details_json: {
    title: 'Ganti insert',
    steps: ['Isolasi mesin', 'Ganti insert', 'Verifikasi runout'],
    parts: ['TNMG160408'], est_duration_h: 3, required_skills: ['mekanik'],
    safety_notes: ['Lockout/tagout'],
  },
  created_at: '2026-08-22T20:38:09', updated_at: '2026-08-22T20:38:09',
}

const technicianResult: TechnicianResult = {
  work_done: 'Bearing replaced', findings: 'Noise resolved', parts_used: [], evidence: [],
}

const analysis = (over: Partial<AnalysisDetail['result']> = {}, snapshot?: unknown): AnalysisDetail => ({
  id: 'run-1', status: 'succeeded', engine_mode: 'ai_engine', error_code: null, error: null,
  request_snapshot: (snapshot ?? {
    asset: { id: 'a1', name: 'CNC-02', type: 'cnc-mill', criticality: 'high' },
    readings: [], history: [], condition: 'chatter',
    business: { production_schedule: null, spareparts: [], sparepart_eta: null, technicians_available: null, operator_report: null },
    tier: 'starter', trigger: 'manual',
  }) as AnalysisDetail['request_snapshot'],
  result: {
    health_score: 72, health_summary: '', anomalies: [], defects: [],
    root_causes: [{ cause: 'Keausan insert', confidence: 0.6, evidence: [] }],
    recommendation: '', priority: 'medium', recommended_window: null,
    explanation: '', blockers: [], work_order: null, tier: 'starter',
    model: 'deepseek-chat', sources: [], ...over,
  },
})

describe('Execute — technician form', () => {
  function render() {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders': [workOrder],
      '/api/v1/work-orders/wo-1/result': { id: 'wo-1', status: 'in_progress', result: {}, result_submitted_at: 'now' },
    })
    return renderRoute('/work-orders/wo-1/execute', '/work-orders/:id/execute', <ExecuteScreen />)
  }

  it('lists every SOP step as a checklist item', async () => {
    render()
    expect(await screen.findByLabelText('Isolasi mesin')).toBeTruthy()
    expect(screen.getByLabelText('Verifikasi runout')).toBeTruthy()
    expect(screen.getByText('0 dari 3 langkah ditandai selesai.')).toBeTruthy()
  })

  it('collects findings and parts used', async () => {
    render()
    expect(await screen.findByLabelText('Temuan di lapangan')).toBeTruthy()
    expect(screen.getByLabelText('Sparepart terpakai')).toBeTruthy()
  })

  // The autonomy boundary: submitting a result must not close the work order.
  it('states that submitting does not complete the work order', async () => {
    render()
    expect(await screen.findByText(/tidak menutup work order/i)).toBeTruthy()
    expect(screen.getByText(/bukan menyatakan selesai sendiri/i)).toBeTruthy()
  })

  it('submits the technician result using the backend payload', async () => {
    setIdentity('demo-technician')
    render()
    const submit = (await screen.findByRole('button', { name: /Kirim hasil pekerjaan/ })) as HTMLButtonElement
    expect(submit.disabled).toBe(false)
    fireEvent.change(screen.getByLabelText('Temuan di lapangan'), { target: { value: 'Noise resolved' } })
    fireEvent.click(submit)
    await waitFor(() => expect(calls.find((call) => call.url.endsWith('/result'))?.body).toEqual({
      work_done: '', findings: 'Noise resolved', parts_used: [], evidence: [],
    }))
  })

  it('tells a non-technician to switch roles', async () => {
    render()
    expect(await screen.findByText(/diisi oleh teknisi — ganti peran/i)).toBeTruthy()
  })
})

describe('Report — verification', () => {
  function render() {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders': [workOrder],
      '/api/v1/work-orders/wo-1/report': {
        ok: false,
        status: 404,
        headers: new Headers(),
        json: async () => ({ error: { code: 'NOT_FOUND', message: 'report_not_found', details: [], request_id: 'req-0' } }),
      },
    })
    return renderRoute('/work-orders/wo-1/report', '/work-orders/:id/report', <ReportScreen />)
  }

  it('calls the report route and shows the three verdicts before verification', async () => {
    render()
    expect(await screen.findByText('Masalah terselesaikan')).toBeTruthy()
    expect(screen.getByText('Sebagian terselesaikan')).toBeTruthy()
    expect(screen.getByText('Belum terselesaikan')).toBeTruthy()
  })

  it('offers synchronous verification from the report screen', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders': [{ ...workOrder, technician_result_json: technicianResult }],
      '/api/v1/work-orders/wo-1/report': {
        ok: false, status: 404, headers: new Headers(),
        json: async () => ({ error: { code: 'NOT_FOUND', message: 'report_not_found', details: [], request_id: 'req-0' } }),
      },
    })
    renderRoute('/work-orders/wo-1/report', '/work-orders/:id/report', <ReportScreen />)
    fireEvent.click(await screen.findByRole('button', { name: 'Jalankan verifikasi' }))
    await waitFor(() => expect(calls.some((call) => call.url.endsWith('/verify') && call.method === 'POST')).toBe(true))
  })

  it('requires a submitted technician result before offering verification', async () => {
    render()
    expect(await screen.findByText(/hasil pekerjaan teknisi diperlukan/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Jalankan verifikasi' })).toBeNull()
    expect(calls.some((call) => call.url.endsWith('/verify'))).toBe(false)
  })

  it('renders the backend report payload after verification', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders': [workOrder],
      '/api/v1/work-orders/wo-1/report': {
        work_order_id: 'wo-1', asset_id: 'a1', problem: 'Bearing noise', action: 'Bearing replaced',
        findings: 'Noise resolved',
        verdict: { verdict: 'resolved', evidence: ['photo-1'], follow_up: [] },
        final_asset_state: { status: 'active', work_order_status: 'completed' },
      },
    })
    renderRoute('/work-orders/wo-1/report', '/work-orders/:id/report', <ReportScreen />)
    expect(await screen.findByText('Masalah terselesaikan')).toBeTruthy()
    expect(screen.getByText('Bearing replaced')).toBeTruthy()
    expect(screen.getByText('Noise resolved')).toBeTruthy()
  })

  it('offers JSON and CSV exports with safe format-specific filenames', async () => {
    const blob = new Blob(['export'], { type: 'text/csv' })
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/work-orders': [workOrder],
      '/api/v1/work-orders/wo-1/report': {
        work_order_id: 'wo-1', asset_id: 'a1', problem: 'Bearing noise', action: 'Bearing replaced',
        findings: 'Noise resolved', verdict: { verdict: 'resolved', evidence: [], follow_up: [] },
        final_asset_state: { status: 'active', work_order_status: 'completed' },
      },
      '/api/v1/work-orders/wo-1/export?format=json': {
        ok: true, status: 200, headers: new Headers(), json: async () => ({}), blob: async () => blob,
      },
      '/api/v1/work-orders/wo-1/export?format=csv': {
        ok: true, status: 200, headers: new Headers(), json: async () => ({}), blob: async () => blob,
      },
    })
    const createObjectURL = vi.fn(() => 'blob:test')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })
    const downloads: string[] = []
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download)
    })
    renderRoute('/work-orders/wo-1/report', '/work-orders/:id/report', <ReportScreen />)
    fireEvent.click(await screen.findByRole('button', { name: 'Ekspor JSON' }))
    await waitFor(() => expect(calls.some((call) => call.url.includes('format=json'))).toBe(true))
    await waitFor(() => expect(downloads).toContain('work-order-wo-1.json'))
    fireEvent.click(screen.getByRole('button', { name: 'Ekspor CSV' }))
    await waitFor(() => expect(calls.some((call) => call.url.includes('format=csv'))).toBe(true))
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalled()
    expect(downloads).toContain('work-order-wo-1.csv')
    expect(click).toHaveBeenCalledTimes(2)
  })
})

describe('Compare — graceful degradation', () => {
  it('carries the adoption sentence verbatim', async () => {
    stubRoutes({ '/config/capabilities': CAPABILITIES, '/api/v1/analyses/run-1': analysis() })
    renderRoute('/analysis/run-1/compare', '/analysis/:id/compare', <CompareScreen />)
    expect(
      await screen.findByText(
        /Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin lengkap input, makin dalam keputusannya\./,
      ),
    ).toBeTruthy()
  })

  it('asks for a second run when none is given', async () => {
    stubRoutes({ '/config/capabilities': CAPABILITIES, '/api/v1/analyses/run-1': analysis() })
    renderRoute('/analysis/run-1/compare', '/analysis/:id/compare', <CompareScreen />)
    expect(await screen.findByText(/Jalankan aset yang sama dua kali/)).toBeTruthy()
  })

  // The comparison is a 40-second video beat; typing a UUID into the address
  // bar is not a usable way to reach it.
  it('offers the asset\'s other runs in a picker instead of requiring a URL edit', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/assets/a1/analyses': [
        { id: 'run-1', status: 'succeeded', tier: 'starter', trigger: 'manual', created_at: '2026-08-22T10:00:00', health_score: 72, priority: 'medium', engine_mode: 'ai_engine' },
        { id: 'run-2', status: 'succeeded', tier: 'professional', trigger: 'manual', created_at: '2026-08-22T14:00:00', health_score: 48, priority: 'high', engine_mode: 'ai_engine' },
      ],
      '/api/v1/analyses/run-1': analysis(),
    })
    renderRoute('/analysis/run-1/compare', '/analysis/:id/compare', <CompareScreen />)

    // The asset id only becomes known once the first run loads, so the list
    // arrives on a second request.
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(2))
    const picker = screen.getByLabelText('Run B') as HTMLSelectElement
    // The run already open is not offered as its own comparison.
    expect([...picker.options].map((option) => option.value)).toEqual(['', 'run-2'])
    expect(picker.options[1].textContent).toContain('professional')
    expect(picker.options[1].textContent).toContain('48')
  })

  it('refuses to compare a run with itself', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/assets/a1/analyses': [],
      '/api/v1/analyses/run-1': analysis(),
    })
    renderRoute('/analysis/run-1/compare?with=run-1', '/analysis/:id/compare', <CompareScreen />)
    expect(await screen.findByText(/Belum ada run kedua untuk dibandingkan/)).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Run B' })).toBeNull()
  })

  it('says so plainly when the asset has only ever been analysed once', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/assets/a1/analyses': [
        { id: 'run-1', status: 'succeeded', tier: 'starter', trigger: 'manual', created_at: '2026-08-22T10:00:00', health_score: 72, priority: 'medium', engine_mode: 'ai_engine' },
      ],
      '/api/v1/analyses/run-1': analysis(),
    })
    renderRoute('/analysis/run-1/compare', '/analysis/:id/compare', <CompareScreen />)
    await waitFor(() =>
      expect(
        (screen.getByLabelText('Run B') as HTMLSelectElement).options[0].textContent,
      ).toMatch(/belum ada run lain/),
    )
    const picker = screen.getByLabelText('Run B') as HTMLSelectElement
    expect(picker.disabled).toBe(true)
    expect(picker.options[0].textContent).toMatch(/belum ada run lain/)
    // A navigation is a link, not a button — one anchor, one focus stop.
    expect(screen.getByRole('link', { name: 'Jalankan analisis kedua' })).toBeTruthy()
  })

  it('scores input coverage per run so the two columns differ visibly', async () => {
    const full = analysis({}, {
      asset: { id: 'a1', name: 'CNC-02', type: 'cnc-mill', criticality: 'high' },
      readings: [{}], history: [{}], condition: 'chatter',
      business: { production_schedule: 'Sen-Sab', spareparts: ['TNMG'], sparepart_eta: '2 hari', technicians_available: 2, operator_report: null },
      tier: 'professional', trigger: 'manual',
    })
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/analyses/run-1': analysis(),
      '/api/v1/analyses/run-2': { ...full, id: 'run-2' },
    })
    renderRoute('/analysis/run-1/compare?with=run-2', '/analysis/:id/compare', <CompareScreen />)
    // Scoped to headings: the run picker above also names both columns.
    expect(await screen.findByRole('heading', { name: 'Run A' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Run B' })).toBeTruthy()
    // Run A has only the manual condition; run B has everything but QC images.
    expect(screen.getByText('1/7 input')).toBeTruthy()
    expect(screen.getByText('6/7 input')).toBeTruthy()

    // Headline numbers render as metric cards: icon chip, title, value, caption.
    const headlines = screen.getAllByRole('heading', { level: 3, name: 'Skor kesehatan' })
    expect(headlines).toHaveLength(2)
    expect(screen.getAllByText('72')).toHaveLength(2)
    expect(screen.getAllByText('Perlu diperhatikan')).toHaveLength(2)
  })

  it('names the missing input where a section has nothing to show', async () => {
    stubRoutes({
      '/config/capabilities': CAPABILITIES,
      '/api/v1/analyses/run-1': analysis(),
      '/api/v1/analyses/run-2': { ...analysis(), id: 'run-2' },
    })
    renderRoute('/analysis/run-1/compare?with=run-2', '/analysis/:id/compare', <CompareScreen />)
    const missing = await screen.findAllByText(/jadwal produksi tidak tersedia pada run ini/)
    expect(missing).toHaveLength(2)
  })
})
