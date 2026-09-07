import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'

async function completeOnboarding(): Promise<void> {
  const res = await apiFetch('/api/settings/onboarding/complete', { method: 'POST' })
  if (!res.ok) {
    throw new Error(`Failed to save onboarding progress: ${res.status}`)
  }
}

// Sets the org's onboarding_completed flag so the wizard stops auto-showing
// (OnboardingGate). Invalidates ['auth','me'] so the freshly-set flag is
// reflected without a reload.
export function useCompleteOnboarding() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: completeOnboarding,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth', 'me'] }),
  })
}
