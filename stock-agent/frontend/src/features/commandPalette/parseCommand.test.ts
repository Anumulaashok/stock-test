import { describe, expect, it } from 'vitest'
import { parseCommand } from './parseCommand'

describe('parseCommand', () => {
  it('returns null for empty/whitespace input', () => {
    expect(parseCommand('')).toBeNull()
    expect(parseCommand('   ')).toBeNull()
  })

  it('parses a bare ticker to the stock page', () => {
    expect(parseCommand('reliance')).toEqual({ path: '/stock/RELIANCE', description: 'Open RELIANCE' })
  })

  it('parses "compare A B" into the compare route', () => {
    const result = parseCommand('compare TCS INFY')
    expect(result).toEqual({ path: '/compare?tickers=TCS,INFY', description: 'Compare TCS, INFY' })
  })

  it('parses comma-separated compare tickers too', () => {
    const result = parseCommand('compare TCS,INFY,BETA')
    expect(result).toEqual({ path: '/compare?tickers=TCS,INFY,BETA', description: 'Compare TCS, INFY, BETA' })
  })

  it('rejects compare with fewer than 2 tickers', () => {
    const result = parseCommand('compare TCS')
    expect(result).toHaveProperty('error')
  })

  it('rejects compare with more than 4 tickers', () => {
    const result = parseCommand('compare A B C D E')
    expect(result).toHaveProperty('error')
  })

  it('parses "screen score>70" into a screener URL with the minScore filter', () => {
    const result = parseCommand('screen score>70')
    expect(result).toEqual({ path: '/screener?minScore=70', description: 'Screen with these filters' })
  })

  it('parses "screen band:strong,excellent" into a screener URL with bands', () => {
    const result = parseCommand('screen band:strong,excellent')
    expect(result).toEqual({ path: '/screener?bands=strong%2Cexcellent', description: 'Screen with these filters' })
  })

  it('combines score and band filters', () => {
    const result = parseCommand('screen score>50 band:good')
    expect(result).toEqual({ path: '/screener?bands=good&minScore=50', description: 'Screen with these filters' })
  })

  it('rejects an unsupported screener filter like sector, rather than silently ignoring it', () => {
    const result = parseCommand('screen roe>20 sector:IT')
    expect(result).toHaveProperty('error')
  })

  it('navigates to a known page name with no arguments', () => {
    expect(parseCommand('watchlist')).toEqual({ path: '/watchlist', description: 'Go to watchlist' })
  })

  it('does not treat a page name followed by extra text as a page nav', () => {
    const result = parseCommand('watchlist extra')
    expect(result).toHaveProperty('error')
  })

  it('returns a helpful error for unrecognized input', () => {
    const result = parseCommand('do something weird here')
    expect(result).toHaveProperty('error')
  })
})
