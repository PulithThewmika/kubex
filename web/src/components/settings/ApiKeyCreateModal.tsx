import { useState } from 'react'
import { useCreateApiKey, type CreatedApiKey } from '../../hooks/useApiKeys'
import { CodeBlock } from '../CodeBlock'
import { Modal } from '../Modal'

type ApiKeyCreateModalProps = {
  onClose: () => void
}

export function ApiKeyCreateModal({ onClose }: ApiKeyCreateModalProps) {
  const [name, setName] = useState('')
  const [created, setCreated] = useState<CreatedApiKey | null>(null)
  const createMutation = useCreateApiKey()

  function handleClose() {
    // The token is shown exactly once (below) — a close mid-request could let
    // the mutation resolve after unmount and lose it, leaving a key row with
    // no way to recover the token.
    if (createMutation.isPending) return
    onClose()
  }

  return (
    <Modal titleId="create-api-key-title" title="Create API key" onClose={handleClose}>
      {created ? (
        <div className="mt-4 flex flex-col gap-4">
          <p className="text-sm text-text-muted">
            Copy this key now — it's shown only once. If you lose it, revoke it and create a new one.
          </p>
          <CodeBlock code={created.token} />
          <button
            type="button"
            onClick={onClose}
            className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90"
          >
            Done
          </button>
        </div>
      ) : (
        <form
          className="mt-4 flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (name.trim().length === 0 || createMutation.isPending) return
            createMutation.mutate(name.trim(), { onSuccess: setCreated })
          }}
        >
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium text-text">Key name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="CI pipeline"
              autoFocus
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
            />
          </label>
          {createMutation.isError && (
            <p className="text-sm text-failed">{(createMutation.error as Error).message}</p>
          )}
          <button
            type="submit"
            disabled={name.trim().length === 0 || createMutation.isPending}
            className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating…' : 'Create key'}
          </button>
        </form>
      )}
    </Modal>
  )
}
