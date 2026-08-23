import { describe, expect, it } from 'vitest'
import { ApiError, errorCopy, getIdentity, setIdentity } from './client'

function apiError(code: string, message: string, details: { field: string; reason: string }[] = []) {
  return new ApiError(400, { code, message, details, request_id: 'req-1' })
}

describe('errorCopy', () => {
  // The server's `message` is a token, never user copy. API.md.
  it('maps known tokens to Indonesian', () => {
    expect(errorCopy(apiError('NOT_FOUND', 'asset_not_found'))).toBe('Mesin tidak ditemukan.')
    expect(errorCopy(apiError('VALIDATION_ERROR', 'file_too_large'))).toMatch(/10 MB/)
  })

  it('explains an illegal work-order transition in words', () => {
    const copy = errorCopy(apiError('CONFLICT', 'invalid_transition:pending_approval->scheduled'))
    expect(copy).toContain('pending_approval')
    expect(copy).toContain('scheduled')
    expect(copy).not.toContain('invalid_transition')
  })

  it('names the rejected extension', () => {
    expect(errorCopy(apiError('VALIDATION_ERROR', 'unsupported_extension:.jpg'))).toContain('.jpg')
  })

  it('falls back to field reasons for validation errors', () => {
    const copy = errorCopy(
      apiError('VALIDATION_ERROR', 'Input tidak valid', [
        { field: 'body.name', reason: 'String should have at least 1 character' },
      ]),
    )
    expect(copy).toContain('at least 1 character')
  })

  it('tells the user the backend may be down when the envelope is missing', () => {
    expect(errorCopy(new TypeError('Failed to fetch'))).toMatch(/backend/i)
  })

  it('keeps the request id for the error state to show', () => {
    expect(apiError('NOT_FOUND', 'asset_not_found').requestId).toBe('req-1')
  })
})

describe('identity', () => {
  it('keeps role changes working when localStorage is unavailable', () => {
    const storage = globalThis.localStorage
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } },
    })
    try {
      expect(setIdentity('demo-manager').user).toBe('demo-manager')
      expect(getIdentity().user).toBe('demo-manager')
    } finally {
      Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage })
      setIdentity('demo-engineer')
    }
  })
})
