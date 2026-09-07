import { Component, type ErrorInfo, type ReactNode } from 'react'

type ErrorBoundaryProps = {
  children: ReactNode
}

type ErrorBoundaryState = {
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
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
        <h1 className="font-heading text-xl font-semibold text-text">Something went wrong</h1>
        <p className="max-w-sm text-sm text-text-muted">
          An unexpected error broke this view. Trying again often clears it; if not, head back to the
          dashboard.
        </p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={this.handleRetry}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-background transition-opacity hover:opacity-90"
          >
            Try again
          </button>
          <a
            href="/app"
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text transition-colors hover:border-accent/50"
          >
            Back to dashboard
          </a>
        </div>
      </div>
    )
  }
}
