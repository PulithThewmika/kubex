import * as React from 'react'
import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { ArrowRight, ArrowUp, Heart, LogIn } from 'lucide-react'
import { cn } from '@/lib/utils'

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger)
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// -------------------------------------------------------------------------
// Theme-adaptive inline styles — remapped from shadcn tokens to the KubeX
// palette (orange / white / near-black) and Anton/Inter fonts.
// -------------------------------------------------------------------------
const STYLES = `
.kx-footer {
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;

  --kx-fg: #E6E8EB;
  --kx-bg: #0A0B0D;
  --kx-acc: #FF5722;
  --kx-fail: #F85149;

  --pill-bg-1: color-mix(in srgb, var(--kx-fg) 4%, transparent);
  --pill-bg-2: color-mix(in srgb, var(--kx-fg) 1%, transparent);
  --pill-shadow: color-mix(in srgb, var(--kx-bg) 55%, transparent);
  --pill-highlight: color-mix(in srgb, var(--kx-fg) 12%, transparent);
  --pill-inset-shadow: color-mix(in srgb, var(--kx-bg) 80%, transparent);
  --pill-border: color-mix(in srgb, var(--kx-fg) 12%, transparent);

  --pill-bg-1-hover: color-mix(in srgb, var(--kx-acc) 14%, transparent);
  --pill-bg-2-hover: color-mix(in srgb, var(--kx-acc) 4%, transparent);
  --pill-border-hover: var(--kx-acc);
  --pill-shadow-hover: color-mix(in srgb, var(--kx-acc) 30%, transparent);
  --pill-highlight-hover: color-mix(in srgb, var(--kx-fg) 22%, transparent);
}

@keyframes kx-footer-breathe {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
  100% { transform: translate(-50%, -50%) scale(1.12); opacity: 0.9; }
}
@keyframes kx-footer-marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
@keyframes kx-footer-heartbeat {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 0 4px color-mix(in srgb, var(--kx-acc) 45%, transparent)); }
  15%, 45% { transform: scale(1.2); filter: drop-shadow(0 0 9px color-mix(in srgb, var(--kx-acc) 80%, transparent)); }
  30% { transform: scale(1); }
}

.kx-anim-breathe { animation: kx-footer-breathe 8s ease-in-out infinite alternate; }
.kx-anim-marquee { animation: kx-footer-marquee 38s linear infinite; }
.kx-anim-heartbeat { animation: kx-footer-heartbeat 2s cubic-bezier(0.25, 1, 0.5, 1) infinite; }

.kx-footer-grid {
  background-size: 56px 56px;
  background-image:
    linear-gradient(to right, color-mix(in srgb, var(--kx-fg) 4%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in srgb, var(--kx-fg) 4%, transparent) 1px, transparent 1px);
  mask-image: linear-gradient(to bottom, transparent, black 30%, black 70%, transparent);
  -webkit-mask-image: linear-gradient(to bottom, transparent, black 30%, black 70%, transparent);
}

.kx-footer-aurora {
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in srgb, var(--kx-acc) 22%, transparent) 0%,
    color-mix(in srgb, var(--kx-acc) 8%, transparent) 45%,
    transparent 70%
  );
}

.kx-glass-pill {
  background: linear-gradient(145deg, var(--pill-bg-1) 0%, var(--pill-bg-2) 100%);
  box-shadow:
    0 10px 30px -10px var(--pill-shadow),
    inset 0 1px 1px var(--pill-highlight),
    inset 0 -1px 2px var(--pill-inset-shadow);
  border: 1.5px solid var(--pill-border);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.kx-glass-pill:hover {
  background: linear-gradient(145deg, var(--pill-bg-1-hover) 0%, var(--pill-bg-2-hover) 100%);
  border-color: var(--pill-border-hover);
  box-shadow: 0 20px 40px -10px var(--pill-shadow-hover), inset 0 1px 1px var(--pill-highlight-hover);
  color: var(--kx-fg);
}

.kx-giant-text {
  font-family: 'Anton', 'Impact', sans-serif;
  font-size: 26vw;
  line-height: 0.75;
  letter-spacing: -0.04em;
  color: transparent;
  -webkit-text-stroke: 1.5px color-mix(in srgb, var(--kx-acc) 22%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--kx-fg) 8%, transparent) 0%, transparent 62%);
  -webkit-background-clip: text;
  background-clip: text;
}

.kx-text-glow {
  background: linear-gradient(180deg, var(--kx-fg) 0%, color-mix(in srgb, var(--kx-fg) 40%, transparent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0 0 22px color-mix(in srgb, var(--kx-acc) 18%, transparent));
}

@media (prefers-reduced-motion: reduce) {
  .kx-anim-breathe, .kx-anim-marquee, .kx-anim-heartbeat { animation: none; }
}
`

