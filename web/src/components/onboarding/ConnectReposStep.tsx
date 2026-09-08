import { GITHUB_APP_INSTALL_URL } from '../../lib/github'
import type { Installation } from '../../types/installation'

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.5 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.46-1.19-1.11-1.51-1.11-1.51-.91-.64.07-.63.07-.63 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05a9.3 9.3 0 0 1 2.5-.35c.85 0 1.7.12 2.5.35 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .28.18.61.69.5A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  )
}

type ConnectReposStepProps = {
  installations: Installation[] | undefined
}

export function ConnectReposStep({ installations }: ConnectReposStepProps) {
  const connected = installations && installations.length > 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-3xl uppercase leading-none text-text sm:text-4xl">
          Connect your repositories
        </h2>
        <p className="max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
          Install the KubeX GitHub App on the organization or repositories you deploy from. KubeX watches
          GitHub Actions runs and provisions webhooks automatically — no per-repo secrets to manage.
        </p>
      </div>

      {connected ? (
        <div role="status" className="border-2 border-healthy bg-healthy/10 px-4 py-3 font-body text-xs font-bold uppercase tracking-wide text-healthy">
          {installations.length === 1
            ? `Connected to ${installations[0].account_login}.`
            : `Connected to ${installations.length} accounts.`}{' '}
          You can add more any time from Settings.
        </div>
      ) : null}

      <a
        href={GITHUB_APP_INSTALL_URL}
        className="group inline-flex w-fit items-center gap-3 border-2 border-accent bg-accent px-5 py-3 font-display text-base uppercase tracking-wide text-background transition-transform duration-300 hover:-translate-y-1 active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none"
      >
        <GitHubIcon />
        {connected ? 'Install on another account' : 'Install GitHub App'}
      </a>

      <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
        Opens GitHub in this tab. GitHub returns you to Settings when the install completes; re-open this
        guide from there to pick up where you left off.
      </p>
    </div>
  )
}
