// Shared "start something" actions — surfaced both in the header ＋ menu and
// the ⌘K command palette.
export type HeaderAction = { label: string; to: string }

export const QUICK_ADD_ACTIONS: HeaderAction[] = [
  { label: 'Connect a repository', to: '/app/settings?tab=connections' },
  { label: 'Add a cluster', to: '/app/settings?tab=connections' },
  { label: 'Create an API key', to: '/app/settings?tab=api-keys' },
  { label: 'Invite a teammate', to: '/app/settings?tab=team' },
]

export const NAV_PAGES: HeaderAction[] = [
  { label: 'Overview', to: '/app' },
  { label: 'Services', to: '/app/services' },
  { label: 'Alerts', to: '/app/alerts' },
  { label: 'Chat', to: '/app/chat' },
  { label: 'Settings', to: '/app/settings' },
]