// -------------------------------------------------------------------------
// Magnetic button primitive
// -------------------------------------------------------------------------
export type MagneticButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    as?: React.ElementType
  }

const MagneticButton = React.forwardRef<HTMLElement, MagneticButtonProps>(
  ({ className, children, as: Component = 'button', ...props }, forwardedRef) => {
    const localRef = useRef<HTMLElement | null>(null)

    useEffect(() => {
      if (typeof window === 'undefined' || prefersReducedMotion()) return
      const element = localRef.current
      if (!element) return

      const ctx = gsap.context(() => {
        const handleMouseMove = (e: MouseEvent) => {
          const rect = element.getBoundingClientRect()
          const x = e.clientX - rect.left - rect.width / 2
          const y = e.clientY - rect.top - rect.height / 2
          gsap.to(element, {
            x: x * 0.35,
            y: y * 0.35,
            rotationX: -y * 0.12,
            rotationY: x * 0.12,
            scale: 1.05,
            ease: 'power2.out',
            duration: 0.4,
          })
        }
        const handleMouseLeave = () => {
          gsap.to(element, {
            x: 0,
            y: 0,
            rotationX: 0,
            rotationY: 0,
            scale: 1,
            ease: 'elastic.out(1, 0.3)',
            duration: 1.1,
          })
        }
        element.addEventListener('mousemove', handleMouseMove)
        element.addEventListener('mouseleave', handleMouseLeave)
        return () => {
          element.removeEventListener('mousemove', handleMouseMove)
          element.removeEventListener('mouseleave', handleMouseLeave)
        }
      }, element)

      return () => ctx.revert()
    }, [])

    return (
      <Component
        ref={(node: HTMLElement) => {
          localRef.current = node
          if (typeof forwardedRef === 'function') forwardedRef(node)
          else if (forwardedRef)
            (forwardedRef as React.MutableRefObject<HTMLElement | null>).current = node
        }}
        className={cn('cursor-pointer', className)}
        {...props}
      >
        {children}
      </Component>
    )
  },
)
MagneticButton.displayName = 'MagneticButton'

// -------------------------------------------------------------------------
// Footer
// -------------------------------------------------------------------------
const MARQUEE_ITEMS = [
  'Deployment-aware observability',
  'Health scoring',
  'DORA metrics',
  'Blast radius',
  'CI · CD · Runtime, correlated',
  'One record per deploy',
]

const MarqueeRun = () => (
  <div className="flex items-center gap-10 px-5">
    {MARQUEE_ITEMS.map((item, i) => (
      <React.Fragment key={item}>
        <span>{item}</span>
        <span className={i % 2 === 0 ? 'text-[var(--kx-acc)]' : 'text-[var(--kx-fg)]/40'}>✦</span>
      </React.Fragment>
    ))}
  </div>
)

type Cta = { href: string; label: string }

const SECONDARY_LINKS = [
  { label: 'Privacy', href: '#' },
  { label: 'Terms', href: '#' },
  { label: 'Contact', href: '#' },
]

