import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'

export type Member = {
  user_id: string
  login: string
  avatar_url: string | null
  role: string
  joined_at: string
}

async function fetchMembers(): Promise<Member[]> {
  const res = await apiFetch('/api/settings/members')
  if (!res.ok) throw new Error(`Failed to fetch members: ${res.status}`)
  return res.json()
}

export function useMembers() {
  return useQuery({ queryKey: ['members'], queryFn: fetchMembers })
}
