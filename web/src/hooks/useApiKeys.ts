import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'

export type ApiKey = {
  id: string
  name: string
  created_at: string
  last_used: string | null
}

// Only ever returned by the create call — the raw token is shown once and
// never stored server-side in a readable form.
export type CreatedApiKey = ApiKey & { token: string }

const API_KEYS_QUERY_KEY = ['api-keys']

async function fetchApiKeys(): Promise<ApiKey[]> {
  const res = await apiFetch('/api/settings/api-keys')
  if (!res.ok) throw new Error(`Failed to fetch API keys: ${res.status}`)
  return res.json()
}

export function useApiKeys() {
  return useQuery({ queryKey: API_KEYS_QUERY_KEY, queryFn: fetchApiKeys })
}

export function useCreateApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (name: string): Promise<CreatedApiKey> => {
      const res = await apiFetch('/api/settings/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail ?? `Failed to create API key: ${res.status}`)
      }
      return res.json()
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY }),
  })
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      const res = await apiFetch(`/api/settings/api-keys/${id}`, { method: 'DELETE' })
      // 404 means it's already gone — the list is about to refetch anyway.
      if (!res.ok && res.status !== 404) {
        throw new Error(`Failed to revoke API key: ${res.status}`)
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY }),
  })
}