export function CinematicFooter({ cta }: { cta: Cta }) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const giantTextRef = useRef<HTMLDivElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const linksRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typeof window === 'undefined' || prefersReducedMotion()) return
    if (!wrapperRef.current) return

    const ctx = gsap.context(() => {
      gsap.fromTo(
        giantTextRef.current,
        { y: '10vh', scale: 0.85, opacity: 0 },
        {
          y: '0vh',
          scale: 1,
          opacity: 1,
          ease: 'power1.out',
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: 'top 80%',
            end: 'bottom bottom',
            scrub: 1,
          },
        },
      )
      gsap.fromTo(
        [headingRef.current, linksRef.current],
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.15,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: 'top 40%',
            end: 'bottom bottom',
            scrub: 1,
          },
        },
      )
    }, wrapperRef)

    return () => ctx.revert()
  }, [])

  const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />

      {/* Curtain-reveal wrapper: clip-path makes it the containing block for
          the fixed footer, so the footer only shows within this box. */}
      <div ref={wrapperRef} className="relative h-screen w-full" style={{ clipPath: 'inset(0)' }}>
        <footer className="kx-footer fixed bottom-0 left-0 flex h-screen w-full flex-col justify-between overflow-hidden border-t-2 border-text bg-background text-text">
          {/* Ambient light + grid */}
          <div className="kx-footer-aurora kx-anim-breathe pointer-events-none absolute left-1/2 top-1/2 z-0 h-[55vh] w-[80vw] -translate-x-1/2 -translate-y-1/2 rounded-[50%] blur-[80px]" />
          <div className="kx-footer-grid pointer-events-none absolute inset-0 z-0" />

          {/* Giant background wordmark */}
          <div
            ref={giantTextRef}
            className="kx-giant-text pointer-events-none absolute -bottom-[4vh] left-1/2 z-0 -translate-x-1/2 select-none whitespace-nowrap uppercase"
          >
            KubeX
          </div>

          {/* Diagonal marquee */}
          <div className="absolute left-0 top-24 z-10 w-full -rotate-2 scale-110 overflow-hidden border-y-2 border-border bg-background/70 py-3 shadow-2xl backdrop-blur-md">
            <div className="kx-anim-marquee flex w-max text-[11px] font-bold uppercase tracking-[0.28em] text-text-muted md:text-xs">
              <MarqueeRun />
              <MarqueeRun />
            </div>
          </div>

          {/* Center content */}
          <div className="relative z-10 mx-auto mt-24 flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6">
            <h2
              ref={headingRef}
              className="kx-text-glow mb-12 text-center font-display text-5xl uppercase leading-[0.85] tracking-tight md:text-8xl"
            >
              See every deploy.
            </h2>

            <div ref={linksRef} className="flex w-full flex-col items-center gap-6">
              <div className="flex w-full flex-wrap justify-center gap-4">
                <MagneticButton
                  as="a"
                  href={cta.href}
                  className="kx-glass-pill group flex items-center gap-3 rounded-full px-9 py-4 font-display text-sm uppercase tracking-wide text-text md:text-base"
                >
                  <LogIn className="h-5 w-5 text-text-muted transition-colors group-hover:text-accent" />
                  {cta.label}
                </MagneticButton>
                <MagneticButton
                  as="a"
                  href="#how"
                  className="kx-glass-pill group flex items-center gap-3 rounded-full px-9 py-4 font-display text-sm uppercase tracking-wide text-text md:text-base"
                >
                  How it works
                  <ArrowRight className="h-5 w-5 text-text-muted transition-colors group-hover:text-accent" />
                </MagneticButton>
              </div>

              <div className="mt-2 flex w-full flex-wrap justify-center gap-3 md:gap-5">
                {SECONDARY_LINKS.map((l) => (
                  <MagneticButton
                    key={l.label}
                    as="a"
                    href={l.href}
                    className="kx-glass-pill rounded-full px-6 py-3 font-body text-xs font-medium uppercase tracking-widest text-text-muted hover:text-text md:text-sm"
                  >
                    {l.label}
                  </MagneticButton>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="relative z-20 flex w-full flex-col items-center justify-between gap-6 px-6 pb-8 md:flex-row md:px-12">
            <div className="order-2 font-body text-[10px] font-semibold uppercase tracking-widest text-text-faint md:order-1 md:text-xs">
              © 2026 KubeX
            </div>

            <div className="kx-glass-pill order-1 flex cursor-default items-center gap-2 rounded-full px-6 py-3 md:order-2">
              <span className="font-body text-[10px] font-bold uppercase tracking-widest text-text-muted md:text-xs">
                Built with
              </span>
              <Heart className="kx-anim-heartbeat h-4 w-4 fill-accent text-accent" />
              <span className="font-body text-[10px] font-bold uppercase tracking-widest text-text-muted md:text-xs">
                for shipping teams
              </span>
            </div>

            <MagneticButton
              as="button"
              onClick={scrollToTop}
              aria-label="Back to top"
              className="kx-glass-pill group order-3 flex h-12 w-12 items-center justify-center rounded-full text-text-muted hover:text-text"
            >
              <ArrowUp className="h-5 w-5 transition-transform duration-300 group-hover:-translate-y-1" />
            </MagneticButton>
          </div>
        </footer>
      </div>
    </>
  )
}

export default CinematicFooter
