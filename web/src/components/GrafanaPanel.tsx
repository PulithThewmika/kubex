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

type Status = 'loading' | 'loaded' | 'no-source' | 'error'

export function GrafanaPanel({ uid, panelId, service, from = 'now-6h', to = 'now', title }: GrafanaPanelProps) {
  const [status, setStatus] = useState<Status>('loading')

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
    // The proxy renders the panel to PNG server-side (#835), so <img> is
    // enough. A GET preflight lets us tell "no metrics source connected"
    // (503, the org has no connected cluster or a relay timeout) apart
    // from a genuine render failure — otherwise both would just be a
    // broken image. Deliberately plain fetch, not apiFetch: a 401 here is
    // a stale Grafana service-account token, not the user's session.
    fetch(src, { credentials: 'include' })
      .then((res) => {
        if (cancelled) return
        if (res.status === 503) setStatus('no-source')
        else if (!res.ok) setStatus('error')
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
      {status === 'no-source' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-4 text-center">
          <p className="text-sm font-medium text-text">No metrics source connected</p>
          <p className="text-xs text-text-muted">
            {title} needs a connected cluster. Connect one to start seeing metrics.
          </p>
          <Link
            to="/app/settings?tab=connections"
            className="mt-1 text-xs font-medium text-accent hover:underline"
          >
            Connect a cluster
          </Link>
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-4 text-center">
          <p className="text-sm font-medium text-text">Panel failed to load</p>
          <p className="text-xs text-text-muted">The {title} panel couldn't be rendered. Try again shortly.</p>
        </div>
      )}
      <img
        alt={title}
        src={src}
        className={`h-full w-full object-contain ${status === 'loaded' ? '' : 'invisible'}`}
        onLoad={() => setStatus((s) => (s === 'no-source' || s === 'error' ? s : 'loaded'))}
        onError={() => setStatus((s) => (s === 'no-source' ? s : 'error'))}
      />
    </div>
  )
}
