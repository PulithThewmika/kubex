import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'
import type { Installation } from '../types/installation'

async function fetchInstallations(): Promise<Installation[]> {
  const res = await apiFetch('/api/settings/installations')
  if (!res.ok) {
    throw new Error(`Failed to fetch installations: ${res.status}`)
  }
  return res.json()
}

const POLL_WHILE_EMPTY_MS = 2000
const MAX_POLL_ATTEMPTS = 5

type UseInstallationsOptions = {
  // Poll briefly right after the GitHub App install redirect (the numeric
  // github_installation_id from ?installation_id=): the `installation`
  // webhook that creates the row can lag the browser redirect back to this
  // page. Matched by id (not list length) so it also works when the org
  // already has other installations.
  pollForInstallationId?: string | null
}

export function useInstallations(options: UseInstallationsOptions = {}) {
  const targetId = options.pollForInstallationId
  return useQuery({
    queryKey: ['installations'],
    queryFn: fetchInstallations,
    refetchInterval: (query) => {
      if (!targetId) return false
      const data = query.state.data
      const found = data?.some((installation) => String(installation.github_installation_id) === targetId)
      if (found) return false
      // ponytail: attempt budget is on the shared ['installations'] cache entry, so
      // a second install within the same gcTime window inherits the prior count
      // instead of a fresh one. Scope per-redirect if this proves to matter.
      if (query.state.dataUpdateCount + query.state.errorUpdateCount >= MAX_POLL_ATTEMPTS) return false
      return POLL_WHILE_EMPTY_MS
    },
  })
}
