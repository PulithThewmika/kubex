// Shared motion tokens. Keep animation values here, not scattered through
// components. Tuned to the maximalist landing: quick, decisive, no bounce.

export const DURATION = {
  fast: 0.25,
  base: 0.5,
  slow: 0.8,
  xslow: 1.1,
} as const

export const EASE = {
  /** GSAP — snappy decisive settle, for headline / hero reveals. */
  premium: 'expo.out',
  /** GSAP — general content reveals. */
  smooth: 'power3.out',
  /** GSAP — soft, for imagery / scale. */
  soft: 'power2.out',
  /** CSS cubic-bezier — hover / tap micro-interactions. */
  css: 'cubic-bezier(0.16, 1, 0.3, 1)',
} as const

export const DISTANCE = {
  xs: 8,
  sm: 14,
  md: 24,
  lg: 48,
} as const

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches
