import type { AnalysisResult, RequestSnapshot } from '../api/types'
import type { Segment } from '../ui/Donut'

const WEIGHT: Record<string, number> = { low: 5, medium: 10, high: 20, critical: 30 }

/**
 * Every finding, whichever way the images arrived. A QC batch lands in
 * `qc_by_phase`, so reading `defects` alone drew a donut with no defect slice
 * for a run whose score the defects had just cut in half.
 */
export function findings(result: AnalysisResult) {
  return [...result.defects, ...(result.qc_by_phase ?? []).flatMap((phase) => phase.findings)]
}

/** What the deterministic score was computed from, for the reader. */
export function healthSources(result: AnalysisResult): string {
  const hasSensors = result.anomalies.length > 0
  const hasQc = findings(result).length > 0
  if (hasSensors && hasQc) return 'sensor + QC'
  if (hasQc) return 'QC saja'
  return 'sensor saja'
}

export function healthSegments(result: AnalysisResult): Segment[] {
  const fromAnomalies = result.anomalies.reduce((sum, item) => sum + (WEIGHT[item.severity] ?? 0), 0)
  const fromDefects = findings(result).filter((item) => item.label === 'defect').reduce((sum, item) => sum + (WEIGHT[item.severity] ?? 0), 0)
  const other = Math.max(0, 100 - result.health_score - fromAnomalies - fromDefects)
  return [
    { label: 'Sisa skor', value: result.health_score, color: 'var(--color-content)' },
    { label: 'Anomali', value: fromAnomalies, color: 'var(--color-crit)' },
    { label: 'Defect', value: fromDefects, color: 'var(--color-high)' },
    { label: 'Overdue', value: other, color: 'var(--color-clay)' },
  ].filter((segment) => segment.value > 0)
}

export const INPUTS = [
  { key: 'sensor', label: 'Data sensor', cost: 'tanpa data sensor, anomali dan health score tidak bisa dihitung dari mesin' },
  { key: 'qc', label: 'Citra QC', cost: 'tanpa citra QC, defect produk tidak bisa dipakai sebagai sinyal kondisi mesin' },
  { key: 'history', label: 'Histori maintenance', cost: 'tanpa histori, kegagalan berulang tidak terdeteksi' },
  { key: 'schedule', label: 'Jadwal produksi', cost: 'tanpa jadwal produksi, jendela maintenance tidak bisa dioptimalkan, hanya diprioritaskan' },
  { key: 'parts', label: 'Stok & ETA sparepart', cost: 'tanpa stok sparepart, ETA tidak bisa jadi blocker penjadwalan' },
  { key: 'tech', label: 'Ketersediaan teknisi', cost: 'tanpa roster teknisi, usulan penugasan hanya berdasarkan skill' },
  { key: 'condition', label: 'Kondisi manual / laporan operator', cost: 'tanpa kondisi manual, analisis hanya bersandar pada data yang terukur' },
] as const
export const FORM_INPUTS = INPUTS.filter((input) => input.key !== 'history')
export type InputKey = (typeof INPUTS)[number]['key']

export function inputCoverage(snapshot: Partial<RequestSnapshot> | null) {
  const business = snapshot?.business
  const present: Record<InputKey, boolean> = {
    sensor: (snapshot?.readings?.length ?? 0) > 0,
    qc: Boolean(snapshot?.qc_batch_id || snapshot?.images?.length),
    history: (snapshot?.history?.length ?? 0) > 0,
    schedule: Object.keys(business?.production_schedule?.work_time ?? {}).length > 0,
    parts: (business?.inventory?.length ?? 0) > 0,
    tech: (business?.technicians?.length ?? 0) > 0,
    condition: Boolean(snapshot?.condition || business?.operator_report),
  }
  return INPUTS.map((input) => ({ ...input, present: present[input.key] }))
}
