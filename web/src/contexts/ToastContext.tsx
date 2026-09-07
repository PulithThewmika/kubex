import { useCallback, useRef, useState, type ReactNode } from 'react'
import { Toast, type ToastRecord } from '../components/Toast'
import { ToastContext, type ToastOptions } from './toast-context'

const DEFAULT_DURATION_MS = 4000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([])
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const toast = useCallback(
    (message: string, options?: ToastOptions) => {
      const id = crypto.randomUUID()
      setToasts((prev) => [...prev, { id, type: options?.type ?? 'info', message }])
      const duration = options?.duration ?? DEFAULT_DURATION_MS
      if (duration > 0) {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), duration),
        )
      }
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-xs flex-col gap-2"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <Toast toast={t} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
