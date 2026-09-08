import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Chat } from './Chat'

const renderChat = () => render(<Chat />, { wrapper: MemoryRouter })

function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame))
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Chat page', () => {
  it('disables the input while streaming and re-enables it once the response finishes', async () => {
    let resolveFetch!: (res: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise<Response>((resolve) => (resolveFetch = resolve))),
    )

    renderChat()
    const input = screen.getByPlaceholderText(/ask about/i)
    fireEvent.change(input, { target: { value: 'What deployed today?' } })
    fireEvent.submit(input.closest('form')!)

    await waitFor(() => expect(input).toBeDisabled())

    resolveFetch(sseResponse(['event: text\ndata: {"text":"Nothing today."}\n\n']))

    await waitFor(() => expect(input).not.toBeDisabled())
    expect(screen.getByText('Nothing today.')).toBeInTheDocument()
  })

  it('shows an error banner when the chat service is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 503 })))

    renderChat()
    const input = screen.getByPlaceholderText(/ask about/i)
    fireEvent.change(input, { target: { value: 'hello' } })
    fireEvent.submit(input.closest('form')!)

    expect(await screen.findByText('Unable to reach the chat service.')).toBeInTheDocument()
  })

  it('populates the input when a suggested prompt chip is clicked, without sending it', () => {
    vi.stubGlobal('fetch', vi.fn())
    renderChat()

    fireEvent.click(screen.getByText('What deployed today?'))

    expect(screen.getByPlaceholderText(/ask about/i)).toHaveValue('What deployed today?')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('replaces the intro screen with the conversation as soon as a message is sent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise<Response>(() => {})))
    renderChat()

    expect(screen.getByText('Ask about your deployments')).toBeInTheDocument()

    const input = screen.getByPlaceholderText(/ask about/i)
    fireEvent.change(input, { target: { value: 'hello there' } })
    fireEvent.submit(input.closest('form')!)

    await waitFor(() =>
      expect(screen.queryByText('Ask about your deployments')).not.toBeInTheDocument(),
    )
    expect(screen.getByText('hello there')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Why is $service degraded?' })).not.toBeInTheDocument()
  })
})
