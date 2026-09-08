import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AddClusterModal } from '../components/AddClusterModal'
import { ConnectReposStep } from '../components/onboarding/ConnectReposStep'
import { DeployMethodStep, type DeployMethod } from '../components/onboarding/DeployMethodStep'
import { MetricsStep, type MetricsMethod } from '../components/onboarding/MetricsStep'
import { NotificationsStep } from '../components/onboarding/NotificationsStep'
import { Stepper } from '../components/onboarding/Stepper'
import { SummaryStep } from '../components/onboarding/SummaryStep'
import { useClusters } from '../hooks/useClusters'
import { useCompleteOnboarding } from '../hooks/useCompleteOnboarding'
import { useInstallInfo } from '../hooks/useInstallInfo'
import { useInstallations } from '../hooks/useInstallations'

const STEP_LABELS = ['Repositories', 'Deployments', 'Metrics', 'Notifications', 'Done']

export function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [deployMethod, setDeployMethod] = useState<DeployMethod | null>(null)
  const [metricsMethod, setMetricsMethod] = useState<MetricsMethod | null>(null)
  const [webhookApiKey, setWebhookApiKey] = useState<string | null>(null)
  const [showAddCluster, setShowAddCluster] = useState(false)

  const { data: installations } = useInstallations()
  const { data: clusters } = useClusters()
  const installInfoQuery = useInstallInfo()
  const complete = useCompleteOnboarding()

  const isLast = step === STEP_LABELS.length - 1
  const finishError = complete.isError ? (complete.error as Error).message : null

  function finish() {
    complete.mutate(undefined, { onSuccess: () => navigate('/app', { replace: true }) })
  }

  function next() {
    setStep((s) => Math.min(STEP_LABELS.length - 1, s + 1))
  }

  // "Skip this step" records an explicit skip for the step's choice (so the
  // summary shows "not configured" rather than a half-answered state), then
  // advances — distinct from "Continue", which keeps whatever's selected.
  // It overrides any current selection: skipping means skipping.
  function skipStep() {
    if (step === 1) setDeployMethod('skip')
    if (step === 2) setMetricsMethod('skip')
    next()
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="flex items-center justify-between gap-4">
        <p className="font-body text-xs font-bold uppercase tracking-[0.3em] text-accent">Get started with KubeX</p>
        <button
          type="button"
          onClick={finish}
          disabled={complete.isPending}
          className="font-body text-xs font-bold uppercase tracking-[0.2em] text-ink-muted transition-colors hover:text-accent disabled:opacity-50"
        >
          Skip setup
        </button>
      </div>

      <div className="mt-6">
        <Stepper steps={STEP_LABELS} current={step} />
      </div>

      <div className="mt-10">
        {step === 0 && <ConnectReposStep installations={installations} />}
        {step === 1 && (
          <DeployMethodStep
            value={deployMethod}
            onChange={setDeployMethod}
            onAddCluster={() => setShowAddCluster(true)}
            ingestPublicUrl={installInfoQuery.data?.ingest_public_url}
            ingestUrlLoading={installInfoQuery.isLoading}
            ingestUrlError={installInfoQuery.isError}
            apiKey={webhookApiKey}
            onApiKeyCreated={setWebhookApiKey}
          />
        )}
        {step === 2 && (
          <MetricsStep
            value={metricsMethod}
            onChange={setMetricsMethod}
            onAddCluster={() => setShowAddCluster(true)}
          />
        )}
        {step === 3 && <NotificationsStep />}
        {step === 4 && (
          <SummaryStep
            installations={installations}
            clusters={clusters}
            deployMethod={deployMethod}
            metricsMethod={metricsMethod}
            onFinish={finish}
            finishing={complete.isPending}
            finishError={finishError}
          />
        )}
      </div>

      {!isLast && finishError && (
        <p className="mt-4 font-body text-xs font-bold uppercase tracking-wide text-failed" role="alert">
          {finishError}
        </p>
      )}

      <div className="mt-10 flex items-center justify-between border-t-2 border-paper-line pt-6">
        <button
          type="button"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="font-body text-xs font-bold uppercase tracking-[0.2em] text-ink-muted transition-colors hover:text-accent disabled:opacity-0"
        >
          Back
        </button>

        {!isLast && (
          <div className="flex items-center gap-4">
            {step > 0 && (
              <button
                type="button"
                onClick={skipStep}
                className="font-body text-xs font-bold uppercase tracking-[0.2em] text-ink-muted transition-colors hover:text-accent"
              >
                Skip this step
              </button>
            )}
            <button
              type="button"
              onClick={next}
              className="border-2 border-accent bg-accent px-5 py-2.5 font-display text-base uppercase tracking-wide text-background transition-transform duration-300 hover:-translate-y-1 active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none"
            >
              Continue
            </button>
          </div>
        )}
      </div>

      {showAddCluster && <AddClusterModal onClose={() => setShowAddCluster(false)} />}
    </div>
  )
}
