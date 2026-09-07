import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '../lib/apiFetch'
import { CodeBlock } from './CodeBlock'
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
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
    },
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="rotate-token-title"
        className="w-full max-w-md rounded-lg border border-border bg-surface p-6"
      >
        <h2 id="rotate-token-title" className="font-heading text-lg font-semibold text-text">
          Rotate token for {cluster.name}
        </h2>

        {!rotated && (
          <div className="mt-4 flex flex-col gap-4">
            <p className="text-sm text-text-muted">
              The agent currently running in this cluster will need to be updated with the new token. Its old token
              keeps working for a 10-minute grace period so you have time to redeploy it.
            </p>
            {mutation.isError && <p className="text-sm text-failed">{(mutation.error as Error).message}</p>}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
                className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90 disabled:opacity-50"
              >
                {mutation.isPending ? 'Rotating…' : 'Rotate token'}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="w-fit rounded-md border border-border px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-background"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {rotated && (
          <div className="mt-4 flex flex-col gap-4">
            <p className="text-sm text-text-muted">
              New token — shown only once. Update the agent's <code>CLUSTER_TOKEN</code> secret with this value
              before the old one's grace period expires.
            </p>
            <CodeBlock code={rotated.token} />
            <button
              type="button"
              onClick={onClose}
              className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
