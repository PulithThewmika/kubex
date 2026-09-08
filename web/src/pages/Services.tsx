import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { ServiceCardGrid } from '../components/ServiceCardGrid'
import { useServices } from '../hooks/useServices'
import { useClusters } from '../hooks/useClusters'
import type { Service } from '../types/service'

const SORTS = [
  { id: 'health', label: 'Health' },
  { id: 'frequency', label: 'Deploy frequency' },
  { id: 'recent', label: 'Last deploy' },
] as const

type SortId = (typeof SORTS)[number]['id']

function isSortId(value: string | null): value is SortId {
  return value !== null && SORTS.some((s) => s.id === value)
}

const UNASSIGNED = '__none__'

function sortServices(services: Service[], sort: SortId): Service[] {
  const copy = [...services]
  if (sort === 'health') {
    return copy.sort((a, b) => (b.health?.score ?? -1) - (a.health?.score ?? -1))
  }
  if (sort === 'frequency') {
    return copy.sort((a, b) => b.deploy_count_30d - a.deploy_count_30d)
  }
  return copy.sort((a, b) => {
    const at = a.latest_deploy?.finished_at ? Date.parse(a.latest_deploy.finished_at) : 0
    const bt = b.latest_deploy?.finished_at ? Date.parse(b.latest_deploy.finished_at) : 0
    return bt - at
  })
}

export function Services() {
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const clusterFilter = searchParams.get('cluster') ?? ''
  const sortParam = searchParams.get('sort')
  const sort: SortId = isSortId(sortParam) ? sortParam : 'health'

  const { data: services, isLoading, isError } = useServices()
  const { data: clusters } = useClusters()

  function setParam(key: string, value: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value) next.set(key, value)
        else next.delete(key)
        return next
      },
      { replace: true },
    )
  }

  const visible = useMemo(() => {
    if (!services) return []
    const q = query.trim().toLowerCase()
    const filtered = services.filter((s) => {
      if (q && !s.name.toLowerCase().includes(q)) return false
      if (clusterFilter === UNASSIGNED) return s.cluster_id === null
      if (clusterFilter && s.cluster_id !== clusterFilter) return false
      return true
    })
    return sortServices(filtered, sort)
  }, [services, query, clusterFilter, sort])

  const hasClusterAssignments = useMemo(
    () => (services ?? []).some((s) => s.cluster_id !== null),
    [services],
  )

  return (
    <div className="p-6">
      <PageHeader title="Services" description="Search, filter, and sort every tracked service." />

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-text-muted">
          Search
          <input
            type="search"
            value={query}
            onChange={(e) => setParam('q', e.target.value)}
            placeholder="Service name"
            className="w-52 rounded-md border border-border-strong bg-surface px-2.5 py-1.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
          />
        </label>

        {(hasClusterAssignments || clusterFilter) && (
          <label className="flex flex-col gap-1 text-xs font-medium text-text-muted">
            Cluster
            <select
              value={clusterFilter}
              onChange={(e) => setParam('cluster', e.target.value)}
              className="rounded-md border border-border-strong bg-surface px-2.5 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
            >
              <option value="">All clusters</option>
              {clusters?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
              <option value={UNASSIGNED}>Unassigned</option>
            </select>
          </label>
        )}

        <label className="flex flex-col gap-1 text-xs font-medium text-text-muted">
          Sort by
          <select
            value={sort}
            onChange={(e) => setParam('sort', e.target.value)}
            className="rounded-md border border-border-strong bg-surface px-2.5 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
          >
            {SORTS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isError ? (
        <div className="rounded-xl border border-failed/30 bg-failed/5 p-4 text-sm text-failed">
          Failed to load services. Retrying automatically.
        </div>
      ) : !isLoading && visible.length === 0 ? (
        services && services.length > 0 ? (
          <EmptyState
            title="No matching services"
            description="No service matches the current search and filters."
            action={{
              label: 'Clear filters',
              onClick: () =>
                setSearchParams(
                  (prev) => {
                    const next = new URLSearchParams(prev)
                    next.delete('q')
                    next.delete('cluster')
                    return next
                  },
                  { replace: true },
                ),
            }}
          />
        ) : (
          <EmptyState
            title="No services yet"
            description="Services appear here once a deployment webhook fires."
            action={{ label: 'Connect a repository', to: '/app/settings?tab=connections' }}
          />
        )
      ) : (
        <ServiceCardGrid services={visible} isLoading={isLoading} />
      )}
    </div>
  )
}
