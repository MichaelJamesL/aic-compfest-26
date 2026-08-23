import { describe, expect, it } from 'vitest'
import {
  formatBytes,
  formatDuration,
  formatPercent,
  formatRupiah,
  parseUtc,
} from './format'

describe('parseUtc', () => {
  // docs/API.md gotcha 3: SQLite returns naive timestamps for tz-aware columns.
  it('treats a naive timestamp as UTC', () => {
    expect(parseUtc('2026-08-20T10:00:00')?.toISOString()).toBe('2026-08-20T10:00:00.000Z')
  })

  it('respects an explicit zone', () => {
    expect(parseUtc('2026-08-20T10:00:00Z')?.toISOString()).toBe('2026-08-20T10:00:00.000Z')
    expect(parseUtc('2026-08-20T17:00:00+07:00')?.toISOString()).toBe('2026-08-20T10:00:00.000Z')
  })

  it('returns null for nothing and for garbage', () => {
    expect(parseUtc(null)).toBeNull()
    expect(parseUtc('')).toBeNull()
    expect(parseUtc('not a date')).toBeNull()
  })
})

describe('formatRupiah', () => {
  // VISUAL_LANGUAGE.md §3: a non-breaking space after Rp, so the amount
  // never wraps away from its unit.
  const NBSP = '\u00a0'

  it('separates Rp from the amount with a non-breaking space', () => {
    expect(formatRupiah(45_000)).toMatch(new RegExp(`^Rp${NBSP}`))
    expect(formatRupiah(45_000)).not.toContain('Rp ')
  })

  it('scales to juta and miliar', () => {
    expect(formatRupiah(18_400_000)).toBe(`Rp${NBSP}18.4 jt`)
    expect(formatRupiah(1_200_000_000)).toBe(`Rp${NBSP}1.2 M`)
  })

  it('keeps small amounts exact', () => {
    expect(formatRupiah(45_000)).toContain('45')
  })

  it('renders an em dash for nothing', () => {
    expect(formatRupiah(null)).toBe('—')
  })
})

describe('misc formatting', () => {
  it('formats bytes', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
  })

  it('formats duration below and above an hour', () => {
    expect(formatDuration(0.5)).toBe('30 menit')
    expect(formatDuration(3)).toBe('3 jam')
    expect(formatDuration(null)).toBe('—')
  })

  it('formats a fraction as a percentage', () => {
    expect(formatPercent(0.25)).toBe('25%')
    expect(formatPercent(1 / 3, 1)).toBe('33.3%')
  })
})
