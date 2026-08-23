/** Minimal CSV parsing, supporting quoted cells and CRLF exports. */
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = []
  let row: string[] = []; let cell = ''; let quoted = false
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i += 1 } else quoted = !quoted
    } else if (char === ',' && !quoted) { row.push(cell.trim()); cell = ''
    } else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && text[i + 1] === '\n') i += 1
      row.push(cell.trim()); cell = ''
      if (row.some(Boolean)) rows.push(row)
      row = []
    } else cell += char
  }
  row.push(cell.trim()); if (row.some(Boolean)) rows.push(row)
  const headers = (rows.shift() ?? []).map((header) => header.toLowerCase())
  return rows.map((values) => Object.fromEntries(headers.map((header, i) => [header, values[i] ?? ''])))
}

export interface ParsedReading { tag: string; value: number; unit: string; recorded_at: string }
const TIME_KEYS = ['recorded_at', 'timestamp', 'time', 'datetime', 'waktu']
const SKIP_KEYS = ['udi', 'id', 'product id', 'type', 'tag', 'unit', 'value']

export function toReadings(rows: Record<string, string>[]): ParsedReading[] {
  if (!rows.length) return []
  const keys = Object.keys(rows[0]); const lower = keys.map((key) => key.toLowerCase())
  const timeKey = keys[lower.findIndex((key) => TIME_KEYS.includes(key))]
  if (lower.includes('tag') && lower.includes('value')) return rows.map((row) => ({
    tag: row[keys[lower.indexOf('tag')]], value: Number(row[keys[lower.indexOf('value')]]),
    unit: lower.includes('unit') ? row[keys[lower.indexOf('unit')]] : '', recorded_at: normaliseTime(timeKey ? row[timeKey] : ''),
  })).filter((reading) => reading.tag && Number.isFinite(reading.value))
  const numericKeys = keys.filter((key, index) => key !== timeKey && !SKIP_KEYS.includes(lower[index]) && rows.some((row) => row[key] !== '' && Number.isFinite(Number(row[key]))))
  return rows.flatMap((row, index) => numericKeys.flatMap((key) => {
    const value = Number(row[key]); return Number.isFinite(value) ? [{ tag: slug(key), value, unit: '', recorded_at: normaliseTime(timeKey ? row[timeKey] : '', index) }] : []
  }))
}
function slug(key: string): string { return key.toLowerCase().replace(/\[[^\]]*\]/g, '').trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') }
function normaliseTime(raw: string, index = 0): string {
  if (raw) { const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(raw) ? raw : `${raw}Z`); if (!Number.isNaN(date.getTime())) return date.toISOString() }
  return new Date(Date.now() - (1000 - index) * 3_600_000).toISOString()
}
