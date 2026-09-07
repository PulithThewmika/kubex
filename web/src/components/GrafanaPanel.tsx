import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

type GrafanaPanelProps = {
  uid: string
  panelId: number
  service: string
  from?: string
  to?: string
  title: string
}

export function GrafanaPanel({ uid, panelId, service, from = 'now-6h', to = 'now', title }: GrafanaPanelProps) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading')

  const params = new URLSearchParams({
    uid,
    panelId: String(panelId),
    'var-service': service,
    from,
    to,
    theme: 'dark',
  })
  const src = `/api/grafana/proxy?${params.toString()}`

  useEffect(() => {
    setStatus('loading')
    let cancelled = false
    // <iframe onError> only fires on network-level failures — a 502 from
    // the proxy (e.g. Grafana unreachable) still "loads" its error body
    // successfully and fires onLoad, never onError. A GET preflight lets
    // us catch real backend failures the iframe itself can't detect.
    // (The route is GET-only — HEAD returns 405 — so this duplicates the
    // iframe's own request; acceptable for two lightweight panels a page.)
    //
    // Deliberately plain fetch, not apiFetch: the proxy forwards Grafana's
    // own upstream status verbatim (grafana.py), so a 401 here means
    // Grafana's service-account token is stale, not that the user's
    // session expired — routing it through apiFetch would force an
    // app-wide logout over a Grafana-side misconfiguration.
    fetch(src, { credentials: 'include' })
      .then((res) => {
        if (!cancelled && !res.ok) setStatus('error')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [src])

  return (
    <div className="relative h-64 overflow-hidden rounded-lg border border-border bg-surface">
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-text-muted">
          Loading {title}…
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-4 text-center">
          <p className="text-sm font-medium text-text">Metrics not available</p>
          <p className="text-xs text-text-muted">
            The {title} panel needs a connected Prometheus data source.
          </p>
          <Link
            to="/app/settings?tab=connections"
            className="mt-1 text-xs font-medium text-accent hover:underline"
          >
            Connect Prometheus
          </Link>
        </div>
      )}
      <iframe
        title={title}
        src={src}
        className={`h-full w-full border-0 ${status === 'loaded' ? '' : 'invisible'}`}
        onLoad={() => setStatus((s) => (s === 'error' ? s : 'loaded'))}
        onError={() => setStatus('error')}
      />
    </div>
  )
}
