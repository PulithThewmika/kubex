import { UserMenu } from './UserMenu'

export function TopBar() {
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-end border-b-2 border-background bg-text px-4 text-background sm:px-6">
      <UserMenu />
    </header>
  )
}
