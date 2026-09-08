import { Markdown } from './Markdown'
import { ToolCallChip } from './ToolCallChip'
import type { ChatMessage } from '../../types/chat'

type MessageBubbleProps = {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap border-2 border-accent bg-accent/10 px-4 py-2.5 text-sm text-ink">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="flex w-full max-w-full flex-col gap-2">
        {message.parts.map((part, i) =>
          part.type === 'text' ? (
            part.text.length > 0 && <Markdown key={i}>{part.text}</Markdown>
          ) : (
            <ToolCallChip
              key={i}
              tool={part.tool}
              input={part.input}
              result={part.result}
              isError={part.is_error}
            />
          ),
        )}
      </div>
    </div>
  )
}
