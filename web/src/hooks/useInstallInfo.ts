import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'

export type InstallInfo = {
  ingest_public_url: string
  agent_namespace: string
  chart_repo_url: string
  chart_path: string
}

async function fetchInstallInfo(): Promise<InstallInfo> {
  const res = await apiFetch('/api/install-info')
  if (!res.ok) {
    throw new Error(`Failed to fetch install info: ${res.status}`)
  }
  return res.json()
}

// Static across the whole session (server config, not per-cluster data) —
// no polling, just cache it once.
export function useInstallInfo() {
  return useQuery({
    queryKey: ['install-info'],
    queryFn: fetchInstallInfo,
    staleTime: Infinity,
  })
}
