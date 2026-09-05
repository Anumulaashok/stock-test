import '@testing-library/jest-dom/vitest'
// jsdom has no real canvas implementation -- Chart.js (ForecastLineChart)
// needs a 2D context to construct without throwing. This polyfills just
// enough of the Canvas API for that; it never asserts on actual pixels.
import 'vitest-canvas-mock'

// jsdom also has no ResizeObserver -- Chart.js's `responsive: true` option
// uses one to redraw on container resize, which tests never trigger, so a
// no-op stub is enough.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub
