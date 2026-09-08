import { EmptyState } from '../components/EmptyState'
import { ServiceCardGrid } from '../components/ServiceCardGrid'
import { useServices } from '../hooks/useServices'

export function Overview() {
  const { data: services, isLoading, isError } = useServices()

  return (
    <div className="p-6">
      <h1 className="mb-4 font-heading text-xl font-semibold text-text">Overview</h1>
      {isError ? (
        <p className="text-sm text-failed">Failed to load services. Retrying automatically.</p>
      ) : !isLoading && services?.length === 0 ? (
        <EmptyState
          title="No services yet"
          description="Services show up here once a deployment webhook fires. Connect a repository to get started."
          action={{ label: 'Connect a repository', to: '/app/settings?tab=connections' }}
        />
      ) : (
        <ServiceCardGrid services={services} isLoading={isLoading} />
      )}
    </div>
  )
}
