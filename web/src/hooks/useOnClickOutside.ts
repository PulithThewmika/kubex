import { useEffect, useRef } from 'react'

export function useOnClickOutside(ref: React.RefObject<HTMLElement>, handler: () => void) {
  // Stashed in a ref so the mousedown listener isn't torn down and
  // reinstalled on every render just because callers pass a fresh inline
  // handler each time (as UserMenu does).
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    function listener(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) handlerRef.current()
    }
    document.addEventListener('mousedown', listener)
    return () => document.removeEventListener('mousedown', listener)
  }, [ref])
}
