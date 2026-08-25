import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { AnalysisResultScreen } from './AnalysisResult'
import type { AnalysisDetail } from '../api/types'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

/** The payload shape captured from the running server — see docs/API.md. */
const succeeded: AnalysisDetail = {
  id: '6f597d34-299b-416e-ba97-6cb55ba41363',
  status: 'succeeded',
  engine_mode: 'ai_engine',
  error_code: null,
  error: null,
  request_snapshot: {
    asset: { id: 'a1', name: 'CNC-02', type: 'cnc-mill', criticality: 'high' },
    readings: [],
    history: [],
    condition: 'chatter',
    business: {
      production_schedule: { work_time: { monday: { start: '06:00:00', end: '14:00:00' } } },
      inventory: [],
      technicians: [{ name: 'Budi', role: 'mekanik', specialty: null, work_time: {}, occupied_time: {} }],
      operator_report: null,
    },
    tier: 'professional',
    trigger: 'manual',
  },
  result: {
    health_score: 48,
    health_summary: 'Significant degradation.',
    anomalies: [
      { tag: 'torque_nm', observed: 58.7, expected_range: [39.4, 41.2], severity: 'high', method: 'iqr' },
    ],
    defects: [],
    root_causes: [
      { cause: 'Keausan insert', confidence: 0.7, evidence: ['torque_nm anomaly'] },
    ],
    recommendation: 'Ganti insert.',
    priority: 'high',
    recommended_window: 'dalam 48 jam',
    explanation: 'Torque melewati ambang SOP.',
    blockers: ['insert TNMG ETA 2 hari'],
    work_order: {
      title: 'Ganti insert dan verifikasi runout',
      steps: ['Isolasi mesin', 'Ganti insert'],
      parts: ['TNMG160408'],
      est_duration_h: 3,
      required_skills: ['mekanik'],
      safety_notes: ['Lockout/tagout sebelum bekerja'],
    },
    tier: 'professional',
    model: 'deepseek-chat',
    sources: ['SOP-CNC-04#3'],
  },
}

function stubFetch(body: unknown, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok,
      status: ok ? 200 : 404,
      headers: new Headers(),
      json: async () => body,
    })),
  )
}

