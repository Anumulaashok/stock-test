import { describe, expect, it } from 'vitest'
import { bucketFor, classifyOverallHealth } from './dataSourceStatus'
import type { DataSourceStatus } from '../types/backend'

function source(overrides: Partial<DataSourceStatus> = {}): DataSourceStatus {
  return {
    name: 'screener',
    label: 'Screener',
    type: 'historical/search',
    configured: true,
    status: 'SUCCESS',
    capabilities: [],
    primary_for: [],
    fallback_for: [],
    last_success_at: null,
    last_error_at: null,
    limitation: null,
    ...overrides,
  }
}

describe('bucketFor', () => {
  it('is idle for an unconfigured source regardless of its status field', () => {
    expect(bucketFor(source({ configured: false, status: 'AUTH_EXPIRED' }))).toBe('idle')
  })

  it('is actionRequired for AUTH_EXPIRED', () => {
    expect(bucketFor(source({ status: 'AUTH_EXPIRED' }))).toBe('actionRequired')
  })

  it('is actionRequired for INVALID', () => {
    expect(bucketFor(source({ status: 'INVALID' }))).toBe('actionRequired')
  })

  it('is degradedServing for RATE_LIMITED', () => {
    expect(bucketFor(source({ status: 'RATE_LIMITED' }))).toBe('degradedServing')
  })

  it('is degradedServing for UNREACHABLE', () => {
    expect(bucketFor(source({ status: 'UNREACHABLE' }))).toBe('degradedServing')
  })

  it('is degradedServing for a SUCCESS source carrying a documented limitation (FMP 402 case)', () => {
    expect(bucketFor(source({ status: 'SUCCESS', limitation: 'Returns HTTP 402 for every NSE/BSE symbol.' }))).toBe(
      'degradedServing',
    )
  })

  it('is healthy for SUCCESS with no limitation', () => {
    expect(bucketFor(source({ status: 'SUCCESS' }))).toBe('healthy')
  })

  it('is idle for UNKNOWN/NOT_CONFIGURED', () => {
    expect(bucketFor(source({ status: 'UNKNOWN' }))).toBe('idle')
    expect(bucketFor(source({ status: 'NOT_CONFIGURED' }))).toBe('idle')
  })
})

describe('classifyOverallHealth', () => {
  it('reports noneConfigured when nothing is configured', () => {
    expect(classifyOverallHealth([source({ configured: false, status: 'NOT_CONFIGURED' })])).toEqual({
      kind: 'noneConfigured',
    })
  })

  it('reports healthy when every configured source is healthy', () => {
    expect(classifyOverallHealth([source(), source({ name: 'yfinance' })])).toEqual({ kind: 'healthy' })
  })

  it('reports degradedServing when a source has a documented limitation but no source needs action', () => {
    const result = classifyOverallHealth([
      source(),
      source({ name: 'fmp', limitation: 'Returns HTTP 402 for every NSE/BSE symbol.' }),
    ])
    expect(result.kind).toBe('degradedServing')
  })

  it('actionRequired wins over degradedServing when both are present', () => {
    const result = classifyOverallHealth([
      source({ name: 'fmp', limitation: 'Returns HTTP 402 for every NSE/BSE symbol.' }),
      source({ name: 'screener', status: 'AUTH_EXPIRED' }),
    ])
    expect(result.kind).toBe('actionRequired')
    if (result.kind === 'actionRequired') {
      expect(result.sources.map((s) => s.name)).toEqual(['screener'])
    }
  })

  it('ignores an unconfigured source entirely, never letting its absence read as degradation', () => {
    const result = classifyOverallHealth([
      source(),
      source({ name: 'indianapi', configured: false, status: 'NOT_CONFIGURED' }),
    ])
    expect(result).toEqual({ kind: 'healthy' })
  })
})
