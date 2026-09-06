import { useQuery } from '@tanstack/react-query'

export type Membership = {
  org_id: string
  org_name: string
  org_slug: string
}

async function fetchMemberships(): Promise<Membership[]> {
  const res = await fetch('/auth/memberships', { credentials: 'include' })
  if (!res.ok) throw new Error(`Failed to fetch memberships: ${res.status}`)
  return res.json()
}

export function useMemberships(enabled: boolean) {
  return useQuery({
    queryKey: ['auth', 'memberships'],
    queryFn: fetchMemberships,
    enabled,
  })
}
