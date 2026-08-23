export interface ParsedReading {
  tag: string
  value: number
  unit: string
  recorded_at: string
}

export type CsvRow = Record<string, string>

export function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
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
  row.push(cell.trim())
  if (row.some(Boolean)) rows.push(row)
  const headers = (rows.shift() ?? []).map((header) => header.toLowerCase())
  return rows.map((values) => Object.fromEntries(headers.map((header, i) => [header, values[i] ?? ''])))
}

export function toReadings(rows: CsvRow[]): ParsedReading[] {
  return rows.flatMap((row) => {
    const timestamp = row.recorded_at || row.timestamp || row.time || ''
    const tag = row.tag || row.name || ''
    if (tag && row.value !== undefined && Number.isFinite(Number(row.value))) {
      return [{ tag, value: Number(row.value), unit: row.unit || '', recorded_at: timestamp }]
    }
    return Object.entries(row)
      .filter(([key, value]) => !['timestamp', 'recorded_at', 'time', 'unit'].includes(key) && value !== '' && Number.isFinite(Number(value)))
      .map(([key, value]) => ({ tag: key, value: Number(value), unit: '', recorded_at: timestamp }))
  })
}
