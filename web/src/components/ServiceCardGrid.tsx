import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { ServiceCard } from './ServiceCard'
import { ServiceCardSkeleton } from './ServiceCardSkeleton'
import type { Service } from '../types/service'

const GRID = 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3'
const SKELETON_COUNT = 6

type ServiceCardGridProps = {
  services: Service[] | undefined
  isLoading: boolean
}

function AddServiceTile() {
  return (
    <Link
      to="/app/settings?tab=connections"
      aria-label="Add a new service"
      className="group flex h-full min-h-[15rem] flex-col border-2 border-dashed border-paper-line-soft bg-paper-raised p-6 outline-offset-4 transition-all duration-300 hover:-translate-y-1 hover:border-solid hover:border-accent hover:shadow-[6px_6px_0_0_rgba(255,87,34,0.18)]"
    >
      <Plus
        className="h-14 w-14 text-accent transition-transform duration-300 group-hover:rotate-90"
        strokeWidth={2.5}
      />
      <h3 className="mt-3 font-display text-3xl uppercase leading-none text-ink">Add service</h3>
      <p className="mt-3 font-body text-sm leading-relaxed text-ink-muted">
        Connect a repository or cluster to start tracking a new service and scoring its deploys.
      </p>
    </Link>
  )
}

export function ServiceCardGrid({ services, isLoading }: ServiceCardGridProps) {
  if (isLoading) {
    return (
      <div className={GRID}>
        {Array.from({ length: SKELETON_COUNT }, (_, i) => (
          <ServiceCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  return (
    <div className={GRID}>
      {services?.map((service, i) => (
        <Link
          key={service.id}
          to={`/app/services/${service.name}`}
          className="group block outline-offset-4"
        >
          <ServiceCard service={service} index={i} />
        </Link>
      ))}
      <AddServiceTile />
    </div>
  )
}
