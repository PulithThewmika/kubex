import type { ReactNode } from 'react'
import { LegalPageLayout } from '../components/legal/LegalPageLayout'

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="font-display text-2xl uppercase leading-none text-text">{heading}</h2>
      <div className="mt-3 flex flex-col gap-3">{children}</div>
    </section>
  )
}

export function Terms() {
  return (
    <LegalPageLayout eyebrow="Legal" title="Terms of Service" updated="September 2026">
      <p>
        These terms cover your use of KubeX — the dashboards, the API, the GitHub App, the
        in-cluster agent, and the in-app assistant. By creating an account or installing the GitHub
        App, you agree to them.
      </p>

      <Section heading="The service">
        <p>
          KubeX correlates GitHub Actions, ArgoCD and Kubernetes runtime signals into deployment
          records and health scores. It's provided as-is, and functionality depends on the
          integrations you connect — accuracy of health scores, DORA metrics and alerts is only as
          good as the data those integrations expose.
        </p>
      </Section>

      <Section heading="Your account and access">
        <p>
          You're responsible for the GitHub account used to sign in, for API keys and cluster
          tokens you generate, and for keeping them out of source control and shared channels. You
          can revoke access or rotate credentials from Settings at any time.
        </p>
      </Section>

      <Section heading="Acceptable use">
        <p>
          Don't use KubeX to access clusters, repositories or data you're not authorized to access,
          to abuse the API or in-cluster agent beyond reasonable operational use, or to attempt to
          extract other orgs' data. We may suspend access for accounts that do.
        </p>
      </Section>

      <Section heading="Availability">
        <p>
          KubeX depends on upstream services (GitHub, ArgoCD, Prometheus, Loki, Slack, the Gemini
          API) it doesn't control. We don't guarantee uninterrupted availability, and an upstream
          outage or rate limit can affect ingestion, scoring or the assistant.
        </p>
      </Section>

      <Section heading="Disclaimer and limitation of liability">
        <p>
          Health scores, safety scores and assistant responses are decision support, not a
          guarantee — they're generated from the signals available at the time and can be wrong,
          incomplete, or delayed. KubeX is provided without warranties of any kind, and to the
          extent permitted by law, we're not liable for damages arising from reliance on scores,
          alerts or assistant output, or from service interruption.
        </p>
      </Section>

      <Section heading="Changes to these terms">
        <p>
          If these terms change materially, we'll update the date at the top of this page.
          Continued use of KubeX after a change means you accept the revised terms.
        </p>
      </Section>

      <Section heading="Contact">
        <p>
          Questions about these terms — open an issue on the{' '}
          <a
            href="https://github.com/PulithThewmika/kubex"
            target="_blank"
            rel="noreferrer"
            className="text-accent underline underline-offset-2"
          >
            KubeX repository
          </a>
          .
        </p>
      </Section>
    </LegalPageLayout>
  )
}
