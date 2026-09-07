// Shown by both RequireAuth and RootRoute when /auth/me genuinely fails
// (a 5xx), as distinct from "unauthenticated" — a transient backend outage
// shouldn't boot an already-logged-in user to /login or the marketing page.
export function AuthErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex h-dvh items-center justify-center bg-background px-4 text-center">
      <div>
        <p className="text-sm text-text-muted">Couldn't verify your session. Check your connection and try again.</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface"
        >
          Retry
        </button>
      </div>
    </div>
  )
}
