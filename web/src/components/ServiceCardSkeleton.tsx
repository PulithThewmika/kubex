export function ServiceCardSkeleton() {
  return (
    <div className="flex flex-col gap-3 border-2 border-paper-line-soft bg-paper-raised p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-2">
          <div className="h-4 w-24 animate-pulse bg-paper-line-soft" />
          <div className="h-4 w-16 animate-pulse bg-paper-line-soft" />
        </div>
        <div className="h-12 w-12 animate-pulse rounded-full bg-paper-line-soft" />
      </div>
      <div className="h-3 w-40 animate-pulse bg-paper-line-soft" />
    </div>
  )
}
