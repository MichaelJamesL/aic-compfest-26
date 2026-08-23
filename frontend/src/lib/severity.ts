import type { IngestionStatus, Priority, Severity, Verdict, WorkOrderStatus } from '../api/types'
export type Tone = 'ok' | 'warn' | 'high' | 'crit' | 'neutral'
export const TONE_TEXT: Record<Tone, string> = { ok: 'text-ok-text', warn: 'text-warn-text', high: 'text-high-text', crit: 'text-crit-text', neutral: 'text-content-3' }
export const TONE_FILL: Record<Tone, string> = { ok: 'bg-ok-fill text-ok-text', warn: 'bg-warn-fill text-warn-text', high: 'bg-high-fill text-high-text', crit: 'bg-crit text-card', neutral: 'bg-surface-raised text-content-2' }
export const TONE_DOT: Record<Tone, string> = { ok: 'bg-ok', warn: 'bg-warn', high: 'bg-high', crit: 'bg-crit', neutral: 'bg-content-3' }
const RISK: Record<Severity, { tone: Tone; label: string }> = { low: { tone: 'ok', label: 'Rendah' }, medium: { tone: 'warn', label: 'Sedang' }, high: { tone: 'high', label: 'Tinggi' }, critical: { tone: 'crit', label: 'Kritis' } }
export const severityTone = (value: Severity): Tone => RISK[value]?.tone ?? 'neutral'
export const severityLabel = (value: Severity): string => RISK[value]?.label ?? value
export const priorityTone = (value: Priority): Tone => RISK[value]?.tone ?? 'neutral'
export const priorityLabel = (value: Priority): string => RISK[value]?.label ?? value
export function healthTone(score: number): Tone { return score >= 80 ? 'ok' : score >= 60 ? 'warn' : score >= 40 ? 'high' : 'crit' }
export function healthLabel(score: number): string { return score >= 80 ? 'Sehat' : score >= 60 ? 'Perlu diperhatikan' : score >= 40 ? 'Menurun' : 'Kritis' }
export const INGESTION: Record<IngestionStatus, { tone: Tone; label: string; hint: string }> = {
  pending: { tone: 'warn', label: 'Belum diindeks', hint: 'Belum masuk knowledge base — belum bisa dikutip analisis.' },
  ready: { tone: 'ok', label: 'Terindeks', hint: 'Tersimpan di pgvector dan bisa dikutip.' }, failed: { tone: 'crit', label: 'Gagal', hint: 'Pengindeksan gagal.' },
}
export const WORK_ORDER: Record<WorkOrderStatus, { tone: Tone; label: string; short: string }> = {
  draft: { tone: 'neutral', label: 'Draft', short: 'Draft' }, pending_approval: { tone: 'warn', label: 'Menunggu persetujuan', short: 'Diajukan' }, approved: { tone: 'ok', label: 'Disetujui', short: 'Disetujui' }, scheduled: { tone: 'ok', label: 'Terjadwal', short: 'Terjadwal' }, in_progress: { tone: 'high', label: 'Dikerjakan', short: 'Dikerjakan' }, blocked: { tone: 'crit', label: 'Terhambat', short: 'Terhambat' }, completed: { tone: 'ok', label: 'Selesai', short: 'Selesai' }, cancelled: { tone: 'neutral', label: 'Dibatalkan', short: 'Batal' }, rejected: { tone: 'crit', label: 'Ditolak', short: 'Ditolak' },
}
export const VERDICT: Record<Verdict, { tone: Tone; label: string; tint: 'sage' | 'apricot' | 'dark' }> = { resolved: { tone: 'ok', label: 'Masalah terselesaikan', tint: 'sage' }, partial: { tone: 'high', label: 'Sebagian terselesaikan', tint: 'apricot' }, not_resolved: { tone: 'crit', label: 'Belum terselesaikan', tint: 'dark' } }
export const WORK_ORDER_TRACK: WorkOrderStatus[] = ['draft', 'pending_approval', 'approved', 'scheduled', 'in_progress', 'completed']
