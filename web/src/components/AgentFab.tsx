import { useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { gsap } from 'gsap'
import { DURATION, EASE, prefersReducedMotion } from '@/lib/motion'
import { ThinkingOrb } from './ui/thinking-orbs'

// Floating "ask the agent" button — bottom-right on every authenticated page
// except Chat itself. The ThinkingOrb sits centred on a dark pill; on
// hover/focus a GSAP tween slides the label open (instant under reduced motion).
export function AgentFab() {
  const { pathname } = useLocation()
  const labelRef = useRef<HTMLSpanElement>(null)
  const tween = useRef<gsap.core.Tween | null>(null)

  if (pathname.startsWith('/app/chat')) return null

  function animate(open: boolean) {
    const el = labelRef.current
    if (!el) return
    tween.current?.kill()

    // GSAP can't tween to width:"auto" — measure the natural width, then pin
    // the element back to where it currently is so the tween starts smoothly.
    let target = 0
    if (open) {
      const current = el.getBoundingClientRect().width
      el.style.width = 'auto'
      target = el.getBoundingClientRect().width
      el.style.width = `${current}px`
    }

    const to = { width: target, opacity: open ? 1 : 0, marginLeft: open ? 12 : 0 }
    if (prefersReducedMotion()) {
      gsap.set(el, to)
      return
    }
    tween.current = gsap.to(el, {
      ...to,
      duration: open ? DURATION.base : DURATION.fast,
      ease: EASE.smooth,
    })
  }

  return (
    <Link
      to="/app/chat"
      aria-label="Ask the KubeX agent"
      onMouseEnter={() => animate(true)}
      onMouseLeave={() => animate(false)}
      onFocus={() => animate(true)}
      onBlur={() => animate(false)}
      className="group fixed bottom-6 right-6 z-40 flex items-center rounded-full border-2 border-ink bg-ink p-1.5 text-paper shadow-[4px_4px_0_0_rgba(22,23,26,0.25)] transition-transform duration-300 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_rgba(22,23,26,0.3)] sm:bottom-8 sm:right-8"
    >
      <span className="flex size-11 shrink-0 items-center justify-center [&_canvas]:!block [&_canvas]:!size-11">
        <ThinkingOrb state="composing" size={64} theme="dark" />
      </span>
      <span
        ref={labelRef}
        className="w-0 overflow-hidden whitespace-nowrap pr-2 font-body text-xs font-bold uppercase tracking-[0.15em] opacity-0"
      >
        Ask KubeX
      </span>
    </Link>
  )
}
