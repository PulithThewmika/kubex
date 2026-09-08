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
    <li className="flex flex-col gap-3 border-2 border-border-strong bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-body text-sm font-bold text-text">{cluster.name}</span>
          <StatusBadge variant={CLUSTER_STATUS_VARIANT[cluster.status]}>{cluster.status}</StatusBadge>
        </div>
        <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
          ArgoCD: {formatComponentStatus(cluster.argocd_status)} · Prometheus:{' '}
          {formatComponentStatus(cluster.prometheus_status)}
        </p>
        <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
          {cluster.last_heartbeat
            ? `Last heartbeat ${formatDistanceToNow(new Date(cluster.last_heartbeat), { addSuffix: true })}`
            : 'No heartbeat received yet'}
        </p>
      </div>
      <button
        type="button"
        onClick={() => onRotateToken(cluster)}
        className="w-fit border-2 border-text-muted px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
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
        <h2 className="font-body text-xs font-bold uppercase tracking-[0.15em] text-text-muted">Clusters</h2>
        <button
          type="button"
          onClick={onAddCluster}
          className="border-2 border-accent bg-accent px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px"
        >
          Add cluster
        </button>
      </div>
      <p className="mt-1 font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
        Kubernetes clusters running the KubeX agent, reporting deployment health back to this org.
      </p>

      <div className="mt-4">
        {isLoading && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            Loading clusters…
          </p>
        )}
        {isError && (
          <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
            Failed to load clusters.
          </p>
        )}
        {!isLoading && !isError && clusters && clusters.length === 0 && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            No clusters connected yet.
          </p>
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
