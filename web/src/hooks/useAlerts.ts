import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'
import type { Alert } from '../types/alert'

export const ALERTS_QUERY_KEY = ['alerts']

async function fetchAlerts(): Promise<Alert[]> {
  const res = await apiFetch('/api/alerts')
  if (!res.ok) {
    throw new Error(`Failed to fetch alerts: ${res.status}`)
  }
  return res.json()
}

const POLL_INTERVAL_MS = 30_000

// Fetches every alert (active + resolved) in one request and lets callers
// split by resolved_at client-side — the list is small and the sidebar badge
// plus the Alerts page both need the full set.
export function useAlerts() {
  return useQuery({
    queryKey: ALERTS_QUERY_KEY,
    queryFn: fetchAlerts,
    refetchInterval: POLL_INTERVAL_MS,
  })
}
