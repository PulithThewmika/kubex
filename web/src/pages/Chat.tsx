import { useState } from 'react'
import { ChatWindow } from '../components/chat/ChatWindow'
import { useChatSession } from '../hooks/useChatSession'

const SUGGESTED_PROMPTS = [
  'What deployed today?',
  'Why is $service degraded?',
  'Compare the last two deploys of $service',
]

export function Chat() {
  const { messages, isStreaming, error, sendMessage } = useChatSession()
  const [input, setInput] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    setInput('')
    void sendMessage(trimmed)
  }

  return (
    <div className="flex h-full flex-col bg-paper">
      {error && (
        <div
          role="alert"
          className="border-b-2 border-failed bg-failed/10 px-4 py-2 text-center font-body text-xs font-bold uppercase tracking-wide text-failed"
        >
          {error}
        </div>
      )}

      {messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-5 px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center border-2 border-paper-line bg-paper-raised text-accent">
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden="true">
              <path
                d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9A1.5 1.5 0 0 1 18.5 16H9l-4 4v-4H5.5A1.5 1.5 0 0 1 4 14.5v-9Z"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <p className="font-heading text-2xl font-bold uppercase tracking-tight text-ink">
              Ask about your deployments
            </p>
            <p className="mt-1.5 max-w-sm font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Grounded in your real correlation, health, and metrics history.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setInput(prompt)}
                className="border-2 border-paper-line-soft px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-ink-muted transition-colors hover:border-accent hover:text-accent"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <ChatWindow messages={messages} isStreaming={isStreaming} />
      )}

      <div className="border-t-2 border-paper-line bg-paper">
        <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl gap-2 p-4">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder="Ask about a deployment, service, or incident…"
            className="flex-1 border-2 border-paper-line-soft bg-paper-raised px-4 py-3 font-body text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="flex items-center gap-1.5 border-2 border-accent bg-accent px-5 py-3 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px disabled:border-paper-line-soft disabled:bg-paper-line-soft disabled:opacity-50"
          >
            Send
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  )
}
