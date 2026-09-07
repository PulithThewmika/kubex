export function LandingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-4 py-8 text-sm text-text-muted sm:flex-row sm:justify-between sm:px-6">
        <span>KubeX</span>
        <div className="flex gap-6">
          <a
            href="https://github.com/PulithThewmika/kubex"
            target="_blank"
            rel="noreferrer"
            className="transition-colors hover:text-text"
          >
            GitHub
          </a>
          <a
            href="https://github.com/PulithThewmika/kubex#readme"
            target="_blank"
            rel="noreferrer"
            className="transition-colors hover:text-text"
          >
            Docs
          </a>
        </div>
      </div>
    </footer>
  )
}
