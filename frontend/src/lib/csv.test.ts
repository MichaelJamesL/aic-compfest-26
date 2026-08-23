import { describe, expect, it } from 'vitest'
import { parseCsv, toReadings } from './csv'

describe('parseCsv', () => {
  it('handles quoted cells containing commas', () => {
    const rows = parseCsv('a,b\n"one, two",3')
    expect(rows).toEqual([{ a: 'one, two', b: '3' }])
  })

  it('handles escaped quotes and CRLF', () => {
    const rows = parseCsv('a\r\n"say ""hi"""')
    expect(rows[0].a).toBe('say "hi"')
  })

  it('returns nothing for a header-only file', () => {
    expect(parseCsv('a,b\n')).toEqual([])
  })
})

describe('toReadings — long format', () => {
  it('reads tag/value/unit/recorded_at', () => {
    const readings = toReadings(
      parseCsv('tag,value,unit,recorded_at\ntorque_nm,41.2,Nm,2026-08-20T10:00:00Z'),
    )
    expect(readings).toEqual([
      { tag: 'torque_nm', value: 41.2, unit: 'Nm', recorded_at: '2026-08-20T10:00:00.000Z' },
    ])
  })

  it('drops rows whose value is not a number', () => {
    const readings = toReadings(parseCsv('tag,value\ntorque_nm,abc\ntorque_nm,5'))
    expect(readings).toHaveLength(1)
  })
})

describe('toReadings — wide format', () => {
  it('melts one row per numeric column and slugs the tag', () => {
    const readings = toReadings(
      parseCsv(
        'timestamp,Torque [Nm],Tool wear [min]\n2026-08-20T10:00:00Z,41.2,180',
      ),
    )
    expect(readings).toHaveLength(2)
    expect(readings.map((r) => r.tag)).toEqual(['torque', 'tool_wear'])
    expect(readings[1].value).toBe(180)
    expect(readings[0].recorded_at).toBe('2026-08-20T10:00:00.000Z')
  })

  it('skips identifier columns that are not measurements', () => {
    const readings = toReadings(parseCsv('UDI,Type,timestamp,torque_nm\n1,M,2026-08-20T10:00:00Z,41.2'))
    expect(readings.map((r) => r.tag)).toEqual(['torque_nm'])
  })

  it('synthesises a timestamp when the export has no time column', () => {
    const readings = toReadings(parseCsv('torque_nm\n41.2\n42.0'))
    expect(readings).toHaveLength(2)
    expect(Number.isNaN(Date.parse(readings[0].recorded_at))).toBe(false)
    // Stable ordering: later rows are later in time.
    expect(Date.parse(readings[1].recorded_at)).toBeGreaterThan(Date.parse(readings[0].recorded_at))
  })
})
