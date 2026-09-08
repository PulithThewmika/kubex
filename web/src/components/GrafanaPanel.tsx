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
  const [imgUrl, setImgUrl] = useState<string | null>(null)

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
    setImgUrl(null)
    let cancelled = false
    let objectUrl: string | null = null

    // One request, not two: server-side PNG rendering is expensive (a
    // headless-Chrome render + a bounded relay round-trip), so fetch the
    // image once and point <img> at an object URL rather than letting the
    // browser issue a second identical render. The response status still
    // distinguishes "no metrics source" (503) from a render failure.
    // Plain fetch, not apiFetch: a 401 here is a stale Grafana SA token,
    // not the user's session.
    fetch(src, { credentials: 'include' })
      .then(async (res) => {
        if (cancelled) return
        if (res.status === 503) {
          setStatus('no-source')
          return
        }
        if (!res.ok) {
          setStatus('error')
          return
        }
        objectUrl = URL.createObjectURL(await res.blob())
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        setImgUrl(objectUrl)
        setStatus('loaded')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])

  return (
    <div className="relative h-64 overflow-hidden border-2 border-paper-line-soft bg-paper-raised">
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center gap-2 font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-paper-line-soft border-t-accent" aria-hidden="true" />
          Loading {title}
        </div>
      )}
      {status === 'no-source' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-4 text-center">
          <p className="font-heading text-sm font-bold uppercase tracking-tight text-ink">No metrics source connected</p>
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
            {title} needs a connected cluster. Connect one to start seeing metrics.
          </p>
          <Link
            to="/app/settings?tab=connections"
            className="mt-1 font-body text-xs font-bold uppercase tracking-wide text-accent hover:underline"
          >
            Connect a cluster
          </Link>
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-4 text-center">
          <p className="font-heading text-sm font-bold uppercase tracking-tight text-ink">Panel failed to load</p>
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
            The {title} panel couldn't be rendered. Try again shortly.
          </p>
        </div>
      )}
      {imgUrl && (
        <img alt={title} src={imgUrl} className="h-full w-full object-contain" />
      )}
    </div>
  )
}
