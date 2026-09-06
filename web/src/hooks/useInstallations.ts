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

export function useInstallations() {
  return useQuery({
    queryKey: ['installations'],
    queryFn: fetchInstallations,
  })
}
