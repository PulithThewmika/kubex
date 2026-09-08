import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChatWindow } from './ChatWindow'
import type { ChatMessage } from '../../types/chat'

describe('ChatWindow', () => {
  it('shows the typing indicator while streaming with no visible content yet', () => {
    const messages: ChatMessage[] = [
      { id: '1', role: 'user', content: 'hi' },
      { id: '2', role: 'assistant', parts: [] },
    ]
    render(<ChatWindow messages={messages} isStreaming={true} />)
    expect(screen.getByText('KubeX is thinking…')).toBeInTheDocument()
  })

  it('hides the typing indicator once text has started streaming in', () => {
    const messages: ChatMessage[] = [
      { id: '1', role: 'user', content: 'hi' },
      { id: '2', role: 'assistant', parts: [{ type: 'text', text: 'Checking' }] },
    ]
    render(<ChatWindow messages={messages} isStreaming={true} />)
    expect(screen.queryByText('KubeX is thinking…')).not.toBeInTheDocument()
    expect(screen.getByText('Checking')).toBeInTheDocument()
  })

  it('does not show the indicator when not streaming', () => {
    const messages: ChatMessage[] = [{ id: '1', role: 'user', content: 'hi' }]
    render(<ChatWindow messages={messages} isStreaming={false} />)
    expect(screen.queryByText('KubeX is thinking…')).not.toBeInTheDocument()
  })
})
