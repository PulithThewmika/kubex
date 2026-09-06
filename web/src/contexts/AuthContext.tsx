import { createContext, useContext, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { Me } from '../types/auth'

const ME_QUERY_KEY = ['auth', 'me']

async function fetchMe(): Promise<Me | null> {
  const res = await fetch('/auth/me', { credentials: 'include' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`Failed to fetch current user: ${res.status}`)
  return res.json()
}

type AuthContextValue = {
  user: Me | null
  isAuthenticated: boolean
  isLoading: boolean
  refetch: () => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const { data, isLoading, refetch } = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  })

  async function logout() {
    await fetch('/auth/logout', { method: 'POST', credentials: 'include' })
    queryClient.setQueryData(ME_QUERY_KEY, null)
  }

  const value: AuthContextValue = {
    user: data ?? null,
    isAuthenticated: !!data,
    isLoading,
    refetch: () => void refetch(),
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
