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

// Maximalist skin: white ground, black + orange type, hard borders. Same
// curtain-reveal + magnetic-button behaviour, no glass / gradients.
const STYLES = `
.kx-footer {
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

.kx-giant-text {
  font-family: 'Anton', 'Impact', sans-serif;
  font-size: 27vw;
  line-height: 0.72;
  letter-spacing: -0.05em;
  color: transparent;
  -webkit-text-stroke: 2px rgba(255, 87, 34, 0.28);
}

@keyframes kx-footer-heartbeat {
  0%, 100% { transform: scale(1); }
  15%, 45% { transform: scale(1.25); }
  30% { transform: scale(1); }
}
.kx-anim-heartbeat { animation: kx-footer-heartbeat 1.8s cubic-bezier(0.25, 1, 0.5, 1) infinite; }

@media (prefers-reduced-motion: reduce) {
  .kx-anim-heartbeat { animation: none; }
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

// Hero-style solid marquee, sized up.
const FooterMarquee = () => (
  <div className="marquee border-y-2 border-background bg-accent text-background" aria-hidden="true">
    <div className="marquee-track py-3">
      {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((t, i) => (
        <span
          key={i}
          className="inline-flex items-center font-display text-2xl uppercase tracking-wider md:text-4xl"
        >
          <span className="px-5">{t}</span>
          <span className="opacity-50">✦</span>
        </span>
      ))}
    </div>
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
        <footer className="kx-footer fixed bottom-0 left-0 flex h-screen w-full flex-col overflow-hidden border-t-2 border-background bg-text pt-16 text-background sm:pt-20">
          {/* Halftone texture */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-0 text-background/[0.07] halftone-lg"
          />

          {/* Giant background wordmark */}
          <div
            ref={giantTextRef}
            className="kx-giant-text pointer-events-none absolute -bottom-[3vh] left-1/2 z-0 -translate-x-1/2 select-none whitespace-nowrap uppercase"
          >
            KubeX
          </div>

          {/* Hero-style marquee */}
          <div className="relative z-10">
            <FooterMarquee />
          </div>

          {/* Center content */}
          <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6">
            <h2
              ref={headingRef}
              className="mb-12 text-center font-display text-6xl uppercase leading-[0.82] tracking-tight text-background sm:text-8xl lg:text-9xl"
            >
              See every <span className="text-accent">deploy.</span>
            </h2>

            <div ref={linksRef} className="flex w-full flex-col items-center gap-6">
              <div className="flex w-full flex-wrap justify-center gap-4">
                <MagneticButton
                  as="a"
                  href={cta.href}
                  className="group flex items-center gap-3 border-2 border-background bg-background px-8 py-4 font-display text-xl uppercase tracking-wide text-text transition-colors hover:bg-accent hover:text-background md:text-2xl"
                >
                  <LogIn className="h-6 w-6" />
                  {cta.label}
                </MagneticButton>
                <MagneticButton
                  as="a"
                  href="#how"
                  className="group flex items-center gap-3 border-2 border-background px-8 py-4 font-display text-xl uppercase tracking-wide text-background transition-colors hover:bg-background hover:text-text md:text-2xl"
                >
                  How it works
                  <ArrowRight className="h-6 w-6" />
                </MagneticButton>
              </div>

              <div className="mt-2 flex w-full flex-wrap justify-center gap-3 md:gap-4">
                {SECONDARY_LINKS.map((l) => (
                  <MagneticButton
                    key={l.label}
                    as="a"
                    href={l.href}
                    className="border-2 border-background px-6 py-3 font-body text-sm font-bold uppercase tracking-widest text-background transition-colors hover:bg-accent hover:text-background md:text-base"
                  >
                    {l.label}
                  </MagneticButton>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom bar — black strip */}
          <div className="relative z-20 flex w-full flex-col items-center justify-between gap-6 border-t-2 border-background bg-background px-6 py-6 text-text md:flex-row md:px-12">
            <div className="order-2 font-body text-[10px] font-bold uppercase tracking-widest text-text/60 md:order-1 md:text-xs">
              © 2026 KubeX
            </div>

            <div className="order-1 flex items-center gap-2 border-2 border-text px-5 py-2.5 md:order-2">
              <span className="font-body text-[10px] font-bold uppercase tracking-widest text-text/70 md:text-xs">
                Built with
              </span>
              <Heart className="kx-anim-heartbeat h-4 w-4 fill-accent text-accent" />
              <span className="font-body text-[10px] font-bold uppercase tracking-widest text-text/70 md:text-xs">
                for shipping teams
              </span>
            </div>

            <MagneticButton
              as="button"
              onClick={scrollToTop}
              aria-label="Back to top"
              className="group order-3 flex h-11 w-11 items-center justify-center border-2 border-text text-text transition-colors hover:bg-accent hover:text-background"
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
