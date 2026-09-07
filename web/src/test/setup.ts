import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement ResizeObserver; components (e.g. PipelineTimeline's
// useElementWidth) that rely on it need a stub or every render test crashes.
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jsdom doesn't implement scrollIntoView either (ChatWindow's auto-scroll).
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// jsdom implements neither IntersectionObserver (Landing page scroll reveals)
// nor matchMedia (prefers-reduced-motion check) — stub both so component
// tests that render these don't crash. Tests exercising the reveal behavior
// itself override window.IntersectionObserver/matchMedia per-test.
if (!globalThis.IntersectionObserver) {
  globalThis.IntersectionObserver = class IntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof IntersectionObserver
}
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as unknown as MediaQueryList
}

afterEach(cleanup)
