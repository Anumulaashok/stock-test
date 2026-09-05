const FORMULA_TRIGGER_CHARS = ['=', '+', '-', '@', '\t', '\r']

/** Escapes one CSV field: quotes when it contains a comma, quote, or
 * newline (doubling embedded quotes), and defuses spreadsheet formula
 * injection (OWASP CSV injection) by prefixing a leading `'` when the
 * value starts with a formula-trigger character. */
function escapeCsvField(value: string): string {
  const defused = FORMULA_TRIGGER_CHARS.includes(value[0]) ? `'${value}` : value
  if (/[",\n\r]/.test(defused)) {
    return `"${defused.replace(/"/g, '""')}"`
  }
  return defused
}

function toRow(fields: (string | number | null)[]): string {
  return fields.map((field) => escapeCsvField(field === null ? '' : String(field))).join(',')
}

/** Renders headers + rows as CSV text. Rows must already be backend
 * values -- this only escapes and joins, it never computes a figure. */
export function toCsv(headers: string[], rows: (string | number | null)[][]): string {
  return [toRow(headers), ...rows.map(toRow)].join('\r\n')
}

function isoDateToday(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Triggers a browser download of `content` as `${namePrefix}_${ISO date}.csv`. */
export function downloadCsv(namePrefix: string, content: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${namePrefix}_${isoDateToday()}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
