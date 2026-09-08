import { useCallback, type KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { GeneralTab } from '../components/settings/GeneralTab'
import { ConnectionsTab } from '../components/settings/ConnectionsTab'
import { ApiKeysTab } from '../components/settings/ApiKeysTab'
import { TeamTab } from '../components/settings/TeamTab'

const TABS = [
  { id: 'general', label: 'General' },
  { id: 'connections', label: 'Connections' },
  { id: 'api-keys', label: 'API Keys' },
  { id: 'team', label: 'Team' },
] as const

type TabId = (typeof TABS)[number]['id']

function isTabId(value: string | null): value is TabId {
  return value !== null && TABS.some((tab) => tab.id === value)
}

export function Settings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const installationId = searchParams.get('installation_id')
  const tabParam = searchParams.get('tab')
  // The GitHub App install redirect lands on /app/settings?installation_id=…
  // with no ?tab= — send it straight to Connections where that state is handled.
  const activeTab: TabId = isTabId(tabParam) ? tabParam : installationId ? 'connections' : 'general'

  const selectTab = useCallback(
    (id: TabId) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('tab', id)
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  function handleTabKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    event.preventDefault()
    const currentIndex = TABS.findIndex((tab) => tab.id === activeTab)
    const delta = event.key === 'ArrowRight' ? 1 : -1
    const next = TABS[(currentIndex + delta + TABS.length) % TABS.length]
    selectTab(next.id)
    document.getElementById(`settings-tab-${next.id}`)?.focus()
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <h1 className="font-heading text-3xl font-bold uppercase tracking-tight text-ink sm:text-4xl">Settings</h1>

      <div
        role="tablist"
        aria-label="Settings sections"
        onKeyDown={handleTabKeyDown}
        className="mt-8 flex gap-1 overflow-x-auto border-b-2 border-paper-line"
      >
        {TABS.map((tab) => {
          const selected = tab.id === activeTab
          return (
            <button
              key={tab.id}
              id={`settings-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`settings-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => selectTab(tab.id)}
              className={`-mb-0.5 shrink-0 border-b-2 px-4 py-3 font-body text-xs font-bold uppercase tracking-wide transition-colors ${
                selected
                  ? 'border-accent text-accent'
                  : 'border-transparent text-ink-muted hover:text-ink'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      <div
        id={`settings-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`settings-tab-${activeTab}`}
        className="mt-10"
      >
        {activeTab === 'general' && <GeneralTab />}
        {activeTab === 'connections' && <ConnectionsTab installationId={installationId} />}
        {activeTab === 'api-keys' && <ApiKeysTab />}
        {activeTab === 'team' && <TeamTab />}
      </div>
    </div>
  )
}
