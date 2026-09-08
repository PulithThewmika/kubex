import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'
import type { DeploymentDetail } from '../types/deploymentDetail'

class FetchDeploymentError extends Error {
  status: number

  constructor(status: number) {
    super(`Failed to fetch deployment: ${status}`)
    this.status = status
  }
}

async function fetchDeployment(id: number): Promise<DeploymentDetail> {
  const res = await apiFetch(`/api/deployments/${id}`)
  if (!res.ok) {
    throw new FetchDeploymentError(res.status)
  }
  return res.json()
}

export function useDeployment(id: number) {
  return useQuery({
    queryKey: ['deployment', id],
    queryFn: () => fetchDeployment(id),
    enabled: Number.isFinite(id),
    retry: (failureCount, error) => {
      if (error instanceof FetchDeploymentError && error.status === 404) return false
      return failureCount < 2
    },
  })
}
