export function ServiceCardSkeleton() {
  return (
    <div className="flex h-full flex-col overflow-hidden border-2 border-paper-line-soft bg-paper-raised">
      <div className="flex items-center justify-between border-b-2 border-paper-line-soft bg-paper p-4">
        <div className="h-8 w-10 animate-pulse bg-paper-line-soft" />
        <div className="h-11 w-11 animate-pulse rounded-full bg-paper-line-soft" />
      </div>
      <div className="flex flex-col gap-3 p-4">
        <div className="h-3 w-24 animate-pulse bg-paper-line-soft" />
        <div className="h-5 w-32 animate-pulse bg-paper-line-soft" />
        <div className="h-3 w-40 animate-pulse bg-paper-line-soft" />
        <div className="h-4 w-full animate-pulse bg-paper-line-soft" />
      </div>
    </div>
  )
}
