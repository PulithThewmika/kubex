import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { useApiKeys, useRevokeApiKey, type ApiKey } from '../../hooks/useApiKeys'
import { Modal } from '../Modal'
import { ApiKeyCreateModal } from './ApiKeyCreateModal'

function KeyRow({ apiKey, onRevoke }: { apiKey: ApiKey; onRevoke: (key: ApiKey) => void }) {
  return (
    <li className="flex flex-col gap-2 border-2 border-border-strong bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <span className="font-body text-sm font-bold text-text">{apiKey.name}</span>
        <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
          Created {formatDistanceToNow(new Date(apiKey.created_at), { addSuffix: true })}
          {' · '}
          {apiKey.last_used
            ? `last used ${formatDistanceToNow(new Date(apiKey.last_used), { addSuffix: true })}`
            : 'never used'}
        </p>
      </div>
      <button
        type="button"
        onClick={() => onRevoke(apiKey)}
        className="w-fit border-2 border-text-muted px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
      >
        Revoke
      </button>
    </li>
  )
}

function RevokeDialog({ apiKey, onClose }: { apiKey: ApiKey; onClose: () => void }) {
  const revokeMutation = useRevokeApiKey()

  // Don't let Escape / overlay / close-button dismiss while the DELETE is in
  // flight — the mutation would resolve against an unmounted component.
  function handleClose() {
    if (revokeMutation.isPending) return
    onClose()
  }

  return (
    <Modal titleId="revoke-api-key-title" title="Revoke API key" onClose={handleClose}>
      <div className="mt-4 flex flex-col gap-4">
        <p className="font-body text-xs font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
          Revoke <span className="font-bold text-text">{apiKey.name}</span>? Any client using it will
          immediately lose access. This can't be undone.
        </p>
        {revokeMutation.isError && (
          <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
            {(revokeMutation.error as Error).message}
          </p>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={revokeMutation.isPending}
            onClick={() => revokeMutation.mutate(apiKey.id, { onSuccess: onClose })}
            className="w-fit border-2 border-failed bg-failed px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-white transition-colors hover:brightness-110 active:translate-y-px disabled:opacity-50"
          >
            {revokeMutation.isPending ? 'Revoking…' : 'Revoke key'}
          </button>
          <button
            type="button"
            disabled={revokeMutation.isPending}
            onClick={onClose}
            className="w-fit border-2 border-text-muted px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  )
}

export function ApiKeysTab() {
  const { data: keys, isLoading, isError } = useApiKeys()
  const [showCreate, setShowCreate] = useState(false)
  const [revoking, setRevoking] = useState<ApiKey | null>(null)

  return (
    <section>
      <div className="flex items-center justify-between">
        <h2 className="font-body text-xs font-bold uppercase tracking-[0.15em] text-text-muted">API keys</h2>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="border-2 border-accent bg-accent px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px"
        >
          Create API key
        </button>
      </div>
      <p className="mt-1 font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
        Keys authenticate scripts and integrations to the KubeX API on behalf of this org.
      </p>

      <div className="mt-4">
        {isLoading && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            Loading API keys…
          </p>
        )}
        {isError && (
          <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
            Failed to load API keys.
          </p>
        )}
        {!isLoading && !isError && keys && keys.length === 0 && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            No API keys yet.
          </p>
        )}
        {keys && keys.length > 0 && (
          <ul className="flex flex-col gap-3">
            {keys.map((apiKey) => (
              <KeyRow key={apiKey.id} apiKey={apiKey} onRevoke={setRevoking} />
            ))}
          </ul>
        )}
      </div>

      {showCreate && <ApiKeyCreateModal onClose={() => setShowCreate(false)} />}
      {revoking && <RevokeDialog apiKey={revoking} onClose={() => setRevoking(null)} />}
    </section>
  )
}
