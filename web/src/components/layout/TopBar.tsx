import { UserMenu } from './UserMenu'

export function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-4">
      <span className="font-heading text-lg font-semibold tracking-wide text-text">
        KubeX
      </span>
      <UserMenu />
    </header>
  )
}
