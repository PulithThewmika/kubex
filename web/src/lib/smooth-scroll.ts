import { gsap } from 'gsap'
import { ScrollToPlugin } from 'gsap/ScrollToPlugin'
import { prefersReducedMotion } from './motion'

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollToPlugin)
}

/**
 * Eased scroll to an anchor (`#id`) or a y position. Clears the sticky header
 * so the target isn't hidden underneath it. User-initiated navigation, so it
 * stays smooth under reduced motion — just quicker.
 */
export function smoothScrollTo(target: string | number, headerOffset = 0) {
  if (typeof window === 'undefined') return
  const duration = prefersReducedMotion() ? 0.3 : 0.8
  gsap.to(window, {
    duration,
    ease: 'power2.inOut',
    overwrite: 'auto',
    scrollTo:
      typeof target === 'number'
        ? target
        : { y: target, offsetY: headerOffset, autoKill: true },
  })
}

/** Height of the sticky header, plus a little breathing room. */
export function headerOffset() {
  if (typeof document === 'undefined') return 0
  return (document.querySelector('header')?.offsetHeight ?? 80) + 12
}
