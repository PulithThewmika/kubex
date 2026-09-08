import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Bell, MessageSquareText, Plug, Sparkles, ArrowRight } from 'lucide-react'
import { Modal } from '../Modal'
import { useAuth } from '../../contexts/AuthContext'

type TourStep = {
  icon: ReactNode
  title: string
  body: string
  link?: { to: string; label: string }
}

const STEPS: TourStep[] = [
  {
    icon: <Sparkles className="h-6 w-6" strokeWidth={1.75} />,
    title: 'Welcome to KubeX',
    body: 'KubeX stitches your CI, CD and cluster health into one record per deploy and scores whether each release made things better or worse.',
  },
  {
    icon: <MessageSquareText className="h-6 w-6" strokeWidth={1.75} />,
    title: 'Just ask',
    body: 'Chat answers questions in plain English — "what deployed today?", "why is payments degraded?" — grounded in your real correlation and metrics history.',
    link: { to: '/app/chat', label: 'Open Chat' },
  },
  {
    icon: <Plug className="h-6 w-6" strokeWidth={1.75} />,
    title: 'Bring your own Claude',
    body: 'Create an org API key and connect KubeX as an MCP server in Claude Desktop, claude.ai or ChatGPT — investigate incidents from the assistant you already use.',
    link: { to: '/app/settings?tab=api-keys', label: 'Create an API key' },
  },
  {
    icon: <Bell className="h-6 w-6" strokeWidth={1.75} />,
    title: 'Get pinged in Slack',
    body: 'Connect a Slack workspace and KubeX posts every alert as it fires and resolves, to the channels you choose — no polling a dashboard.',
    link: { to: '/app/settings?tab=connections', label: 'Connect Slack' },
  },
]

// ponytail: per-browser localStorage flag, one bump of the version suffix
// re-shows the tour to everyone. Move to a users.welcome_seen_at column if it
// needs to follow a user across devices.
const storageKey = (userId: string) => `kubex.welcome.v1.${userId}`

function alreadySeen(userId: string): boolean {
  try {
    return localStorage.getItem(storageKey(userId)) === '1'
  } catch {
    return true
  }
}

function markSeen(userId: string) {
  try {
    localStorage.setItem(storageKey(userId), '1')
  } catch {
    // private mode / storage disabled — the tour just re-shows next visit
  }
}

/**
 * First-run introduction shown once per user: a short stack of tips covering
 * chat, the MCP connector and Slack alerts. Self-gates on auth + a localStorage
 * flag, so it's safe to mount unconditionally in the app shell.
 */
export function WelcomeTour() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (user && !alreadySeen(user.user_id)) setOpen(true)
  }, [user])

  if (!open || !user) return null

  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  function dismiss() {
    markSeen(user!.user_id)
    setOpen(false)
  }

  return (
    <Modal titleId="welcome-tour-title" title={current.title} onClose={dismiss} widthClassName="max-w-md">
      <div className="flex flex-col gap-5 pt-5">
        <div className="flex h-12 w-12 items-center justify-center border-2 border-paper-line-soft bg-paper text-accent">
          {current.icon}
        </div>

        <p className="font-body text-sm leading-relaxed text-ink-muted">{current.body}</p>

        {current.link && (
          <Link
            to={current.link.to}
            onClick={dismiss}
            className="inline-flex w-fit items-center gap-1.5 border-2 border-paper-line-soft px-3 py-1.5 font-body text-xs font-bold uppercase tracking-[0.15em] text-ink-muted transition-colors hover:border-accent hover:text-accent"
          >
            {current.link.label}
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
          </Link>
        )}

        <div className="mt-1 flex items-center justify-between border-t-2 border-paper-line-soft pt-4">
          <div className="flex gap-1.5" aria-hidden="true">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 w-1.5 ${i === step ? 'bg-accent' : 'bg-paper-line-soft'}`}
              />
            ))}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={dismiss}
              className="border-2 border-transparent px-3 py-1.5 font-body text-xs font-bold uppercase tracking-[0.15em] text-ink-muted transition-colors hover:text-ink"
            >
              {isLast ? 'Close' : 'Skip'}
            </button>
            {!isLast && (
              <button
                type="button"
                onClick={() => setStep((s) => Math.min(s + 1, STEPS.length - 1))}
                className="inline-flex items-center gap-1.5 border-2 border-accent bg-accent px-3.5 py-1.5 font-body text-xs font-bold uppercase tracking-[0.15em] text-background transition-colors hover:bg-accent-hover active:translate-y-px"
              >
                Next
                <ArrowRight className="h-3.5 w-3.5" strokeWidth={2.5} />
              </button>
            )}
            {isLast && (
              <button
                type="button"
                onClick={dismiss}
                className="border-2 border-accent bg-accent px-3.5 py-1.5 font-body text-xs font-bold uppercase tracking-[0.15em] text-background transition-colors hover:bg-accent-hover active:translate-y-px"
              >
                Got it
              </button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  )
}
