import { describe, expect, it } from 'vitest'
import { toCsv } from './csv'

describe('toCsv', () => {
  it('joins headers and rows with CRLF and commas', () => {
    expect(toCsv(['a', 'b'], [['1', '2']])).toBe('a,b\r\n1,2')
  })

  it('quotes a field containing a comma', () => {
    expect(toCsv(['ticker'], [['RELIANCE, LTD']])).toBe('ticker\r\n"RELIANCE, LTD"')
  })

  it('doubles an embedded quote and wraps the field', () => {
    expect(toCsv(['note'], [['say "hi"']])).toBe('note\r\n"say ""hi"""')
  })

  it('quotes a field containing a newline', () => {
    expect(toCsv(['note'], [['line1\nline2']])).toBe('note\r\n"line1\nline2"')
  })

  it('renders null as an empty field', () => {
    expect(toCsv(['price'], [[null]])).toBe('price\r\n')
  })

  it('prefixes a formula-trigger leading character to defuse spreadsheet injection', () => {
    expect(toCsv(['x'], [['=SUM(A1:A2)']])).toBe("x\r\n'=SUM(A1:A2)")
    expect(toCsv(['x'], [['+1']])).toBe("x\r\n'+1")
    expect(toCsv(['x'], [['@cmd']])).toBe("x\r\n'@cmd")
  })

  it('does not defuse a value that merely contains, but does not start with, a formula-trigger character', () => {
    expect(toCsv(['x'], [['A-1']])).toBe('x\r\nA-1')
  })

  it('renders numbers as their string form', () => {
    expect(toCsv(['n'], [[42]])).toBe('n\r\n42')
  })

  it('renders zero rows as just the header line', () => {
    expect(toCsv(['a', 'b'], [])).toBe('a,b')
  })
})
