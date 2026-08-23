import type { AnalysisResult, RequestSnapshot } from '../api/types'
import type { Segment } from '../ui/Donut'

export const FORM_INPUTS = [
  { key: 'sensor', label: 'Data sensor', cost: 'anomali sensor tidak bisa dihitung' },
  { key: 'qc', label: 'Citra QC', cost: 'rantai QC ke mesin tidak bisa ditarik' },
  { key: 'schedule', label: 'Jadwal produksi', cost: 'jendela maintenance tidak bisa dioptimalkan, hanya diprioritaskan' },
  { key: 'parts', label: 'Sparepart', cost: 'ETA tidak bisa jadi blocker penjadwalan' },
  { key: 'tech', label: 'Teknisi', cost: 'kapasitas pengerjaan tidak bisa dipastikan' },
  { key: 'condition', label: 'Kondisi manual', cost: 'konteks lapangan tidak tersedia' },
] as const

const COVERAGE_INPUTS = [
  ...FORM_INPUTS,
  { key: 'history', label: 'Histori maintenance', cost: 'pola kegagalan berulang tidak terlihat' },
] as const

export function healthSegments(result: AnalysisResult): Segment[] {
  const score = Math.max(0, Math.min(100, result.health_score))
  return [
    { label: 'Kesehatan', value: score, color: 'var(--color-ok)' },
    { label: 'Pengurangan', value: 100 - score, color: 'var(--color-crit)' },
  ]
}

export function inputCoverage(snapshot: RequestSnapshot | null): Array<(typeof COVERAGE_INPUTS)[number] & { present: boolean }> {
  const business = snapshot?.business
  const present: Record<string, boolean> = {
    sensor: (snapshot?.readings.length ?? 0) > 0,
    qc: Boolean(snapshot?.qc_batch_id || snapshot?.images?.length),
    history: (snapshot?.history.length ?? 0) > 0,
    schedule: Boolean(business?.production_schedule),
    parts: (business?.spareparts.length ?? 0) > 0,
    tech: business?.technicians_available != null,
    condition: Boolean(snapshot?.condition || business?.operator_report),
  }
  return COVERAGE_INPUTS.map((item) => ({ ...item, present: present[item.key] }))
}
