import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '../lib/apiFetch'
import { CLUSTERS_QUERY_KEY } from '../hooks/useClusters'
import { CodeBlock } from './CodeBlock'
import { Modal } from './Modal'
import type { Cluster, ClusterRotateTokenResponse } from '../types/cluster'

async function rotateToken(clusterId: string): Promise<ClusterRotateTokenResponse> {
  const res = await apiFetch(`/api/clusters/${clusterId}/rotate-token`, { method: 'POST' })
  if (!res.ok) {
    throw new Error(`Failed to rotate token: ${res.status}`)
  }
  return res.json()
}

type RotateTokenDialogProps = {
  cluster: Cluster
  onClose: () => void
}

export function RotateTokenDialog({ cluster, onClose }: RotateTokenDialogProps) {
  const [rotated, setRotated] = useState<ClusterRotateTokenResponse | null>(null)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => rotateToken(cluster.id),
    onSuccess: (data) => {
      setRotated(data)
      queryClient.invalidateQueries({ queryKey: CLUSTERS_QUERY_KEY })
    },
  })

  // Same rationale as AddClusterModal's handleClose guard: the rotated
  // token is shown exactly once, so closing mid-rotation could let the
  // request resolve after unmount and lose it (CodeRabbit, PR #804).
  function handleClose() {
    if (mutation.isPending) return
    onClose()
  }

  return (
    <Modal titleId="rotate-token-title" title={`Rotate token for ${cluster.name}`} onClose={handleClose} widthClassName="max-w-md">
      {!rotated && (
        <div className="mt-4 flex flex-col gap-4">
          <p className="font-body text-xs font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
            The agent currently running in this cluster will need to be updated with the new token. Its old token
            keeps working for a 10-minute grace period so you have time to redeploy it.
          </p>
          {mutation.isError && (
            <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
              {(mutation.error as Error).message}
            </p>
          )}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="w-fit border-2 border-accent bg-accent px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px disabled:opacity-50"
            >
              {mutation.isPending ? 'Rotating…' : 'Rotate token'}
            </button>
            <button
              type="button"
              onClick={handleClose}
              disabled={mutation.isPending}
              className="w-fit border-2 border-text-muted px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {rotated && (
        <div className="mt-4 flex flex-col gap-4">
          <p className="font-body text-xs font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
            New token — shown only once. Update the agent's <code>CLUSTER_TOKEN</code> secret with this value
            before the old one's grace period expires.
          </p>
          <CodeBlock code={rotated.token} />
          <button
            type="button"
            onClick={onClose}
            className="w-fit border-2 border-accent bg-accent px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px"
          >
            Done
          </button>
        </div>
      )}
    </Modal>
  )
}
