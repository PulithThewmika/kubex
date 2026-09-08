// Shown by both RequireAuth and RootRoute when /auth/me genuinely fails
// (a 5xx), as distinct from "unauthenticated" — a transient backend outage
// shouldn't boot an already-logged-in user to /login or the marketing page.
export function AuthErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="relative flex h-dvh items-center justify-center overflow-hidden bg-background px-6 text-center text-text">
      <div aria-hidden="true" className="absolute inset-0 text-accent/[0.07] halftone-lg" />
      <div className="relative z-10 flex flex-col items-center">
        <p className="font-body text-xs font-bold uppercase tracking-[0.3em] text-accent">Connection lost</p>
        <h1 className="mt-3 max-w-md font-display text-4xl uppercase leading-[0.9] text-text sm:text-5xl">
          Couldn't verify your session.
        </h1>
        <p className="mt-4 max-w-sm font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
          Check your connection and try again.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-8 border-2 border-accent bg-accent px-6 py-3.5 font-display text-lg uppercase tracking-wide text-background transition-transform duration-300 hover:-translate-y-1 active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none"
        >
          Retry
        </button>
      </div>
    </div>
  )
}
