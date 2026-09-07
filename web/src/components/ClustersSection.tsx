import { formatDistanceToNow } from 'date-fns'
import { useClusters } from '../hooks/useClusters'
import { StatusBadge } from './StatusBadge'
import type { Cluster } from '../types/cluster'

const CLUSTER_STATUS_VARIANT: Record<Cluster['status'], 'healthy' | 'degraded' | 'failed'> = {
  connected: 'healthy',
  pending: 'degraded',
  disconnected: 'failed',
}

// Agent-reported component status is a small free-text vocabulary
// ("found" / "not_found" / "rbac_denied" / "patch_failed", see
// services/cluster-agent/cluster_agent/{argocd,prometheus}.py) rather than
// a fixed enum — render it as-is rather than hardcoding every value here.
function formatComponentStatus(status: string | null): string {
  if (!status) return 'Not checked yet'
  return status.replaceAll('_', ' ')
}

type ClusterRowProps = {
  cluster: Cluster
  onRotateToken: (cluster: Cluster) => void
}

function ClusterRow({ cluster, onRotateToken }: ClusterRowProps) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text">{cluster.name}</span>
          <StatusBadge variant={CLUSTER_STATUS_VARIANT[cluster.status]}>{cluster.status}</StatusBadge>
        </div>
        <p className="text-xs text-text-muted">
          ArgoCD: {formatComponentStatus(cluster.argocd_status)} · Prometheus:{' '}
          {formatComponentStatus(cluster.prometheus_status)}
        </p>
        <p className="text-xs text-text-muted">
          {cluster.last_heartbeat
            ? `Last heartbeat ${formatDistanceToNow(new Date(cluster.last_heartbeat), { addSuffix: true })}`
            : 'No heartbeat received yet'}
        </p>
      </div>
      <button
        type="button"
        onClick={() => onRotateToken(cluster)}
        className="w-fit rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-background"
      >
        Rotate token
      </button>
    </li>
  )
}

type ClustersSectionProps = {
  onAddCluster: () => void
  onRotateToken: (cluster: Cluster) => void
}

export function ClustersSection({ onAddCluster, onRotateToken }: ClustersSectionProps) {
  const { data: clusters, isLoading, isError } = useClusters()

  return (
    <section className="mt-10">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Clusters</h2>
        <button
          type="button"
          onClick={onAddCluster}
          className="rounded-md bg-text px-3 py-1.5 text-xs font-medium text-background transition-colors hover:opacity-90"
        >
          Add cluster
        </button>
      </div>
      <p className="mt-1 text-sm text-text-muted">
        Kubernetes clusters running the KubeX agent, reporting deployment health back to this org.
      </p>

      <div className="mt-4">
        {isLoading && <p className="text-sm text-text-muted">Loading clusters…</p>}
        {isError && <p className="text-sm text-failed">Failed to load clusters.</p>}
        {!isLoading && !isError && clusters && clusters.length === 0 && (
          <p className="text-sm text-text-muted">No clusters connected yet.</p>
        )}
        {clusters && clusters.length > 0 && (
          <ul className="flex flex-col gap-3">
            {clusters.map((cluster) => (
              <ClusterRow key={cluster.id} cluster={cluster} onRotateToken={onRotateToken} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
