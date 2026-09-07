import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useReveal } from './useReveal'

type ObserverCallback = (entries: Pick<IntersectionObserverEntry, 'isIntersecting'>[]) => void

function stubIntersectionObserver() {
  let callback: ObserverCallback = () => {}
  const observe = vi.fn()
  const disconnect = vi.fn()
  class FakeIntersectionObserver {
    constructor(cb: ObserverCallback) {
      callback = cb
    }
    observe = observe
    unobserve = vi.fn()
    disconnect = disconnect
  }
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)
  return {
    fire: (isIntersecting: boolean) => callback([{ isIntersecting }]),
    observe,
    disconnect,
  }
}

function stubReducedMotion(matches: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches, media: query }) as MediaQueryList)
}

function Probe() {
  const { ref, visible } = useReveal<HTMLDivElement>()
  return (
    <div ref={ref} data-testid="probe">
      {visible ? 'visible' : 'hidden'}
    </div>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useReveal', () => {
  it('starts hidden and becomes visible once the element intersects', () => {
    stubReducedMotion(false)
    const io = stubIntersectionObserver()
    render(<Probe />)

    expect(screen.getByTestId('probe')).toHaveTextContent('hidden')
    act(() => io.fire(true))
    expect(screen.getByTestId('probe')).toHaveTextContent('visible')
    expect(io.disconnect).toHaveBeenCalled()
  })

  it('renders visible immediately when prefers-reduced-motion is set', () => {
    stubReducedMotion(true)
    const io = stubIntersectionObserver()
    render(<Probe />)

    expect(screen.getByTestId('probe')).toHaveTextContent('visible')
    expect(io.observe).not.toHaveBeenCalled()
  })

  it('renders visible immediately when IntersectionObserver is unavailable', () => {
    stubReducedMotion(false)
    vi.stubGlobal('IntersectionObserver', undefined)
    render(<Probe />)

    expect(screen.getByTestId('probe')).toHaveTextContent('visible')
  })

  it('renders visible immediately when matchMedia is unavailable', () => {
    vi.stubGlobal('matchMedia', undefined)
    stubIntersectionObserver()
    render(<Probe />)

    expect(screen.getByTestId('probe')).toHaveTextContent('visible')
  })
})
