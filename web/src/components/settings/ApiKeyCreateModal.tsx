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
          <p className="font-body text-xs font-semibold uppercase leading-relaxed tracking-wide text-ink-muted">
            Copy this key now — it's shown only once. If you lose it, revoke it and create a new one.
          </p>
          <CodeBlock code={created.token} />
          <button
            type="button"
            onClick={onClose}
            className="w-fit border-2 border-accent bg-accent px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px"
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
          <label className="flex flex-col gap-2 font-body text-xs font-bold uppercase tracking-wide">
            <span className="text-ink">Key name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="CI pipeline"
              autoFocus
              className="border-2 border-paper-line-soft bg-paper px-3 py-2.5 font-body text-sm normal-case tracking-normal text-ink focus:border-accent focus:outline-none"
            />
          </label>
          {createMutation.isError && (
            <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
              {(createMutation.error as Error).message}
            </p>
          )}
          <button
            type="submit"
            disabled={name.trim().length === 0 || createMutation.isPending}
            className="w-fit border-2 border-accent bg-accent px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating…' : 'Create key'}
          </button>
        </form>
      )}
    </Modal>
  )
}
