import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCountUp } from './useCountUp'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('useCountUp', () => {
  it('reaches the target value', async () => {
    const { result } = renderHook(() => useCountUp(70))
    await waitFor(() => expect(result.current).toBe(70), { timeout: 5000 })
  })

  it('returns null when the target is null, never animating toward a fabricated number', () => {
    const { result } = renderHook(() => useCountUp(null))
    expect(result.current).toBeNull()
  })

  it('jumps straight to the target with no animation when the OS asks for reduced motion', () => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
    const { result } = renderHook(() => useCountUp(70))
    expect(result.current).toBe(70)
  })

  it('re-animates toward a new target when it changes', async () => {
    const { result, rerender } = renderHook(({ target }) => useCountUp(target), { initialProps: { target: 70 } })
    await waitFor(() => expect(result.current).toBe(70), { timeout: 5000 })

    rerender({ target: 40 })
    await waitFor(() => expect(result.current).toBe(40), { timeout: 5000 })
  })
})
