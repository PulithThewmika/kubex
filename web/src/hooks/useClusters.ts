import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'
import type { Cluster } from '../types/cluster'

async function fetchClusters(): Promise<Cluster[]> {
  const res = await apiFetch('/api/clusters')
  if (!res.ok) {
    throw new Error(`Failed to fetch clusters: ${res.status}`)
  }
  return res.json()
}

const POLL_INTERVAL_MS = 30_000

export function useClusters() {
  return useQuery({
    queryKey: ['clusters'],
    queryFn: fetchClusters,
    refetchInterval: POLL_INTERVAL_MS,
  })
}
