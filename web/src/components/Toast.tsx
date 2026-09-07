export type ToastType = 'success' | 'error' | 'info'

export type ToastRecord = {
  id: string
  type: ToastType
  message: string
}

const STYLES: Record<ToastType, { border: string; icon: string; iconPath: JSX.Element }> = {
  success: {
    border: 'border-healthy/40',
    icon: 'text-healthy',
    iconPath: <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />,
  },
  error: {
    border: 'border-failed/40',
    icon: 'text-failed',
    iconPath: <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />,
  },
  info: {
    border: 'border-border',
    icon: 'text-text-muted',
    iconPath: (
      <>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
        <path d="M12 11v5M12 8h.01" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      </>
    ),
  },
}

type ToastProps = {
  toast: ToastRecord
  onDismiss: (id: string) => void
}

export function Toast({ toast, onDismiss }: ToastProps) {
  const style = STYLES[toast.type]
  return (
    <div
      role={toast.type === 'error' ? 'alert' : 'status'}
      className={`flex items-start gap-2.5 rounded-lg border bg-surface px-3.5 py-2.5 text-sm text-text shadow-lg ${style.border}`}
    >
      <svg viewBox="0 0 24 24" fill="none" className={`mt-0.5 h-4 w-4 shrink-0 ${style.icon}`} aria-hidden="true">
        {style.iconPath}
      </svg>
      <span className="flex-1">{toast.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="-mr-1 -mt-0.5 shrink-0 rounded p-0.5 text-text-muted transition-colors hover:text-text"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  )
}
