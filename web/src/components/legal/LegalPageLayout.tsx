import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Reveal } from '../landing/Reveal'

type LegalPageLayoutProps = {
  eyebrow: string
  title: string
  updated: string
  children: ReactNode
}

// Bare standalone page (no landing nav/footer) for /privacy and /terms,
// following the same halftone + outlined-heading treatment as NotFound.tsx.
export function LegalPageLayout({ eyebrow, title, updated, children }: LegalPageLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()

  // location.key is 'default' only for the very first entry in this tab's
  // history (e.g. a fresh tab opened straight at /privacy) — in that case
  // there's nothing to go back to, so fall back to the landing page instead
  // of leaving the SPA history stack.
  const goBack = () => {
    if (location.key !== 'default') navigate(-1)
    else navigate('/')
  }

  return (
    <div className="relative overflow-hidden px-6 py-16 sm:px-10">
      <div aria-hidden="true" className="absolute inset-0 text-accent/[0.07] halftone-lg" />

      <div className="relative z-10 mx-auto max-w-3xl">
        <Reveal>
          <button
            type="button"
            onClick={goBack}
            className="inline-flex items-center gap-2 font-body text-xs font-bold uppercase tracking-widest text-text-muted transition-colors hover:text-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          <p className="mt-8 font-body text-xs font-bold uppercase tracking-[0.3em] text-accent">{eyebrow}</p>
          <h1 className="mt-3 font-display text-5xl uppercase leading-[0.85] text-text sm:text-7xl">{title}</h1>
          <p className="mt-4 font-body text-xs font-semibold uppercase tracking-wide text-text-faint">
            Last updated {updated}
          </p>

          <div className="prose-legal mt-12 flex flex-col gap-8 font-body text-sm leading-relaxed text-text-muted">
            {children}
          </div>
        </Reveal>
      </div>
    </div>
  )
}
