import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from './ToastContext'
import { useToast } from '../hooks/useToast'

function Trigger() {
  const { toast } = useToast()
  return (
    <>
      <button onClick={() => toast('Saved', { type: 'success' })}>ok</button>
      <button onClick={() => toast('Boom', { type: 'error', duration: 0 })}>err</button>
    </>
  )
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>,
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('ToastProvider / useToast', () => {
  it('shows a toast and auto-dismisses it after the default duration', () => {
    vi.useFakeTimers()
    renderWithProvider()

    act(() => {
      screen.getByText('ok').click()
    })
    expect(screen.getByText('Saved')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(screen.queryByText('Saved')).not.toBeInTheDocument()
  })

  it('keeps a toast with duration 0 until dismissed', () => {
    vi.useFakeTimers()
    renderWithProvider()

    act(() => {
      screen.getByText('err').click()
    })
    const region = screen.getByText('Boom')
    expect(region).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(10_000)
    })
    expect(screen.getByText('Boom')).toBeInTheDocument()

    act(() => {
      screen.getByRole('button', { name: /dismiss notification/i }).click()
    })
    expect(screen.queryByText('Boom')).not.toBeInTheDocument()
  })

  it('stacks multiple toasts', () => {
    renderWithProvider()
    act(() => {
      screen.getByText('ok').click()
      screen.getByText('err').click()
    })
    expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(screen.getByText('Boom')).toBeInTheDocument()
  })

  it('throws if useToast is used outside a provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Trigger />)).toThrow(/ToastProvider/)
    spy.mockRestore()
  })
})
