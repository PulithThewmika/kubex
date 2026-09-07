import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AddClusterModal } from '../components/AddClusterModal'
import { ConnectReposStep } from '../components/onboarding/ConnectReposStep'
import { DeployMethodStep, type DeployMethod } from '../components/onboarding/DeployMethodStep'
import { MetricsStep, type MetricsMethod } from '../components/onboarding/MetricsStep'
import { Stepper } from '../components/onboarding/Stepper'
import { SummaryStep } from '../components/onboarding/SummaryStep'
import { useClusters } from '../hooks/useClusters'
import { useCompleteOnboarding } from '../hooks/useCompleteOnboarding'
import { useInstallInfo } from '../hooks/useInstallInfo'
import { useInstallations } from '../hooks/useInstallations'

const STEP_LABELS = ['Repositories', 'Deployments', 'Metrics', 'Done']

export function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [deployMethod, setDeployMethod] = useState<DeployMethod | null>(null)
  const [metricsMethod, setMetricsMethod] = useState<MetricsMethod | null>(null)
  // ponytail: the health-check URL is captured but not persisted — there's
  // no service to attach it to during onboarding. Wire it to
  // PUT /api/services/:name/health-check once the org's first deployment
  // exists.
  const [healthCheckUrl, setHealthCheckUrl] = useState('')
  const [showAddCluster, setShowAddCluster] = useState(false)

  const { data: installations } = useInstallations()
  const { data: clusters } = useClusters()
  const { data: installInfo } = useInstallInfo()
  const complete = useCompleteOnboarding()

  const isLast = step === STEP_LABELS.length - 1

  function finish() {
    complete.mutate(undefined, { onSuccess: () => navigate('/app', { replace: true }) })
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Get started with KubeX</p>
        <button
          type="button"
          onClick={finish}
          disabled={complete.isPending}
          className="text-xs font-medium text-text-muted underline-offset-4 hover:text-text hover:underline disabled:opacity-50"
        >
          Skip setup
        </button>
      </div>

      <div className="mt-6">
        <Stepper steps={STEP_LABELS} current={step} />
      </div>

      <div className="mt-8">
        {step === 0 && <ConnectReposStep installations={installations} />}
        {step === 1 && (
          <DeployMethodStep
            value={deployMethod}
            onChange={setDeployMethod}
            onAddCluster={() => setShowAddCluster(true)}
            ingestPublicUrl={installInfo?.ingest_public_url}
          />
        )}
        {step === 2 && (
          <MetricsStep
            value={metricsMethod}
            onChange={setMetricsMethod}
            onAddCluster={() => setShowAddCluster(true)}
            healthCheckUrl={healthCheckUrl}
            onHealthCheckUrlChange={setHealthCheckUrl}
          />
        )}
        {step === 3 && (
          <SummaryStep
            installations={installations}
            clusters={clusters}
            deployMethod={deployMethod}
            metricsMethod={metricsMethod}
            onFinish={finish}
            finishing={complete.isPending}
            finishError={complete.isError ? (complete.error as Error).message : null}
          />
        )}
      </div>

      <div className="mt-8 flex items-center justify-between border-t border-border pt-5">
        <button
          type="button"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="rounded-md px-3 py-2 text-sm font-medium text-text-muted transition-colors hover:text-text disabled:opacity-0"
        >
          Back
        </button>

        {!isLast && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              className="rounded-md px-3 py-2 text-sm font-medium text-text-muted transition-colors hover:text-text"
            >
              Skip this step
            </button>
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              className="rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90"
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
