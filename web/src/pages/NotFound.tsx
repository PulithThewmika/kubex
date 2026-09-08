import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { Reveal } from '../components/landing/Reveal'

export function NotFound() {
  return (
    <div className="relative flex min-h-[70vh] flex-col items-center justify-center overflow-hidden px-6 py-16 text-center">
      <div aria-hidden="true" className="absolute inset-0 text-accent/[0.07] halftone-lg" />

      <Reveal className="relative z-10 flex flex-col items-center">
        <p className="font-body text-xs font-bold uppercase tracking-[0.3em] text-accent">Error 404</p>
        <h1 className="mt-3 font-display text-[6rem] uppercase leading-[0.78] text-text text-outline sm:text-[10rem]">
          Lost.
        </h1>
        <p className="mt-6 max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
          That page doesn't exist or it moved. Nothing else on the platform is broken.
        </p>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/app"
            className="group inline-flex items-center gap-3 border-2 border-accent bg-accent px-6 py-3.5 font-display text-lg uppercase tracking-wide text-background transition-transform duration-300 hover:-translate-y-1 active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none"
          >
            Back to dashboard
            <ArrowRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transform-none" />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 border-2 border-text px-6 py-3.5 font-display text-lg uppercase tracking-wide text-text transition-colors duration-300 hover:border-accent hover:text-accent"
          >
            <ArrowLeft className="h-5 w-5" />
            Home
          </Link>
        </div>
      </Reveal>
    </div>
  )
}
