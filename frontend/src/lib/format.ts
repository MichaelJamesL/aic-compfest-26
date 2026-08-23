/** Formatting. All numbers that reach the screen come through here. */

/**
 * The backend returns naive timestamps on SQLite ("2026-08-20T10:00:00") even
 * though the columns are timezone-aware. Treat every timestamp as UTC.
 * docs/API.md gotcha 3.
 */
export function parseUtc(raw: string | null | undefined): Date | null {
  if (!raw) return null
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw)
  const date = new Date(hasZone ? raw : `${raw}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

const dateTime = new Intl.DateTimeFormat('id-ID', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})
const dateOnly = new Intl.DateTimeFormat('id-ID', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

export function formatDateTime(raw: string | null | undefined): string {
  const date = parseUtc(raw)
  return date ? dateTime.format(date) : '—'
}

export function formatDate(raw: string | null | undefined): string {
  const date = parseUtc(raw)
  return date ? dateOnly.format(date) : '—'
}

export function formatRelative(raw: string | null | undefined): string {
  const date = parseUtc(raw)
  if (!date) return '—'
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return 'baru saja'
  if (minutes < 60) return `${minutes} menit lalu`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} jam lalu`
  return `${Math.round(hours / 24)} hari lalu`
}

/** Indonesian currency, non-breaking space after Rp. */
export function formatRupiah(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 1_000_000_000) return `Rp ${(value / 1_000_000_000).toFixed(1)} M`
  if (value >= 1_000_000) return `Rp ${(value / 1_000_000).toFixed(1)} jt`
  return `Rp ${new Intl.NumberFormat('id-ID').format(value)}`
}

export function formatNumber(value: number, digits = 1): string {
  return new Intl.NumberFormat('id-ID', {
    maximumFractionDigits: digits,
  }).format(value)
}

export function formatPercent(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatDuration(hours: number | null | undefined): string {
  if (hours == null) return '—'
  if (hours < 1) return `${Math.round(hours * 60)} menit`
  return `${formatNumber(hours)} jam`
}
