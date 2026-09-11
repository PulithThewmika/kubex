# KubeX

<p align="center">
  <img src="https://github.com/user-attachments/assets/2ade9dc2-b228-4c8a-818b-c8d6a67392cc" alt="KubeX logo" width="160">
</p>

**Deployment-aware observability for Kubernetes.** KubeX correlates your CI
(GitHub Actions), CD (ArgoCD), and runtime health (Kubernetes + Prometheus)
into one record per deployment, then autonomously answers the question every
release raises: *did this deployment make things worse?*

It also computes DORA metrics per team, fires deployment-scoped alerts, and
exposes the whole surface through an MCP server so you can investigate
incidents in natural language from Claude or ChatGPT.

> 📖 **Full documentation lives in the [Wiki](https://github.com/PulithThewmika/kubex/wiki).**
> Architecture deep-dives, the correlation engine, scoring formulas, the
> multi-tenant model, API/MCP reference, and deployment guides are all there.
> This README is just the map.

---

## Demo

https://github.com/user-attachments/assets/c130fc35-31f4-4221-a727-eb04b031f3fe

## Why it exists

Most observability tools tell you *something* is wrong. They rarely tell you
*which deployment* caused it. KubeX links every CI run and every ArgoCD sync
into a single deployment record — even when the image-tag bump commit means
the SHAs don't match — and scores the release's impact on error rate,
latency, and pod restarts against a pre-deploy baseline.

Two novel pieces:

- **Correlation engine** — joins GitHub and ArgoCD events into one deployment,
  handles out-of-order events, and auto-registers unknown services.
- **Health scoring agent** — a scheduled batch job that grades each release
  0–100 (`healthy` / `degraded` / `failed`) from real metrics, with an
  explainable breakdown.

## Features

| | |
|---|---|
| **Per-deployment correlation** | CI + CD + runtime health as one timeline |
| **Autonomous health scoring** | Every release graded against its own baseline |
| **Pre-deploy safety score** | Rule-based risk estimate before you ship |
| **DORA metrics** | Deploy frequency, lead time, change-failure rate, MTTR — per team |
| **Deployment-scoped alerting** | Alerts routed to Slack, tied to the release that caused them |
| **MCP server** | Natural-language incident investigation from Claude / ChatGPT |
| **Grafana dashboards** | Operator (platform-wide) and customer (org-scoped) sets |
| **Multi-tenant SaaS** | GitHub OAuth login, org isolation, GitHub App onboarding |

## Architecture at a glance

![KubeX architecture](https://github.com/user-attachments/assets/8121a0e9-8b8a-406a-a67a-a3117cd6415c)

- **Kind cluster** — sample app, Prometheus stack, Loki, ArgoCD, Alertmanager.
- **docker-compose** — ingest service, detection agent, MCP server, Grafana.
- **Supabase Postgres** — the integration contract; every producer writes it,
  every consumer reads it.

See the [Architecture](https://github.com/PulithThewmika/kubex/wiki) pages in
the Wiki for the full picture.

## Repository layout

```text
deploy/     Kind config, docker-compose, Helm values, Grafana/ArgoCD/Alertmanager config
services/
  ingest/     FastAPI — webhooks, REST API, auth, chat proxy, correlation engine
  agent/      Detection agent — health scoring, DORA reads, alerting, blast radius
  mcp-server/ MCP server (TypeScript) — deployment/metrics/logs tools
web/        React shell (Vite)
scripts/    End-to-end smoke test
```

The sample application (frontend → orders → payments) lives in its own repo:
[deploylens-sample-app](https://github.com/PulithThewmika/deploylens-sample-app).

## Quick start

Prerequisites: Docker (Compose v2), Kind, kubectl, Helm, a Supabase project.

```bash
cp .env.example .env        # fill in Supabase + GitHub + Slack values
make cluster-up             # create the Kind cluster
make migrate                # apply SQL migrations to Supabase
make up                     # ingest, agent, mcp-server, grafana
make forwards               # bridge in-cluster Prometheus/Loki/Alertmanager
```

Deploying the in-cluster pieces (Prometheus stack, Loki, ArgoCD, Alertmanager,
and the sample app via ArgoCD) is a separate step — see the
[Wiki](https://github.com/PulithThewmika/kubex/wiki) setup guide.

Local ports: Grafana `3000`, ingest `8000`, React shell `5173`,
Prometheus `9090`, ArgoCD `8443`.

Run `make help` for the full list of workflow targets. Detailed setup —
Supabase connection strings, GitHub App registration, ngrok webhook tunnel —
is in the [Wiki](https://github.com/PulithThewmika/kubex/wiki).

## Tech stack

Python · FastAPI · SQLAlchemy 2.x · asyncpg · PostgreSQL (Supabase) ·
Prometheus · Loki · ArgoCD · Grafana · TypeScript (MCP) · React + Vite ·
MCP · Docker · Kind

## Status

Solo academic project (12-week timeline). M1–M3 complete (foundation,
scoring, DORA, alerts, MCP, shell). M4 in progress — the SaaS transition
(GitHub App onboarding, cluster agent, tiered integration, frontend upgrade).

## License

[MIT](LICENSE)
