import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { MessageBubble } from './MessageBubble'
import type { ChatMessage, MessagePart } from '../../types/chat'

type ChatWindowProps = {
  messages: ChatMessage[]
  isStreaming?: boolean
}

export function ChatWindow({ messages, isStreaming = false }: ChatWindowProps) {
  const lastMessage = messages[messages.length - 1]
  const awaitingFirstToken =
    isStreaming && lastMessage?.role === 'assistant' && !lastMessage.parts.some(hasVisibleContent)

  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {awaitingFirstToken && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function hasVisibleContent(part: MessagePart): boolean {
  return part.type !== 'text' || part.text.length > 0
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <span
        className="text-shine font-body text-xs font-bold uppercase tracking-wide"
        style={{ '--shine-base': '#8C877A' } as CSSProperties}
      >
        KubeX is thinking…
      </span>
    </div>
  )
}
