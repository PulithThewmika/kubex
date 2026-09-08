import { NoServicesEmpty } from '../components/NoServicesEmpty'
import { PageHeader } from '../components/PageHeader'
import { ServiceCardGrid } from '../components/ServiceCardGrid'
import { useServices } from '../hooks/useServices'

export function Overview() {
  const { data: services, isLoading, isError } = useServices()
  const count = services?.length ?? 0

  return (
    <div className="p-6">
      <PageHeader
        title="Overview"
        description={
          isLoading || isError
            ? 'Every service KubeX is tracking, with its latest deployment health.'
            : `${count} service${count === 1 ? '' : 's'} tracked.`
        }
      />
      {isError ? (
        <div className="border-2 border-failed bg-failed/5 p-4 font-body text-xs font-bold uppercase tracking-wide text-failed">
          Failed to load services. Retrying automatically.
        </div>
      ) : !isLoading && services?.length === 0 ? (
        <NoServicesEmpty />
      ) : (
        <ServiceCardGrid services={services} isLoading={isLoading} />
      )}
    </div>
  )
}
