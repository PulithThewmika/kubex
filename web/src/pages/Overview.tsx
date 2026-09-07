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
        <p className="text-sm text-text-muted">
          No services registered yet. Services appear here once a deployment webhook fires.
        </p>
      ) : (
        <ServiceCardGrid services={services} isLoading={isLoading} />
      )}
    </div>
  )
}
