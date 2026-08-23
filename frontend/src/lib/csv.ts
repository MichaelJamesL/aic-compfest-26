/** Minimal CSV parsing — enough for a sensor export. No dependency. */
export function parseCsv(text: string): Record<string, string>[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n').filter((l) => l.trim())
  if (lines.length < 2) return []
  const header = splitLine(lines[0]).map((h) => h.trim())
  return lines.slice(1).map((line) => {
    const cells = splitLine(line)
    return Object.fromEntries(header.map((key, i) => [key, (cells[i] ?? '').trim()]))
  })
}

function splitLine(line: string): string[] {
  const out: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        cell += '"'
        i++
      } else quoted = !quoted
    } else if (char === ',' && !quoted) {
      out.push(cell)
      cell = ''
    } else cell += char
  }
  out.push(cell)
  return out
}

export interface ParsedReading {
  tag: string
  value: number
  unit: string
  recorded_at: string
}

const TIME_KEYS = ['recorded_at', 'timestamp', 'time', 'datetime', 'waktu']
const SKIP_KEYS = ['udi', 'id', 'product id', 'type', 'tag', 'unit', 'value']

/**
 * Accepts both shapes a PLC export comes in:
 *  - long:  tag,value,unit,recorded_at
 *  - wide:  timestamp,torque_nm,tool_wear_min,…   (melted into long)
 */
export function toReadings(rows: Record<string, string>[]): ParsedReading[] {
  if (!rows.length) return []
  const keys = Object.keys(rows[0])
  const lower = keys.map((k) => k.toLowerCase())
  const timeKey = keys[lower.findIndex((k) => TIME_KEYS.includes(k))]

  if (lower.includes('tag') && lower.includes('value')) {
    return rows
      .map((row) => ({
        tag: row[keys[lower.indexOf('tag')]],
        value: Number(row[keys[lower.indexOf('value')]]),
        unit: lower.includes('unit') ? row[keys[lower.indexOf('unit')]] : '',
        recorded_at: normaliseTime(timeKey ? row[timeKey] : ''),
      }))
      .filter((r) => r.tag && Number.isFinite(r.value))
  }

  const numericKeys = keys.filter(
    (key, i) =>
      key !== timeKey &&
      !SKIP_KEYS.includes(lower[i]) &&
      rows.some((row) => row[key] !== '' && Number.isFinite(Number(row[key]))),
  )

  const out: ParsedReading[] = []
  rows.forEach((row, index) => {
    const at = normaliseTime(timeKey ? row[timeKey] : '', index)
    for (const key of numericKeys) {
      const value = Number(row[key])
      if (!Number.isFinite(value)) continue
      out.push({ tag: slug(key), value, unit: '', recorded_at: at })
    }
  })
  return out
}

function slug(key: string): string {
  return key
    .toLowerCase()
    .replace(/\[[^\]]*\]/g, '')
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}

function normaliseTime(raw: string, index = 0): string {
  if (raw) {
    const parsed = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(raw) ? raw : `${raw}Z`)
    if (!Number.isNaN(parsed.getTime())) return parsed.toISOString()
  }
  // No timestamp column: synthesise a stable hourly series ending now.
  return new Date(Date.now() - (1000 - index) * 3_600_000).toISOString()
}
