import { describe, expect, it } from 'vitest'
import { formatDateTime } from './format'

describe('formatDateTime', () => {
  it('treats timezone-less API timestamps as UTC', () => {
    const formatted = formatDateTime('2026-08-23T00:00:00')
    expect(formatted).toContain('23 Agu 2026')
  })
})
