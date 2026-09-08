import { useLocation } from 'react-router-dom'
import { Logo } from './Logo'
import { UserMenu } from './UserMenu'

const TITLES: Array<[RegExp, string]> = [
  [/^\/app\/?$/, 'Overview'],
  [/^\/app\/services\/[^/]+/, 'Service'],
  [/^\/app\/services\/?$/, 'Services'],
  [/^\/app\/alerts/, 'Alerts'],
  [/^\/app\/deployments\//, 'Deployment'],
  [/^\/app\/chat/, 'Chat'],
  [/^\/app\/settings/, 'Settings'],
  [/^\/app\/onboarding/, 'Get started'],
]

function titleFor(pathname: string): string {
  return TITLES.find(([re]) => re.test(pathname))?.[1] ?? 'KubeX'
}

export function TopBar() {
  const { pathname } = useLocation()
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between border-b-2 border-text bg-surface/95 px-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3">
        <Logo withWordmark={false} markClassName="h-6 w-6" />
        <span className="font-body text-xs font-bold uppercase tracking-[0.2em] text-text">{titleFor(pathname)}</span>
      </div>
      <UserMenu />
    </header>
  )
}
