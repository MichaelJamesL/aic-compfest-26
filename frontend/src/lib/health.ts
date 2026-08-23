import type { AnalysisResult } from '../api/types'
import type { Segment } from '../ui/Donut'

/**
 * Reconstruct the health-score deduction breakdown for the donut segments.
 * Mirrors HEALTH_WEIGHTS in ai-engine/src/signals.py — if those weights change,
 * change these. The remainder covers overdue + repeat-failure deductions,
 * which the result does not itemise.
 */
const WEIGHT: Record<string, number> = { low: 5, medium: 10, high: 20, critical: 30 }

export function healthSegments(result: AnalysisResult): Segment[] {
  const fromAnomalies = result.anomalies.reduce((sum, a) => sum + (WEIGHT[a.severity] ?? 0), 0)
  const fromDefects = result.defects
    .filter((d) => d.label === 'defect')
    .reduce((sum, d) => sum + (WEIGHT[d.severity] ?? 0), 0)

  const accounted = fromAnomalies + fromDefects
  const other = Math.max(0, 100 - result.health_score - accounted)

  // The score is the dominant arc; the deductions are what ate into it. Giving
  // the score a near-invisible fill inverts the reading of the whole ring —
  // it was white while the card was dark, and is ink now that the card is not.
  return [
    { label: 'Sisa skor', value: result.health_score, color: 'var(--color-content)' },
    { label: 'Anomali', value: fromAnomalies, color: 'var(--color-crit)' },
    { label: 'Defect', value: fromDefects, color: 'var(--color-high)' },
    { label: 'Overdue', value: other, color: 'var(--color-clay)' },
  ].filter((segment) => segment.value > 0)
}

/**
 * What each input contributes, and what its absence costs. One definition —
 * the analyse form and the result screen must say the same thing.
 * SCREENS.md §2 / §3 D.
 */
export const INPUTS = [
  {
    key: 'sensor',
    label: 'Data sensor',
    cost: 'tanpa data sensor, anomali dan health score tidak bisa dihitung dari mesin',
  },
  {
    key: 'qc',
    label: 'Citra QC',
    cost: 'tanpa citra QC, defect produk tidak bisa dipakai sebagai sinyal kondisi mesin',
  },
  {
    key: 'history',
    label: 'Histori maintenance',
    cost: 'tanpa histori, kegagalan berulang tidak terdeteksi',
  },
  {
    key: 'schedule',
    label: 'Jadwal produksi',
    cost: 'tanpa jadwal produksi, jendela maintenance tidak bisa dioptimalkan, hanya diprioritaskan',
  },
  {
    key: 'parts',
    label: 'Stok & ETA sparepart',
    cost: 'tanpa stok sparepart, ETA tidak bisa jadi blocker penjadwalan',
  },
  {
    key: 'tech',
    label: 'Ketersediaan teknisi',
    cost: 'tanpa roster teknisi, usulan penugasan hanya berdasarkan skill',
  },
  {
    key: 'condition',
    label: 'Kondisi manual / laporan operator',
    cost: 'tanpa kondisi manual, analisis hanya bersandar pada data yang terukur',
  },
] as const

/**
 * The five the analyse form owns, plus the manual condition. `history` is not
 * here: it is uploaded in Setup and read from the knowledge base, so the form
 * cannot claim it either way.
 */
export const FORM_INPUTS = INPUTS.filter((input) => input.key !== 'history')

export type InputKey = (typeof INPUTS)[number]['key']

/** Which inputs the run actually had, for the partial-input disclosure. */
export function inputCoverage(snapshot: {
  readings?: unknown[]
  history?: unknown[]
  condition?: string | null
  business?: {
    production_schedule: string | null
    spareparts: string[]
    technicians_available: number | null
    operator_report?: string | null
  }
} | null) {
  const business = snapshot?.business
  const present: Record<InputKey, boolean> = {
    sensor: (snapshot?.readings?.length ?? 0) > 0,
    qc: false,
    history: (snapshot?.history?.length ?? 0) > 0,
    schedule: Boolean(business?.production_schedule),
    parts: (business?.spareparts?.length ?? 0) > 0,
    tech: business?.technicians_available != null,
    condition: Boolean(snapshot?.condition || business?.operator_report),
  }
  return INPUTS.map((input) => ({ ...input, present: present[input.key] }))
}
