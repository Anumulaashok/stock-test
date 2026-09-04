import { describe, expect, it } from 'vitest'

/**
 * I1's enforcement mechanism: fails the build if a chart or data-transform
 * file fabricates data instead of rendering what the backend returned.
 * `Math.random`/`faker`/`generateMockSeries`-shaped helpers have no
 * legitimate use in these directories -- every number on screen must
 * trace to a computation the backend already did. See PROJECT brief §4.5.
 *
 * Uses Vite's `import.meta.glob` (not Node's `fs`) so this stays a plain
 * browser-safe module under the app's Node-types-free tsconfig -- the
 * same reason chart/lib source itself never reaches for `fs`.
 *
 * Scans `api/` too, not just `components/`/`lib/`/`features/` --
 * reshaping (grouping, bucketing, filtering already-fetched rows) lives
 * in `api/`, and that is precisely where synthetic data would enter the
 * app if it ever did: one fabricated point slipped into a response
 * shape there would flow, unnoticed, into every chart downstream.
 */

const FORBIDDEN_PATTERNS = [/Math\.random\s*\(/, /\bfaker\b/i, /generateMock\w*\s*\(/]

// Files legitimately allowed to reference these terms (e.g. a future
// dedicated, explicitly-named and reviewed seeded-fixture helper). Keyed
// by the path as it appears in the glob below.
const ALLOWLIST = new Set<string>([])

const files = import.meta.glob(
  ['../components/**/*.{ts,tsx}', '../lib/**/*.{ts,tsx}', '../api/**/*.{ts,tsx}', '../features/**/*.{ts,tsx}'],
  { query: '?raw', import: 'default', eager: true },
) as Record<string, string>

describe('synthetic-data tripwire', () => {
  it('finds no Math.random/faker/generateMock-shaped helper under chart or data-transform directories', () => {
    const offenders: string[] = []

    for (const [path, content] of Object.entries(files)) {
      if (/\.test\.tsx?$/.test(path) || ALLOWLIST.has(path)) continue
      for (const pattern of FORBIDDEN_PATTERNS) {
        if (pattern.test(content)) {
          offenders.push(`${path} matches ${pattern}`)
        }
      }
    }

    expect(offenders).toEqual([])
  })
})
