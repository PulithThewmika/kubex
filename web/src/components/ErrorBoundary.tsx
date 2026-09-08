import { Component, type ErrorInfo, type ReactNode } from 'react'

type ErrorBoundaryProps = {
  children: ReactNode
  // When this value changes, a caught error is cleared so children reconcile
  // normally. Pass the route path so navigating away from a crashed page
  // recovers — without remounting children on every same-route render.
  resetKey?: unknown
}

type ErrorBoundaryState = {
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // ponytail: console only — no error-reporting backend in this project.
    // Swap for a real sink (Sentry etc.) here if one is ever added.
    console.error('Uncaught render error:', error, info.componentStack)
  }

  handleRetry = () => {
    this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-4 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-full border border-failed/30 bg-failed/10 text-failed">
          <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
            <path d="M12 8v5M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
          </svg>
        </div>
        <h1 className="font-heading text-xl font-semibold text-text">Something went wrong</h1>
        <p className="max-w-sm text-sm leading-relaxed text-text-muted">
          An unexpected error broke this view. Trying again often clears it; if not, head back to the
          dashboard.
        </p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={this.handleRetry}
            className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-semibold text-background transition-colors hover:bg-accent-hover active:translate-y-px"
          >
            Try again
          </button>
          <a
            href="/app"
            className="rounded-md border border-border-strong px-3.5 py-1.5 text-sm font-medium text-text transition-colors hover:border-accent hover:text-accent"
          >
            Back to dashboard
          </a>
        </div>
      </div>
    )
  }
}
