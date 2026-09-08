import { Link } from 'react-router-dom'

// Empty state for "no services connected yet" — bare illustration on the left,
// a vertical bordered "table" of copy on the right, echoing the landing
// "How it works" cell sizing (font-display titles, font-body body text).
export function NoServicesEmpty() {
  return (
    <div
      role="status"
      className="flex flex-col items-start gap-8 md:flex-row md:items-center md:gap-12"
    >
      <img
        src="/Noservice.png"
        alt=""
        className="w-full max-w-xs select-none object-contain md:max-w-sm"
      />

      <div className="grid w-full gap-px border-2 border-paper-line bg-paper-line md:max-w-md">
        <div className="bg-paper-raised p-6">
          <h2 className="font-display text-3xl uppercase leading-none text-ink sm:text-4xl">No services yet</h2>
        </div>
        <div className="bg-paper-raised p-6">
          <p className="font-body text-sm leading-relaxed text-ink-muted">
            Services appear here once a deployment webhook fires.
          </p>
        </div>
        <div className="bg-paper-raised p-6">
          <Link
            to="/app/settings?tab=connections"
            className="inline-block border-2 border-accent bg-accent px-5 py-2.5 font-display text-xl uppercase tracking-wide text-background transition-transform hover:-translate-y-0.5"
          >
            Connect a repository →
          </Link>
        </div>
      </div>
    </div>
  )
}
