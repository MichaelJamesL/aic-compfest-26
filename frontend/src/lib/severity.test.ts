import { describe, expect, it } from 'vitest'
import {
  INGESTION,
  TONE_DOT,
  TONE_FILL,
  TONE_TEXT,
  WORK_ORDER,
  WORK_ORDER_TRACK,
  healthLabel,
  healthTone,
  priorityLabel,
  priorityTone,
  severityLabel,
} from './severity'
import type { WorkOrderStatus } from '../api/types'

describe('health bands', () => {
  it('maps the four bands from VISUAL_LANGUAGE.md §2', () => {
    expect(healthTone(92)).toBe('ok')
    expect(healthTone(80)).toBe('ok')
    expect(healthTone(79)).toBe('warn')
    expect(healthTone(60)).toBe('warn')
    expect(healthTone(59)).toBe('high')
    expect(healthTone(40)).toBe('high')
    expect(healthTone(39)).toBe('crit')
    expect(healthTone(0)).toBe('crit')
  })

  it('always carries a label, so colour is never the only channel', () => {
    for (const score of [95, 70, 45, 10]) {
      expect(healthLabel(score).length).toBeGreaterThan(0)
    }
  })
})

describe('domain to token maps', () => {
  it('covers every tone in all three token maps', () => {
    for (const tone of ['ok', 'warn', 'high', 'crit', 'neutral'] as const) {
      expect(TONE_TEXT[tone]).toBeTruthy()
      expect(TONE_FILL[tone]).toBeTruthy()
      expect(TONE_DOT[tone]).toBeTruthy()
    }
  })

  it('labels every priority and severity in Indonesian', () => {
    for (const level of ['low', 'medium', 'high', 'critical'] as const) {
      expect(priorityLabel(level)).not.toBe(level)
      expect(severityLabel(level)).not.toBe(level)
      expect(priorityTone(level)).not.toBe('neutral')
    }
  })

  it('covers every work-order status the API can return', () => {
    const all: WorkOrderStatus[] = [
      'draft',
      'pending_approval',
      'approved',
      'scheduled',
      'in_progress',
      'blocked',
      'completed',
      'cancelled',
      'rejected',
    ]
    for (const status of all) {
      expect(WORK_ORDER[status]?.label).toBeTruthy()
    }
  })

  it('tracks only the happy path, ending at completed', () => {
    expect(WORK_ORDER_TRACK).toContain('approved')
    expect(WORK_ORDER_TRACK.at(-1)).toBe('completed')
    expect(WORK_ORDER_TRACK).not.toContain('rejected')
  })
})

describe('ingestion status', () => {
  // A pending document is not in the corpus and cannot be cited — the UI
  // must say so. SCREENS.md §1.
  it('warns on pending rather than reading as success', () => {
    expect(INGESTION.pending.tone).toBe('warn')
    expect(INGESTION.pending.hint).toMatch(/knowledge base/i)
    expect(INGESTION.ready.tone).toBe('ok')
    expect(INGESTION.failed.tone).toBe('crit')
  })
})
