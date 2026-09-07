import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useInstallations } from '../hooks/useInstallations'
import { ClustersSection } from '../components/ClustersSection'
import { AddClusterModal } from '../components/AddClusterModal'
import { RotateTokenDialog } from '../components/RotateTokenDialog'
import type { Installation } from '../types/installation'
import type { Cluster } from '../types/cluster'

// The GitHub App's slug is a separate identity from this repo's name (set at
// app registration, not touched by EPIC-025's DeployLens -> KubeX rename) —
// override via VITE_GITHUB_APP_SLUG if the registered app isn't "deploylens".
const GITHUB_APP_SLUG = import.meta.env.VITE_GITHUB_APP_SLUG ?? 'deploylens'
const GITHUB_APP_INSTALL_URL = `https://github.com/apps/${GITHUB_APP_SLUG}/installations/new`

const STATUS_STYLES: Record<Installation['status'], string> = {
  active: 'bg-healthy/10 text-healthy',
  suspended: 'bg-degraded/10 text-degraded',
  removed: 'bg-failed/10 text-failed',
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.5 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.46-1.19-1.11-1.51-1.11-1.51-.91-.64.07-.63.07-.63 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05a9.3 9.3 0 0 1 2.5-.35c.85 0 1.7.12 2.5.35 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .28.18.61.69.5A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  )
}

function StatusBadge({ status }: { status: Installation['status'] }) {
  return (
    <span className={`w-fit rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[status]}`}>
      {status}
    </span>
  )
}

function InstallationRow({ installation }: { installation: Installation }) {
  return (
    <li className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-medium text-text">{installation.account_login}</p>
        <p className="mt-1 text-xs text-text-muted">
          {installation.repos.length > 0 ? installation.repos.join(', ') : 'No repos selected'}
        </p>
      </div>
      <StatusBadge status={installation.status} />
    </li>
  )
}

export function Settings() {
  const [showAddCluster, setShowAddCluster] = useState(false)
  const [rotatingCluster, setRotatingCluster] = useState<Cluster | null>(null)
  const [searchParams] = useSearchParams()
  const installationId = searchParams.get('installation_id')
  const { data: installations, isLoading, isError } = useInstallations({
    pollForInstallationId: installationId,
  })

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="font-heading text-2xl font-semibold text-text">Settings</h1>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Connect GitHub</h2>
        <p className="mt-1 text-sm text-text-muted">
          Install the KubeX GitHub App to automatically provision webhooks for your repos.
        </p>

        {installationId && (
          <div
            role="status"
            className="mt-4 rounded-md border border-healthy/30 bg-healthy/10 px-4 py-3 text-sm text-healthy"
          >
            GitHub App installation #{installationId} connected successfully.
          </div>
        )}

        <a
          href={GITHUB_APP_INSTALL_URL}
          className="mt-4 flex w-fit items-center gap-2 rounded-md bg-text px-4 py-2.5 text-sm font-medium text-background transition-colors hover:opacity-90"
        >
          <GitHubIcon />
          Connect GitHub
        </a>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-text-muted">Loading installations…</p>}
          {isError && <p className="text-sm text-failed">Failed to load installations.</p>}
          {!isLoading && !isError && installations && installations.length === 0 && !installationId && (
            <p className="text-sm text-text-muted">No GitHub App installations yet.</p>
          )}
          {installations && installations.length > 0 && (
            <ul className="flex flex-col gap-3">
              {installations.map((installation) => (
                <InstallationRow key={installation.id} installation={installation} />
              ))}
            </ul>
          )}
        </div>
      </section>

      <ClustersSection onAddCluster={() => setShowAddCluster(true)} onRotateToken={setRotatingCluster} />

      {showAddCluster && <AddClusterModal onClose={() => setShowAddCluster(false)} />}
      {rotatingCluster && (
        <RotateTokenDialog cluster={rotatingCluster} onClose={() => setRotatingCluster(null)} />
      )}
    </div>
  )
}
