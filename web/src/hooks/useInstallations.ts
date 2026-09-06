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
  // Poll briefly right after the GitHub App install redirect: the
  // `installation` webhook that creates the row can lag the browser
  // redirect back to this page.
  pollWhileEmpty?: boolean
}

export function useInstallations(options: UseInstallationsOptions = {}) {
  return useQuery({
    queryKey: ['installations'],
    queryFn: fetchInstallations,
    refetchInterval: (query) => {
      if (!options.pollWhileEmpty) return false
      if (query.state.data && query.state.data.length > 0) return false
      if (query.state.dataUpdateCount >= MAX_POLL_ATTEMPTS) return false
      return POLL_WHILE_EMPTY_MS
    },
  })
}
