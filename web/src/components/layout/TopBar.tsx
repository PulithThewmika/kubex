import { useLocation } from 'react-router-dom'
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
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface/80 px-4 backdrop-blur sm:px-6">
      <span className="font-heading text-sm font-semibold tracking-tight text-text">{titleFor(pathname)}</span>
      <UserMenu />
    </header>
  )
}
