import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { CAPABILITIES, renderRoute, stubRoutes } from '../test/harness'
import { WorkOrderDetailScreen } from './WorkOrderDetail'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const asset = {
  id: 'a1', factory_id: 'f', name: 'CNC-02', asset_type: 'cnc-mill',
  criticality: 'high', location: 'Lini A', status: 'active', specs: {},
}

const analysis = {
  id: 'run-1', status: 'succeeded', engine_mode: 'ai_engine', error: null, error_code: null,
  request_snapshot: null,
  result: {
    health_score: 48, health_summary: 'Degradasi bearing terdeteksi.',
    anomalies: [{ tag: 'torque_nm', observed: 58.7, expected_range: [39, 41], severity: 'high', method: 'iqr' }],
    defects: [{ image: 'x.png', subject: 'product', score: 1, threshold: 0.5, label: 'defect', severity: 'high', region: null, heatmap_path: null, method: 'patchcore', phase: 'finishing' }],
    qc_by_phase: [], root_causes: [{ cause: 'Bearing aus', confidence: 0.82, evidence: [] }],
    recommendation: 'Ganti bearing', priority: 'high', recommended_window: null,
    explanation: '', blockers: [], work_order: null, sources: [],
  },
}

const order = {
  id: 'wo-1', factory_id: 'f', asset_id: 'a1', analysis_id: 'run-1',
  title: 'Ganti bearing', description: 'Ganti bearing spindle', priority: 'high',
  status: 'in_progress', created_at: '2026-08-25T02:00:00Z', updated_at: '2026-08-25T02:00:00Z',
  assigned_technician: 'Budi', scheduled_start: '2026-08-26T06:00:00Z',
  scheduled_end: '2026-08-26T08:00:00Z', schedule_note: null,
  details_json: {
    title: 'Ganti bearing', steps: ['Matikan mesin'], parts: ['SKF-6204'],
    est_duration_h: 2, required_skills: ['mekanik'], safety_notes: [],
    result_attempts: [{
      result: { work_done: 'dibersihkan', findings: 'kotor', parts_used: [], evidence: [] },
      verification: { verdict: 'not_resolved', evidence: [], follow_up: ['ganti bearing'] },
      submitted_at: '2026-08-25T03:00:00Z', verified_at: '2026-08-25T03:30:00Z',
    }],
  },
  technician_result_json: { work_done: 'bearing diganti', findings: 'aus', parts_used: ['SKF-6204'], evidence: [] },
  result_submitted_at: '2026-08-25T05:00:00Z',
  verification_json: null,
}

function render() {
  stubRoutes({
    '/config/capabilities': CAPABILITIES,
    '/api/v1/work-orders': [order],
    '/api/v1/assets/a1': asset,
    '/api/v1/analyses/run-1': analysis,
    '/api/v1/business-context': { production_schedule: null, inventory: [], technicians: [] },
  })
  return renderRoute('/work-orders/wo-1', '/work-orders/:id', <WorkOrderDetailScreen />)
}

describe('Work order detail — the evidence, not just the task', () => {
  it('names the machine the job is for', async () => {
    render()
    expect(await screen.findByText('CNC-02')).toBeTruthy()
    expect(screen.getByText('cnc-mill')).toBeTruthy()
    expect(screen.getByText('Lini A')).toBeTruthy()
  })

  it('carries the analysis that caused it, with a way back to it', async () => {
    render()
    expect(await screen.findByText('Degradasi bearing terdeteksi.')).toBeTruthy()
    expect(screen.getByText('48')).toBeTruthy()
    expect(screen.getByText(/Bearing aus/)).toBeTruthy()
    expect(screen.getByText('82%')).toBeTruthy()
    expect(screen.getByText(/1 anomali sensor · 1 defect visual/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Lihat analisis' }).getAttribute('href'))
      .toBe('/analysis/run-1')
  })

  it('shows the assignment', async () => {
    render()
    expect(await screen.findByText(/Budi/)).toBeTruthy()
  })

  it('keeps the rejected report next to the one that replaced it', async () => {
    render()
    expect(await screen.findByText(/Percobaan 1 — ditolak/)).toBeTruthy()
    expect(screen.getByText('dibersihkan')).toBeTruthy()
    expect(screen.getByText('Belum terselesaikan')).toBeTruthy()
    expect(screen.getByText('Tindak lanjut: ganti bearing')).toBeTruthy()
    // the current attempt, still awaiting a verdict
    expect(screen.getByText(/Percobaan 2/)).toBeTruthy()
    expect(screen.getByText('bearing diganti')).toBeTruthy()
    expect(screen.getByText('Menunggu verifikasi.')).toBeTruthy()
  })
})
