import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Modal } from './Modal'

function renderModal(onClose = vi.fn()) {
  return render(
    <Modal titleId="t" title="Test modal" onClose={onClose}>
      <button type="button">First</button>
      <button type="button">Last</button>
    </Modal>,
  )
}

describe('Modal', () => {
  it('calls onClose on Escape', () => {
    const onClose = vi.fn()
    renderModal(onClose)

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('traps Tab focus within the dialog, wrapping from the last to the first focusable element', () => {
    // The header's own Close (X) button is part of the focusable set and
    // comes first in DOM order (rendered before the children) — it's the
    // true first element, not the "First" child button.
    renderModal()

    const last = screen.getByRole('button', { name: 'Last' })
    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })

    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }))
  })

  it('wraps Shift+Tab from the first focusable element to the last', () => {
    renderModal()

    const closeButton = screen.getByRole('button', { name: 'Close' })
    closeButton.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })

    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Last' }))
  })

  it('restores focus to the previously focused element on unmount', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()

    const { unmount } = renderModal()
    expect(document.activeElement).not.toBe(trigger)

    unmount()
    expect(document.activeElement).toBe(trigger)

    trigger.remove()
  })
})
