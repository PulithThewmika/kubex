import { Logo } from '../layout/Logo'

const LINKS = [
  { label: 'GitHub', href: 'https://github.com/PulithThewmika/kubex' },
  { label: 'Docs', href: 'https://github.com/PulithThewmika/kubex#readme' },
  { label: 'Project board', href: 'https://github.com/users/PulithThewmika/projects/3' },
]

export function LandingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-4 py-10 text-sm text-text-muted sm:flex-row sm:justify-between sm:px-6">
        <div className="flex flex-col items-center gap-1 sm:items-start">
          <Logo markClassName="h-6 w-6" />
          <span className="text-xs text-text-faint">Deployment-aware observability.</span>
        </div>
        <div className="flex gap-6">
          {LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="transition-colors hover:text-text"
            >
              {link.label}
            </a>
          ))}
        </div>
      </div>
    </footer>
  )
}
