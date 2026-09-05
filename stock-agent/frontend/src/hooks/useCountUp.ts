import { useEffect, useState } from 'react'

const DURATION_MS = 700

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

/**
 * Counts up to `target` on mount/change -- the app's one deliberate
 * count-up treatment (spent on the hero investment-view score only,
 * not spread across every numeric). Returns `target` directly with no
 * animation when it's null (nothing to animate toward) or the OS asks
 * for reduced motion.
 */
export function useCountUp(target: number | null): number | null {
  const skipAnimation = target === null || prefersReducedMotion()
  const [animatedValue, setAnimatedValue] = useState(0)

  useEffect(() => {
    if (skipAnimation) return
    const start = performance.now()
    let frame: number
    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(elapsed / DURATION_MS, 1)
      setAnimatedValue(Math.round(progress * (target as number)))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, skipAnimation])

  return skipAnimation ? target : animatedValue
}
