import { describe, expect, it } from 'vitest'
import { formatBytes, formatDuration, formatPercent, formatRupiah, parseUtc, formatDateTime } from './format'

describe('parseUtc', () => {
  it('treats a naive timestamp as UTC', () => expect(parseUtc('2026-08-20T10:00:00')?.toISOString()).toBe('2026-08-20T10:00:00.000Z'))
  it('respects an explicit zone', () => expect(parseUtc('2026-08-20T17:00:00+07:00')?.toISOString()).toBe('2026-08-20T10:00:00.000Z'))
  it('returns null for invalid input', () => expect(parseUtc(null)).toBeNull())
})
describe('formatting', () => {
  it('formats dates in Indonesian UTC', () => expect(formatDateTime('2026-08-23T00:00:00')).toContain('23 Agu 2026'))
  it('formats rupiah', () => {
    expect(formatRupiah(45_000)).toMatch(/^Rp\u00a0/)
    expect(formatRupiah(18_400_000)).toBe('Rp\u00a018.4 jt')
    expect(formatRupiah(null)).toBe('—')
  })
  it('formats bytes and duration', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2 KB')
    expect(formatDuration(0.5)).toBe('30 menit')
    expect(formatDuration(null)).toBe('—')
  })
  it('formats percentages', () => expect(formatPercent(1 / 3, 1)).toBe('33.3%'))
})