function renderScreen() {
  return render(
    <MemoryRouter initialEntries={['/analysis/6f597d34']}>
      <Routes>
        <Route path="/analysis/:id" element={<AnalysisResultScreen />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnalysisResult — succeeded', () => {
  beforeEach(() => stubFetch(succeeded))

  it('shows the deterministic health score and its severity band', async () => {
    renderScreen()
    expect(await screen.findByText('48')).toBeTruthy()
    expect(screen.getByText('Menurun')).toBeTruthy()
  })

  it('marks the numbers as computed, not written by the model', async () => {
    renderScreen()
    await screen.findByText('48')
    expect(screen.getAllByText(/Dihitung deterministik/).length).toBeGreaterThan(0)
  })

  it('renders the anomaly with its normal range and method', async () => {
    renderScreen()
    expect(await screen.findByText('torque_nm')).toBeTruthy()
    expect(screen.getByText('39.4 – 41.2')).toBeTruthy()
    expect(screen.getByText('IQR')).toBeTruthy()
  })

  it('lists the sources actually used', async () => {
    renderScreen()
    expect(await screen.findByText('SOP-CNC-04#3')).toBeTruthy()
  })

  it('shows the blocker and the fixed objective-function wording', async () => {
    renderScreen()
    expect(await screen.findByText('insert TNMG ETA 2 hari')).toBeTruthy()
    expect(screen.getByText(/meminimalkan ekspektasi biaya downtime/i)).toBeTruthy()
  })

  it('states the autonomy boundary on the approval bar', async () => {
    renderScreen()
    expect(await screen.findByText(/AI mengusulkan dan menyiapkan/)).toBeTruthy()
  })

  it('does not claim stub output when the real engine ran', async () => {
    renderScreen()
    await screen.findByText('48')
    expect(screen.queryByText(/stub offline/i)).toBeNull()
  })
})

describe('AnalysisResult — partial input', () => {
  it('names the missing inputs and what they cost rather than hiding the card', async () => {
    stubFetch(succeeded)
    renderScreen()
    expect(await screen.findByText(/Citra QC/)).toBeTruthy()
    expect(screen.getByText(/Belum ada citra QC pada analisis ini/)).toBeTruthy()
  })

  it('says so plainly when no document was retrieved', async () => {
    stubFetch({
      ...succeeded,
      result: { ...succeeded.result!, sources: [] },
    })
    renderScreen()
    expect(
      await screen.findByText(/tidak memiliki dasar dokumen yang bisa dikutip/i),
    ).toBeTruthy()
  })

  it('reports no anomalies as a result, not as an empty state', async () => {
    stubFetch({ ...succeeded, result: { ...succeeded.result!, anomalies: [] } })
    renderScreen()
    expect(await screen.findByText('Tidak ada anomali di luar rentang normal.')).toBeTruthy()
  })
})

describe('AnalysisResult — offline stub', () => {
  it('never presents stub output as model output', async () => {
    stubFetch({ ...succeeded, engine_mode: 'offline_stub' })
    renderScreen()
    expect(await screen.findByText(/stub offline, bukan dari model/i)).toBeTruthy()
  })
})

describe('AnalysisResult — failed', () => {
  // HTTP is 201/200 even when the run failed. docs/API.md gotcha 5.
  it('handles a failed run that arrived with a success status code', async () => {
    stubFetch({
      ...succeeded,
      status: 'failed',
      result: null,
      engine_mode: 'unavailable',
      error_code: 'AI_ENGINE_UNAVAILABLE',
    })
    renderScreen()
    expect(await screen.findByText(/Mesin analisis tidak tersedia/)).toBeTruthy()
    expect(screen.getByText(/AI_ENGINE_UNAVAILABLE/)).toBeTruthy()
  })
})

describe('AnalysisResult — error', () => {
  it('maps the error envelope to Indonesian and surfaces the request id', async () => {
    stubFetch(
      {
        error: {
          code: 'NOT_FOUND',
          message: 'analysis_not_found',
          details: [],
          request_id: 'req-42',
        },
      },
      false,
    )
    renderScreen()
    await waitFor(() => expect(screen.getByText('Analisis tidak ditemukan.')).toBeTruthy())
    expect(screen.getByText(/req-42/)).toBeTruthy()
  })

  it('counts the deviating images without claiming to know the defect type', async () => {
    stubFetch({ ...succeeded, result: { ...succeeded.result, defects: [
      { image: 'a.png', subject: 'product', score: 0.9, threshold: 0.5, label: 'defect',
        severity: 'high', region: null, heatmap_path: null, method: 'patchcore',
        defect_class: null, class_confidence: null },
    ] } })
    renderScreen()
    expect(await screen.findByText(/citra menyimpang dari unit normal/)).toBeTruthy()
    // no defect type is named anywhere: this version detects, it does not classify
    expect(screen.queryByText(/scratch|thread|failure mode/i)).toBeNull()
  })

  it('counts QC findings that arrived as a batch, not only asset-level ones', async () => {
    const finding = (label: string, cls: string | null) => ({
      image: `${label}.png`, subject: 'product', score: 0.9, threshold: 0.5,
      label, severity: 'high', region: null, heatmap_path: null, method: 'patchcore',
      defect_class: cls, class_confidence: cls ? 0.9 : null,
    })
    stubFetch({ ...succeeded, result: { ...succeeded.result, defects: [], qc_by_phase: [{
      phase: 'finishing', asset_id: 'a1', product: 'metal-nut-4lug',
      inspected: 3, defects: 2, defect_rate: 0.67,
      findings: [finding('defect', 'thread_side'), finding('defect', 'thread_side'), finding('ok', null)],
    }] } })
    renderScreen()

    // the card read result.defects only, so a batch of images reported "none"
    expect(await screen.findByText(/2 dari 3 citra ditandai defect/)).toBeTruthy()
    expect(screen.queryByText(/Belum ada citra QC pada analisis ini/)).toBeNull()
    expect(screen.getByText('defect rate')).toBeTruthy()
  })

  it('says outright when every inspected image failed', async () => {
    const finding = (label: string) => ({
      image: `${label}.png`, subject: 'product', score: 0.9, threshold: 0.5,
      label, severity: 'high', region: null, heatmap_path: null, method: 'patchcore',
      defect_class: null, class_confidence: null,
    })
    stubFetch({ ...succeeded, result: { ...succeeded.result, defects: [], qc_by_phase: [{
      phase: 'finishing', asset_id: 'a1', product: 'metal-nut-4lug',
      inspected: 8, defects: 8, defect_rate: 1,
      findings: Array.from({ length: 8 }, () => finding('defect')),
    }] } })
    renderScreen()

    // "8 dari 8" reads as a tally; a total failure should say so in words
    expect(await screen.findByText(/Semua 8 citra ditandai defect/)).toBeTruthy()
    expect(screen.getByText('100%')).toBeTruthy()
  })
})
