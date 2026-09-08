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
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {awaitingFirstToken && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}

function hasVisibleContent(part: MessagePart): boolean {
  return part.type !== 'text' || part.text.length > 0
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 border-2 border-paper-line-soft bg-paper-raised px-3.5 py-2.5">
        <span
          className="text-shine font-body text-xs font-bold uppercase tracking-wide"
          style={{ '--shine-base': '#8C877A' } as CSSProperties}
        >
          KubeX is thinking…
        </span>
      </div>
    </div>
  )
}
