import { Link } from 'react-router-dom'
import { ServiceCard } from './ServiceCard'
import { ServiceCardSkeleton } from './ServiceCardSkeleton'
import type { Service } from '../types/service'

const GRID = 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3'
const SKELETON_COUNT = 6

type ServiceCardGridProps = {
  services: Service[] | undefined
  isLoading: boolean
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
      {services?.map((service) => (
        <Link key={service.id} to={`/app/services/${service.name}`} className="block">
          <ServiceCard service={service} />
        </Link>
      ))}
    </div>
  )
}
