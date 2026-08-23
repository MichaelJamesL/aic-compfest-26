import type { IngestionStatus, Priority, Severity, Verdict, WorkOrderStatus } from '../api/types'

export type Tone = 'ok' | 'warn' | 'high' | 'crit' | 'neutral'

export const TONE_FILL: Record<Tone, string> = {
  ok: 'bg-ok-fill text-ok-text',
  warn: 'bg-warn-fill text-warn-text',
  high: 'bg-high-fill text-high-text',
  crit: 'bg-crit-fill text-crit-text',
  neutral: 'bg-raised text-dim',
}

export const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  high: 'bg-high',
  crit: 'bg-crit',
  neutral: 'bg-dim',
}

export const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-ok-text',
  warn: 'text-warn-text',
  high: 'text-high-text',
  crit: 'text-crit-text',
  neutral: 'text-dim',
}

const RISK_TONE: Record<Severity, Tone> = { low: 'ok', medium: 'warn', high: 'high', critical: 'crit' }
const RISK_LABEL: Record<Severity, string> = { low: 'Rendah', medium: 'Sedang', high: 'Tinggi', critical: 'Kritis' }

export function severityTone(value: Severity): Tone { return RISK_TONE[value] }
export function severityLabel(value: Severity): string { return RISK_LABEL[value] }
export function priorityTone(value: Priority): Tone { return RISK_TONE[value] }
export function priorityLabel(value: Priority): string { return RISK_LABEL[value] }

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

export const INGESTION: Record<IngestionStatus, { label: string; tone: Tone; hint: string }> = {
  pending: { label: 'Belum diindeks', tone: 'warn', hint: 'Belum masuk knowledge base.' },
  ready: { label: 'Terindeks', tone: 'ok', hint: 'Siap dikutip analisis.' },
  failed: { label: 'Gagal', tone: 'crit', hint: 'Pengindeksan gagal.' },
}

export const VERDICT: Record<Verdict, { label: string; tone: Tone; tint: 'dark' | 'sage' | 'apricot' }> = {
  resolved: { label: 'Masalah terselesaikan', tone: 'ok', tint: 'sage' },
  partial: { label: 'Sebagian terselesaikan', tone: 'warn', tint: 'apricot' },
  not_resolved: { label: 'Belum terselesaikan', tone: 'crit', tint: 'dark' },
}

export const WORK_ORDER_TRACK: WorkOrderStatus[] = ['draft', 'pending_approval', 'approved', 'scheduled', 'in_progress', 'completed']
export const WORK_ORDER: Record<WorkOrderStatus, { label: string; short: string; tone: Tone }> = {
  draft: { label: 'Draft', short: 'Draft', tone: 'neutral' },
  pending_approval: { label: 'Menunggu persetujuan', short: 'Menunggu', tone: 'warn' },
  approved: { label: 'Disetujui', short: 'Disetujui', tone: 'ok' },
  scheduled: { label: 'Terjadwal', short: 'Terjadwal', tone: 'ok' },
  in_progress: { label: 'Sedang dikerjakan', short: 'Dikerjakan', tone: 'high' },
  blocked: { label: 'Terblokir', short: 'Terblokir', tone: 'crit' },
  completed: { label: 'Selesai', short: 'Selesai', tone: 'ok' },
  cancelled: { label: 'Dibatalkan', short: 'Dibatalkan', tone: 'neutral' },
  rejected: { label: 'Ditolak', short: 'Ditolak', tone: 'crit' },
}
