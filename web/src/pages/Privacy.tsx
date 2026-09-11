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

export function Privacy() {
  return (
    <LegalPageLayout eyebrow="Legal" title="Privacy Policy" updated="September 2026">
      <p>
        KubeX correlates data from tools you already run — GitHub, ArgoCD, Kubernetes, Prometheus
        and Loki — into one deployment record. This page explains what we collect to do that, and
        what we don't.
      </p>

      <Section heading="What we collect">
        <p>
          <strong className="text-text">Account data.</strong> When you sign in with GitHub, we
          store your GitHub user ID, username, avatar URL and email as provided by GitHub's OAuth
          flow. We don't receive or store your GitHub password.
        </p>
        <p>
          <strong className="text-text">Deployment data.</strong> Once you install the KubeX
          GitHub App and connect a cluster, we ingest CI workflow runs, ArgoCD sync events, and
          Kubernetes pod health, restarts and readiness signals from the lightweight in-cluster
          agent you deploy. This becomes the deployment records and health scores shown in the app.
        </p>
        <p>
          <strong className="text-text">Metrics and logs.</strong> If you connect Prometheus and
          Loki, we query error rates, latency and log lines scoped to the time window of a specific
          deployment — we don't run standing log/metric collection beyond what a health or safety
          score needs.
        </p>
        <p>
          <strong className="text-text">Chat messages.</strong> The in-app assistant is powered by
          the Gemini API. Messages you send it, along with the deployment data it reads via MCP to
          answer you, are sent to Google's Gemini API to generate a response. We don't use your
          chat messages to train any model ourselves.
        </p>
        <p>
          <strong className="text-text">API keys and tokens.</strong> API keys you generate for MCP
          connectors, and webhook/cluster tokens for ArgoCD and Slack, are stored hashed or
          encrypted — never in plaintext — and are only ever shown to you once, at creation.
        </p>
      </Section>

      <Section heading="How we use it">
        <p>
          Solely to run the product: correlating your CI/CD/runtime signals into deployment
          records, computing health and safety scores, rendering dashboards, and answering
          questions you ask the in-app assistant. We don't sell your data, and we don't share it
          with third parties beyond the processors below.
        </p>
      </Section>

      <Section heading="Third-party processors">
        <p>
          GitHub (authentication and CI/CD data), Google Gemini API (the in-app assistant),
          and Slack (if you connect it, for alert delivery). Each processes only what's needed for
          its function and is bound by its own privacy terms.
        </p>
      </Section>

      <Section heading="Data retention">
        <p>
          Deployment records, health scores and chat history are retained for as long as your
          account and org remain active, so historical DORA metrics and trends stay meaningful.
          Deleting your account or disconnecting an integration removes the associated stored data
          on request.
        </p>
      </Section>

      <Section heading="Your rights">
        <p>
          You can revoke the GitHub App's access, rotate or delete API keys, and disconnect
          integrations at any time from Settings. To request a full export or deletion of your
          account data, reach out via the contact link below.
        </p>
      </Section>

      <Section heading="Changes to this policy">
        <p>
          If this policy changes materially, we'll update the date at the top of this page.
          Continued use of KubeX after a change means you accept the revised policy.
        </p>
      </Section>

      <Section heading="Contact">
        <p>
          Questions about this policy or your data — open an issue on the{' '}
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
