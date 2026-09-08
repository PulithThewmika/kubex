export function ServiceCardSkeleton() {
  return (
    <div className="flex flex-col gap-3 border-2 border-border-strong bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-2">
          <div className="h-4 w-24 animate-pulse bg-border" />
          <div className="h-4 w-16 animate-pulse bg-border" />
        </div>
        <div className="h-12 w-12 animate-pulse rounded-full bg-border" />
      </div>
      <div className="h-3 w-40 animate-pulse bg-border" />
    </div>
  )
}
