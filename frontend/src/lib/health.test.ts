import { describe, expect, it } from 'vitest'
import { healthSegments, healthSources, inputCoverage } from './health'
import type { AnalysisResult } from '../api/types'

const base: AnalysisResult = {
  health_score: 100,
  health_summary: '',
  anomalies: [],
  defects: [],
  root_causes: [],
  recommendation: '',
  priority: 'low',
  recommended_window: null,
  explanation: '',
  blockers: [],
  work_order: null,
  tier: 'professional',
  model: 'deepseek-chat',
  sources: [],
}

describe('healthSegments', () => {
  it('sums to 100 so the donut is a whole ring', () => {
    const result: AnalysisResult = {
      ...base,
      health_score: 48,
      anomalies: [
        { tag: 'torque_nm', observed: 92, expected_range: [58, 81], severity: 'high', method: 'iqr' },
      ],
    }
    const total = healthSegments(result).reduce((sum, s) => sum + s.value, 0)
    expect(total).toBe(100)
  })

  it('attributes an anomaly deduction to its own segment', () => {
    const result: AnalysisResult = {
      ...base,
      health_score: 80,
      anomalies: [
        { tag: 'a', observed: 1, expected_range: [0, 0], severity: 'high', method: 'iqr' },
      ],
    }
    const anomaly = healthSegments(result).find((s) => s.label === 'Anomali')
    expect(anomaly?.value).toBe(20) // HEALTH_WEIGHTS.anomaly.high in signals.py
  })

  it('ignores images labelled ok when attributing defect deductions', () => {
    const result: AnalysisResult = {
      ...base,
      health_score: 90,
      defects: [
        {
          image: 'a.png', subject: 'product', score: 0.1, threshold: 0.5, label: 'ok',
          severity: 'critical', region: null, heatmap_path: null, method: 'patchcore',
        },
      ],
    }
    expect(healthSegments(result).find((s) => s.label === 'Defect')).toBeUndefined()
  })

  it('drops empty segments so the ring has no zero-width slices', () => {
    expect(healthSegments(base).map((s) => s.label)).toEqual(['Sisa skor'])
  })
})

const reading = {
  id: 'r1', tag: 'torque_nm', value: 1, unit: 'nm',
  recorded_at: '2026-08-23T00:00:00Z', source: 'csv', external_id: null,
}

describe('inputCoverage', () => {
  it('reports everything missing for a null snapshot', () => {
    const coverage = inputCoverage(null)
    expect(coverage.every((item) => !item.present)).toBe(true)
    // Every missing input states what it costs — SCREENS.md §2.
    expect(coverage.every((item) => item.cost.length > 0)).toBe(true)
  })

  it('detects the inputs that are present', () => {
    const coverage = inputCoverage({
      readings: [reading],
      history: [],
      condition: null,
      business: {
        production_schedule: { work_time: { monday: { start: '06:00:00', end: '14:00:00' } } },
        inventory: [],
        technicians: [
          { name: 'Budi', role: 'mekanik', specialty: null, work_time: {}, occupied_time: {} },
        ],
      },
    })
    const present = coverage.filter((item) => item.present).map((item) => item.key)
    expect(present).toEqual(['sensor', 'schedule', 'tech'])
  })
})

describe('healthSources', () => {
  const base = {
    health_score: 80, health_summary: '', anomalies: [], defects: [], root_causes: [],
    recommendation: '', priority: 'low' as const, recommended_window: null, explanation: '',
    blockers: [], work_order: null, tier: null, model: null, sources: [],
  }
  const defect = {
    image: 'a.png', subject: 'product' as const, score: 0.9, threshold: 0.5,
    label: 'defect' as const, severity: 'high' as const, region: null,
    heatmap_path: null, method: 'patchcore', defect_class: null, class_confidence: null,
  }
  const anomaly = {
    tag: 'torque_nm', observed: 9, expected_range: [1, 2] as [number, number],
    severity: 'high' as const, method: 'robust_z',
  }

  it('says sensor only when no images were inspected', () => {
    expect(healthSources({ ...base, anomalies: [anomaly] })).toBe('sensor saja')
  })

  it('names QC too, including a batch that never touched result.defects', () => {
    const withBatch = {
      ...base, anomalies: [anomaly],
      qc_by_phase: [{ phase: 'f', asset_id: 'a', product: 'n', inspected: 1, defects: 1, defect_rate: 1, findings: [defect] }],
    }
    expect(healthSources(withBatch)).toBe('sensor + QC')
    // and the donut gets its defect slice, which reading result.defects missed
    expect(healthSegments(withBatch).find((s) => s.label === 'Defect')?.value).toBe(20)
  })

  it('says QC only when there are no sensor anomalies', () => {
    expect(healthSources({ ...base, defects: [defect] })).toBe('QC saja')
  })
})
