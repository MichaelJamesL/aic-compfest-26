/**
 * The single mapping from a domain value to a design token.
 * Colour is never the only channel — every entry carries a label too.
 * docs/design/VISUAL_LANGUAGE.md §2.
 */
import type { IngestionStatus, Priority, Severity, Verdict, WorkOrderStatus } from '../api/types'

export type Tone = 'ok' | 'warn' | 'high' | 'crit' | 'neutral'

export const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-ok-text',
  warn: 'text-warn-text',
  high: 'text-high-text',
  crit: 'text-crit-text',
  neutral: 'text-content-3',
}

export const TONE_FILL: Record<Tone, string> = {
  ok: 'bg-ok-fill text-ok-text',
  warn: 'bg-warn-fill text-warn-text',
  high: 'bg-high-fill text-high-text',
  crit: 'bg-crit text-card',
  neutral: 'bg-surface-raised text-content-2',
}

export const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  high: 'bg-high',
  crit: 'bg-crit',
  neutral: 'bg-content-3',
}

/** Health score bands, from docs/design/VISUAL_LANGUAGE.md §2. */
export function healthTone(score: number): Tone {
  if (score >= 80) return 'ok'
  if (score >= 60) return 'warn'
  if (score >= 40) return 'high'
  return 'crit'
}

export function healthLabel(score: number): string {
  if (score >= 80) return 'Sehat'
  if (score >= 60) return 'Perlu diperhatikan'
  if (score >= 40) return 'Menurun'
  return 'Kritis'
}

const PRIORITY: Record<Priority, { tone: Tone; label: string }> = {
  low: { tone: 'ok', label: 'Rendah' },
  medium: { tone: 'warn', label: 'Sedang' },
  high: { tone: 'high', label: 'Tinggi' },
  critical: { tone: 'crit', label: 'Kritis' },
}

export const priorityTone = (p: Priority): Tone => PRIORITY[p]?.tone ?? 'neutral'
export const priorityLabel = (p: Priority): string => PRIORITY[p]?.label ?? p

const SEVERITY: Record<Severity, { tone: Tone; label: string }> = {
  low: { tone: 'ok', label: 'Rendah' },
  medium: { tone: 'warn', label: 'Sedang' },
  high: { tone: 'high', label: 'Tinggi' },
  critical: { tone: 'crit', label: 'Kritis' },
}

export const severityTone = (s: Severity): Tone => SEVERITY[s]?.tone ?? 'neutral'
export const severityLabel = (s: Severity): string => SEVERITY[s]?.label ?? s

/**
 * A `pending` document is not in the knowledge base and cannot be cited.
 * Surfacing this is load-bearing — see docs/design/SCREENS.md §1.
 */
export const INGESTION: Record<IngestionStatus, { tone: Tone; label: string; hint: string }> = {
  pending: {
    tone: 'warn',
    label: 'Belum diindeks',
    hint: 'Belum masuk knowledge base — belum bisa dikutip analisis.',
  },
  ready: { tone: 'ok', label: 'Terindeks', hint: 'Tersimpan di pgvector dan bisa dikutip.' },
  failed: { tone: 'crit', label: 'Gagal', hint: 'Pengindeksan gagal.' },
}

/**
 * `short` is for the six-step track, where the full label does not fit and
 * would truncate. Everywhere else uses `label`.
 */
export const WORK_ORDER: Record<WorkOrderStatus, { tone: Tone; label: string; short: string }> = {
  draft: { tone: 'neutral', label: 'Draft', short: 'Draft' },
  pending_approval: { tone: 'warn', label: 'Menunggu persetujuan', short: 'Diajukan' },
  approved: { tone: 'ok', label: 'Disetujui', short: 'Disetujui' },
  scheduled: { tone: 'ok', label: 'Terjadwal', short: 'Terjadwal' },
  in_progress: { tone: 'high', label: 'Dikerjakan', short: 'Dikerjakan' },
  blocked: { tone: 'crit', label: 'Terhambat', short: 'Terhambat' },
  completed: { tone: 'ok', label: 'Selesai', short: 'Selesai' },
  cancelled: { tone: 'neutral', label: 'Dibatalkan', short: 'Batal' },
  rejected: { tone: 'crit', label: 'Ditolak', short: 'Ditolak' },
}

/**
 * Verification outcomes. `not_resolved` is a tinted card with a border rather
 * than a solid fill — it must read as unfinished, not as an error toast.
 * SCREENS.md §6.
 */
export const VERDICT: Record<Verdict, { tone: Tone; label: string; tint: 'sage' | 'apricot' | 'dark' }> = {
  resolved: { tone: 'ok', label: 'Masalah terselesaikan', tint: 'sage' },
  partial: { tone: 'high', label: 'Sebagian terselesaikan', tint: 'apricot' },
  not_resolved: { tone: 'crit', label: 'Belum terselesaikan', tint: 'dark' },
}

/** The happy path of the state machine, for the progress track. */
export const WORK_ORDER_TRACK: WorkOrderStatus[] = [
  'draft',
  'pending_approval',
  'approved',
  'scheduled',
  'in_progress',
  'completed',
]
