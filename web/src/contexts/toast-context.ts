import { createContext } from 'react'
import type { ToastType } from '../components/Toast'

export type ToastOptions = { type?: ToastType; duration?: number }

export type ToastContextValue = {
  toast: (message: string, options?: ToastOptions) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)
