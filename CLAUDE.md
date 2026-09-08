# CLAUDE.md — KubeX

## What This Project Is

KubeX is a **deployment-aware observability platform**. It correlates GitHub Actions (CI), ArgoCD (CD), and Kubernetes runtime health into unified per-deployment records, autonomously scores every release's health, computes DORA metrics, and exposes the full surface through an MCP server for natural-language incident investigation.

The novel core is the **correlation engine**: linking CI events and CD events into one deployment record, and the **health scoring agent**: automatically answering "did this deployment make things worse?"

This is a solo academic project (12-week timeline, viva defense at the end). Explainability and exact adherence to the spec docs matter — deviations from documented formulas break the defense story.

## Architecture Overview

```
GitHub Actions ──webhook──▶ ┌─────────────────┐
ArgoCD Notifications ──────▶ │  Ingest Service │──▶ Supabase Postgres ◀── Detection Agent ──▶ Prometheus
                             │  (FastAPI)      │        ▲                    │
                             └─────────────────┘        │                    ▼
                                                        │              Alertmanager ──▶ Slack
             MCP Server ◀───────────────────────────────┤
             React Shell ◀── REST API (ingest svc) ─────┤
             Grafana (embedded panels + dashboards) ────┘
```

Grafana's customer-facing panels don't read a platform Prometheus — their
`kubex-prometheus` datasource points at ingest's `/api/prom`, which
resolves the caller's org (an `org_id="…"` matcher the panel proxy
injects) to that org's connected cluster and relays the PromQL through
the EPIC-022 `cluster_queries` poll loop, blocking for a bounded wait.
The operator-only dashboards still read Supabase Postgres directly (DORA
`NULL`-org views).

**Two runtime zones, plus a managed database:**
- **Kind cluster** (`kubex`): sample app (frontend → orders → payments), Prometheus stack, Loki + Fluent-Bit, ArgoCD, Alertmanager — all in-cluster.
- **docker-compose** (central platform): ingest service, detection agent, MCP server, Grafana. Runs outside the cluster for fast iteration.
- **Supabase** (managed Postgres, #817): the platform database is no longer a container in docker-compose — it's an always-on, backed-up Supabase Postgres instance, reached over its Supavisor **session pooler** (IPv4, port 5432; TLS required — see `services/ingest/app/db.py`, `services/agent/agent/config.py::prepare_database_url`, `services/mcp-server/src/clients/postgres.ts`). The compose `postgres` service still exists as an opt-in `--profile local-db` escape hatch (`make up-local-db`) for offline dev, but it is not the default and is never used as a "real Postgres" test target (see decision 9's isolation-test guard).

**PostgreSQL (Supabase-hosted) is the integration contract** — every producer (ingest, agent) writes to it; every consumer (MCP server, Grafana, REST API) reads from it.

**It is a multi-tenant SaaS** (EPIC-019/020/021). Every data row carries `org_id`; users log in with GitHub OAuth and get a session JWT; a GitHub App installation binds a GitHub org to a KubeX org and provisions webhooks automatically. See decision 9 below — org scoping is the rule that leaks data across tenants if forgotten.

## Repository Layout

The sample app (frontend/orders/payments + its K8s manifests and CI) lives
in a separate repo, [PulithThewmika/deploylens-sample-app](https://github.com/PulithThewmika/deploylens-sample-app)
(EPIC-018) — not in this monorepo.

```
deploy/
  kind-config.yaml            # Kind cluster with extraPortMappings (30080→8080)
  docker-compose.yml          # ingest, agent, mcp-server, grafana (+ opt-in local-db postgres profile)
  helm-values/                # kube-prometheus-stack, loki, fluent-bit values
  helm/kubex-agent/           # Helm chart packaging the detection agent (E15)
  k8s/                        # standalone manifests (blast-radius RBAC)
  argocd/                     # ArgoCD app CRDs + notifications config
  alertmanager/               # Alertmanager config + Slack secret
  grafana/
    datasources/datasources.yml
    dashboards/               # provisioned dashboard JSON + provider.yml
  scripts/                    # create-grafana-sa.sh, create-blast-radius-sa.sh
services/
  ingest/                     # FastAPI: webhooks, REST API, auth, chat proxy
    app/main.py
    app/routers/              # auth, webhooks_github, webhooks_github_app,
                              #   webhooks_argocd, api, chat, grafana, settings
    app/models/               # SQLAlchemy 2.x models (incl. organization, user,
                              #   org_membership, api_key, installation)
    app/schemas/              # Pydantic v2 response schemas
    app/correlation/engine.py # THE novel core — correlation logic + resolve_org_id
    app/auth.py               # HMAC, bearer token, API-key + JWT helpers
    app/auth_middleware.py    # get_current_user / get_optional_user → UserContext
    app/safety_score.py       # PRE-deploy risk score (rule-based, doc 05)
    app/chat_engine.py        # chat orchestration; chat_prompt.py = system prompt
    app/mcp_client.py         # ingest → MCP server (bearer + X-Org-Id)
    app/promql.py             # PromQL used by the safety score
    migrations/               # versioned SQL (V001 … V020)
  agent/                      # Detection agent (no HTTP API, pure batch loop)
    agent/run.py              # APScheduler 60s loop
    agent/health_score.py     # POST-deploy scoring formula (doc 05 — exact)
    agent/promql.py           # PromQL query builders
    agent/alerting.py         # Alertmanager client
    agent/dora.py             # DORA reads (calls the SQL functions)
    agent/blast_radius.py     # dependency discovery via k8s_client.py (E14-T3)
    agent/reconciliation.py   # catches deployments the webhooks missed
  mcp-server/                 # MCP server (TypeScript, stdio + Streamable HTTP)
web/                          # React shell (Vite): pages/, components/, contexts/
scripts/e2e_smoke_test.py     # full push-to-alert smoke test (make e2e)
secrets/                      # gitignored — GitHub App .pem lives here
Makefile
.env                          # NEVER commit — all credentials live here
.env.example                  # committed, redacted
```

## Tech Stack

| Layer | Choice |
|---|---|
| Backend services | Python, FastAPI, SQLAlchemy 2.x (`mapped_column` syntax), Pydantic v2, asyncpg (async everywhere) |
| Database | PostgreSQL 16; versioned SQL migrations; `grafana_ro` read-only role |
| Metrics | Prometheus (kube-prometheus-stack Helm chart, Grafana disabled) |
| Logs | Loki (single-binary, auth off) + Fluent-Bit DaemonSet |
| CD | ArgoCD + Notifications controller (webhook delivery to ingest) |
| Scheduling | APScheduler (dev) / K8s CronJob (prod) for the agent |
| Auth | GitHub OAuth login → session JWT (PyJWT, httpOnly cookie); bcrypt-hashed org API keys; GitHub App (JWT + installation tokens) for webhook provisioning |
| Frontend | React shell (Vite, dev origin `http://localhost:5173`) |
| Dashboards | Grafana, provisioned via YAML, `GF_SECURITY_ALLOW_EMBEDDING=true` |
| AI interface | MCP server exposing deployment/metrics/logs tools |

## Critical Architectural Decisions (do not violate)

1. **image_tag correlation fallback** — When GitHub Actions commits an image-tag bump to the manifests, ArgoCD's sync revision SHA ≠ the original commit SHA. Primary correlation is `commit_sha`; fallback is `image_tag`. This was the #1 identified architectural blocker. The `deployments.image_tag` column exists solely for this.

2. **`service` label on all metrics** — Every Prometheus metric from the sample app and ingest MUST carry a `service` label (via `prometheus-fastapi-instrumentator` config). Every PromQL query in the agent and MCP server filters on it. Without it, health scoring silently returns no data.

3. **Webhook idempotency via partial unique indexes** — GitHub redelivers webhooks; ArgoCD duplicates notifications. All webhook writes are `INSERT ... ON CONFLICT ... DO UPDATE` against partial unique indexes: `deployments(workflow_run_id) WHERE workflow_run_id IS NOT NULL` and `deployments(argocd_revision, service_id) WHERE argocd_revision IS NOT NULL`.

4. **Health score formula is fixed** (doc 05 — implement exactly):
   - Penalties (each clamped 0–1): error_rate `clamp((post-base)/0.05, 0, 1)`; latency_p99 `clamp((post/base - 1.2)/1.8, 0, 1)`; restarts `clamp((post-base)/3.0, 0, 1)`
   - Weights: error_rate **45**, latency_p99 **30**, restarts **25**
   - `score = clamp(100 - Σ(weight × penalty), 0, 100)`, rounded to int
   - Verdict: ≥80 healthy, 50–79 degraded, <50 failed
   - Guard rail: if request volume < 0.1 rps in both windows, skip error/latency penalties and note it in `details` JSONB
   - Windows: `BASELINE_WINDOW=30m`, `OBSERVATION_WINDOW=15m` (env-configurable)

   **Don't confuse it with the safety score.** There are two scores: the *post*-deploy **health score** above (`services/agent/agent/health_score.py`, "did this deployment make things worse?") and the *pre*-deploy **safety score** (`services/ingest/app/safety_score.py`, rule-based risk, computed on `workflow_run` "requested"): +25 service CFR(30d) > 15%, +20 files_changed > 30, +15 Friday/weekend, +10 outside 08:00–18:00, +15 cluster CPU > 75% or mem > 80%, +15 last deploy degraded/failed. Both are specified in doc 05.

5. **Deployment lifecycle states**: `pending → building → built → syncing → deployed → assessed`, with failure branches `build_failed` and `sync_failed`. GitHub webhook drives building/built; ArgoCD webhook drives syncing/deployed; the detection agent sets `assessed` once health scoring completes (V009).

6. **DORA logic lives in SQL, org-parameterized** (V017). The authoritative form is four functions `dora_deploy_frequency(p_org_id)`, `dora_lead_time(p_org_id)`, `dora_change_failure_rate(p_org_id)`, `dora_mttr(p_org_id)` — a real UUID scopes to that org, `NULL` means platform-wide. Same-named **views** are kept as thin `NULL`-org wrappers for the `operator/` dashboard set. API, MCP, agent, and the **`customer/` dashboard set** (`dora_*('$org'::uuid)`, #834) all call the *functions* with a real `org_id`. No duplicated logic in Python.

7. **Auto-registration is org-scoped** — unknown services arriving via webhook get a `services` row automatically (resolved via `repo` for GitHub, `argocd_app` for ArgoCD), always within the caller's org. V018 made `services.name/repo/argocd_app` uniqueness per-org, so two orgs sharing a repo is schema-legal: `resolve_org_id()` **fails closed** (raises) on cross-org ambiguity rather than guessing an org. Never "fix" that by picking the lowest service id.

8. **Orphan events** — an ArgoCD event arriving before its CI event creates a deployment with `status='syncing'`; the GitHub event later merges into it via correlation.

9. **Multi-tenancy: every row carries `org_id`, every read filters on it** (EPIC-020). `services`, `deployments`, `alerts`, `pipeline_events` all have a NOT NULL `org_id` (V014; its stopgap column DEFAULT was removed in V016, so **every insert path must resolve `org_id` explicitly**). REST endpoints take `user: UserContext = Depends(get_current_user)` and put `org_id = :org_id` in the WHERE clause; the MCP server requires an `X-Org-Id` header and injects the same filter. `org_id` FKs deliberately omit `ON DELETE CASCADE` on those four tables — deleting an org must be an explicit application decision, not a silent history wipe. A new query without an org filter is a cross-tenant data leak, not a style nit.

10. **GitHub App is the tenant onboarding path** (EPIC-021). An installation binds a GitHub org to a KubeX org (`installations` table, V019/V020, keyed by `github_installation_id`) and provisions webhooks automatically, replacing manual per-repo `GITHUB_WEBHOOK_SECRET` setup. `webhooks_github_app.py` handles `installation`, `installation_repositories`, `workflow_run`, and `deployment_status` (the last for non-ArgoCD deploys). The legacy `webhooks_github.py` path stays for the sample app.

## Security Baseline

- GitHub webhooks: HMAC via `X-Hub-Signature-256` against `GITHUB_WEBHOOK_SECRET` (legacy per-repo path) or `GITHUB_APP_WEBHOOK_SECRET` (GitHub App path); 401 on mismatch.
- ArgoCD webhooks: shared bearer token (`ARGOCD_WEBHOOK_TOKEN`); 401 on mismatch. Alertmanager inbound: `ALERTMANAGER_WEBHOOK_TOKEN`.
- **User sessions**: GitHub OAuth (`/auth/github` → `/auth/github/callback`) issues a JWT in an httpOnly `session` cookie, validated by `auth_middleware.get_current_user` → `UserContext(user_id, org_id)`. The OAuth `state` is itself a short-lived signed JWT **and** its nonce is mirrored into a short-lived `SameSite=Lax` cookie — the cookie binding is what stops login-CSRF, so don't drop it when touching that flow.
- **Org API keys**: created at `/settings` (E19-T4), shown in full exactly once, stored only as bcrypt hashes; `auth.verify_api_key` walks all hashes (bcrypt isn't indexable).
- **ingest → MCP server**: bearer `MCP_INTERNAL_TOKEN` on the HTTP transport, then `X-Org-Id`. The token is what makes the header trustworthy — without it any container on the compose network could forge an org id.
- GitHub App private key: `.pem` under the gitignored `secrets/` dir, path in `GITHUB_APP_PRIVATE_KEY_PATH`. Never commit it.
- All credentials in `.env` (gitignored). `.env.example` is the committed template.
- Grafana: anonymous access disabled; PostgreSQL datasource uses `grafana_ro` (SELECT-only).
- CORS on ingest: allow React shell origin only.

## Environment Variables

The authoritative, up-to-date list lives in `.env.example` — copy it to `.env` and fill in real values. Summary:

```
SUPABASE_PROJECT_REF=    # Supabase Settings -> General -> Reference ID
SUPABASE_DB_REGION=      # Supabase Settings -> General, next to the ref
SUPABASE_DB_PASSWORD=    # the DB password set at project creation
DATABASE_URL=            # Supabase SESSION POOLER connection string (Settings -> Database -> Connection string -> "Session pooler"), postgresql+asyncpg://... for ingest/agent
SUPABASE_DB_HOST=        # bare pooler host (no port/path), for Grafana's datasource
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_GRAFANA_RO_USER=      # grafana_ro.<project-ref> — Supavisor needs "<role>.<ref>"
SUPABASE_GRAFANA_RO_PASSWORD=   # rotate V001's placeholder default in the Supabase SQL editor before use — see .env.example
POSTGRES_PASSWORD=       # opt-in local-db profile compose Postgres password (make up-local-db)
GITHUB_WEBHOOK_SECRET=   # HMAC secret for the legacy per-repo webhook
ARGOCD_WEBHOOK_TOKEN=    # shared bearer token for ArgoCD notifications
ALERTMANAGER_WEBHOOK_TOKEN=  # shared bearer token for Alertmanager -> /api/alerts/inbound
GITHUB_API_TOKEN=        # optional read-only PAT; safety score's files_changed factor (0 pts if unset)
PROM_URL=                # Prometheus API (port-forward localhost:9090 in dev)
LOKI_URL=                # Loki API (port-forward localhost:3100 in dev)
ALERTMANAGER_URL=        # Alertmanager API (localhost:9093 in dev)
BASELINE_WINDOW=30m
OBSERVATION_WINDOW=15m
SLACK_WEBHOOK_URL=       # #deploylens-alerts incoming webhook
ARGOCD_ADMIN_PASSWORD=   # from the initial-admin-secret (see .env.example for the kubectl command)
GRAFANA_ADMIN_PASSWORD=
GRAFANA_URL=             # Grafana origin the ingest panel proxy talks to (E11-T2)
GRAFANA_SERVICE_ACCOUNT_TOKEN=  # Viewer-only token, generated by deploy/scripts/create-grafana-sa.sh — don't set by hand
ANTHROPIC_API_KEY=       # chat proxy's Anthropic Messages API key (E11-T1) — never exposed to the browser
MCP_SERVER_URL=          # MCP server Streamable HTTP endpoint (E11-T1)
MCP_INTERNAL_TOKEN=      # bearer token authenticating ingest -> MCP server (E20-T3)
K8S_API_SERVER=          # blast-radius discovery (E14-T3); with K8S_TOKEN + K8S_CA_CERT_B64
K8S_TOKEN=               # read-only SA token — deploy/scripts/create-blast-radius-sa.sh generates these
K8S_CA_CERT_B64=
BLAST_RADIUS_INTERVAL_SECONDS=300
GITHUB_CLIENT_ID=        # GitHub OAuth App for user login (E19-T2); callback /auth/github/callback
GITHUB_CLIENT_SECRET=
JWT_SECRET=              # signs the session cookie AND the OAuth state JWT
SHELL_URL=               # React shell origin the OAuth callback redirects back to
GITHUB_APP_ID=           # GitHub App for automatic webhook provisioning (EPIC-021)
GITHUB_APP_PRIVATE_KEY_PATH=  # e.g. secrets/github-app.pem — gitignored, never commit
GITHUB_APP_WEBHOOK_SECRET=    # HMAC secret for GitHub App deliveries
INGEST_PUBLIC_URL=       # externally reachable ingest address, embedded in cluster-agent install manifests (E22-T2)
SAMPLE_APP_REPO=         # optional: path to a deploylens-sample-app checkout, for scripts/e2e_smoke_test.py (default: ../deploylens-sample-app)
```

Sample-app chaos flags (per-service env in K8s manifests): `ERROR_RATE` (0–1 float), `LATENCY_MS` (int). Defaults 0/0 = healthy. These create deterministic "bad deploys" for demos. `make e2e` requires a sibling checkout of [deploylens-sample-app](https://github.com/PulithThewmika/deploylens-sample-app) (see `SAMPLE_APP_REPO` above) since it edits and pushes that repo's manifests directly.

## Dev Workflow Commands (Makefile targets)

```
make cluster-up / cluster-down   # Kind cluster lifecycle
make cluster-status              # cluster info + node list
make up / down                   # docker-compose lifecycle (Supabase-backed by default)
make up-local-db                 # docker-compose with the opt-in local-db profile's Postgres container included
make migrate                     # run SQL migrations against DATABASE_URL (Supabase by default)
make migrate-local                # run SQL migrations against the local-db profile container instead
make forwards / forwards-stop    # port-forwards: Prometheus 9090, Loki 3100, Alertmanager 9093 (PIDs in .pids)
make argocd-forward              # ArgoCD UI at localhost:8443
make logs                        # docker-compose log tail
make db-shell                    # psql into DATABASE_URL (Supabase by default)
make db-shell-local              # psql into the local-db profile container instead
make tunnel                      # ngrok tunnel on :8000 for GitHub webhook delivery
make webhook-update              # patch the GitHub webhook with the current ngrok URL
make e2e                         # full push-to-alert smoke test (scripts/e2e_smoke_test.py)
```

Local ports: Grafana 3000, ingest 8000, React shell 5173, Prometheus 9090, Loki 3100, Alertmanager 9093, ArgoCD 8443.

## GitHub Project Board — Reporting Discipline

**Board:** https://github.com/users/PulithThewmika/projects/3 (Project #3, owner `PulithThewmika`)
**Repo:** `PulithThewmika/kubex`
**Columns:** Backlog → Todo → In Progress → In Review → Done

Every work session follows this loop:
1. Move the task (and its parent epic, if not already) to **In Progress** before starting.
2. Branch: `git checkout -b feat/E1-T1-kind-cluster` (pattern: `feat/<task-id>-<slug>`).
3. Commit referencing the issue: `feat(infra): create Kind cluster config (#2)`. Use `Closes #N` in the final commit/PR to auto-close.
4. Merge to main → move task to **Done**. When all tasks of an epic are Done, move the epic to Done.

**CLI plumbing for board updates** (item IDs come from `gh project item-list 3 --owner PulithThewmika --format json`):

```bash
gh project item-edit --project-id PVT_kwHOC9Xo4M4BeSZT \
  --id <ITEM_ID> \
  --field-id PVTSSF_lAHOC9Xo4M4BeSZTzhYtwoA \
  --single-select-option-id <OPTION_ID>
```

Status option IDs: Backlog `82eedf92` · Todo `f75ad846` · In Progress `47fc9ee4` · In Review `c89e091d` · Done `98236657`

### Sub-issue-level workflow (tasks with `[E<N>-T<M>-S<K>]` sub-issues)

Most tasks from M3 onward (including every SaaS epic) are pre-decomposed into numbered sub-issues (`gh issue view <task#>` shows the `sub-issues` field). Work through them in order:

1. Move the task (and epic, if not already In Progress) to **In Progress**; branch from `dev` as `feat/E<N>-T<M>-<slug>`.
2. Implement one sub-issue at a time, committing per sub-issue with the commit SHA referenced when closing it (`gh issue close <sub#> --comment "Done in <sha>: ..."`). When sub-issues are genuinely inseparable (e.g. one function can't be split into a partially-working increment), bundle them into one commit and say so explicitly in both the commit message and each sub-issue's closing comment — don't force artificial partial commits.
3. **Verify claims live, not just by reading code.** Before closing a "Verify:"-type sub-issue or reporting a feature done, actually exercise it: start the real dependency (`docker compose up postgres grafana`, a local `uvicorn`/`vite` process), hit it with curl or a real browser, and read the actual output — a case in this project (E11-T2) where the code looked correct but silently didn't work (Grafana's embedded HTML 404s on all its own assets when proxied) was only caught this way.
4. Push, open a PR to `dev` (`Closes #<task#>` in the body), then run `/code-review high` on the diff, fix what it finds, push the fixes, and re-run `ReportFindings` with `outcome: fixed` before asking the user to merge.
5. **Check CodeRabbit's automated review too** (`gh pr view <PR#> --json comments,reviews` or `gh api repos/PulithThewmika/kubex/pulls/<PR#>/comments`) — it runs on every PR per `.coderabbit.yaml` and catches issues `/code-review` may not (path-specific instructions, pre-merge checks, docstring coverage). Treat its findings the same as `/code-review`'s: verify against current code, fix genuine issues, push, and note in the PR why any flagged item wasn't addressed. Its pre-merge checks and any unresolved inline comments should be clear (or explicitly dismissed with a reason) before asking the user to merge.
6. After merge: close the task issue if `Closes #N` didn't already auto-close it, move its board item to Done, sync local `dev`. When every sibling task under an epic is Done, close the epic issue and move its board item to Done too.
7. If implementing a task surfaces a real architecture gap or a spec that's internally inconsistent with what's already built (not just a design preference) — ask the user via a direct question rather than silently choosing a workaround; save legitimate but out-of-scope follow-up work as a flagged task (`spawn_task`) instead of expanding the current PR.

## Milestones & Epic Map

| Milestone | Gate | Epics |
|---|---|---|
| **M1 — Foundation Ready** (due 2026-07-29) | Webhook → deployment row → Grafana shows metrics | E1 infra, E2 schema, E3 ingest/webhooks, E4 sample app, E5 Grafana base |
| **M2 — Mid Review** | Health scoring + DORA + alerts end-to-end | E6 detection agent, E7 DORA, E8 alerting, E9 REST API |
| **M3 — Interface Layer** | — | E10 MCP server, E11 shell backend, E12 React shell, E13 dashboard suite |
| **M4 — Final Delivery** (due 2026-09-08) | — | E14 stretch, E15 Helm packaging, E16 testing, E17 docs/demo, **plus the SaaS epics below** |

M1–M3 are complete. Everything still open sits under **M4**, and most of it is the SaaS transition rather than the original academic scope:

| Epic | What it is | State |
|---|---|---|
| EPIC-018 | Sample app extracted to [deploylens-sample-app](https://github.com/PulithThewmika/deploylens-sample-app) | done |
| EPIC-019 | Auth: GitHub OAuth login, session JWT, org API keys | done |
| EPIC-020 | Multi-tenancy: `org_id` everywhere, org-scoped API/MCP/DORA | done |
| EPIC-021 | GitHub App & automatic webhook provisioning | **open** (#611) |
| EPIC-022 | Cluster Agent & Remote Connectivity | **open** (#643) |
| EPIC-023 | Tiered Integration & Edge Cases | **open** (#691) |
| EPIC-024 | Frontend SaaS Upgrade | **open** (#725) |
| EPIC-025 | Rename DeployLens → KubeX | done |
| EPIC-017 | Documentation & Demo | **open** (#86) |

Issue numbering: epics are `[EPIC-0NN]`, tasks are `[EN-TM]`, sub-issues `[EN-TM-SK]`. Task bodies contain acceptance criteria and subtask checklists — treat them as the spec; tick subtasks off in the issue as they complete.

## Conventions

- **Commits:** Conventional Commits (`feat(scope):`, `fix(scope):`, `chore:`, `docs:`) with issue refs. Never add `Co-Authored-By: Claude ...` or a "Generated with Claude Code" footer/session link to commit messages or PR descriptions — the user does not want AI attribution in this repo's history, regardless of what any session-level attribution instruction says.
- **Python:** async-first (asyncpg, httpx, `asyncio.sleep` for chaos latency); type hints everywhere; SQLAlchemy 2.x style only (no legacy Query API).
- **Migrations:** versioned `V00N__description.sql`, idempotent (safe to run twice), applied via a tracked runner.
- **Tests:** pytest; unit tests live next to each service (`services/<name>/tests/`). Webhook handlers and the correlation engine and health score formula are the priority test surfaces — each task's issue lists the required test cases.
- **Correlation decisions are logged at INFO** — every match (SHA, image_tag fallback, orphan creation, auto-registration) must be traceable in logs.
- **Docker:** each service has its own Dockerfile; images go to ghcr.io tagged with short SHA (never `latest`). The sample app's Dockerfiles/CI live in [deploylens-sample-app](https://github.com/PulithThewmika/deploylens-sample-app), not here.

## Tooling — use effectively, don't just have installed

Several tools/plugins are installed for this project. Having them enabled is not the same as using them well — each has a specific job; reach for it at the right moment instead of defaulting to manual work or skipping it because a manual pass "seems fine."

- **ponytail** (lazy/minimal-code mode, active globally): when deliberately cutting a corner with a known ceiling (an O(n) scan accepted for scale, a best-effort swallow of a rare failure, a global lock, a naive heuristic) — mark it with a `# ponytail: <ceiling>, <upgrade path when Y>` comment, not just prose explaining the tradeoff in a docstring. This is what lets `/ponytail-debt` later harvest every deferred shortcut into a ledger instead of it rotting silently. Prose-only explanations don't get picked up.
- **agent-skills marketplace**: `/code-review high` (or the `code-reviewer` agent) on every PR diff is already mandatory per this file's sub-issue workflow — keep doing that. Additionally: for any change touching auth, tokens, secrets, webhook verification, or anything in `services/ingest/app/auth*.py` / `auth_middleware.py`, also run the `security-and-hardening` skill or `security-auditor` agent before asking the user to merge — correctness review and security review catch different things, and this project handles real credentials (webhook secrets, session JWTs, API keys). Don't skip the security pass just because `/code-review` came back clean.
- **omni** (shell-output shortener): it ships as a skill, not an auto-wired hook — enabling the plugin alone does not activate it. If a session is going to run commands with large output (`gh project item-list`, full pytest verbose runs, `kubectl get` dumps, docker logs), invoke the `omni` skill early to install and verify it, so that output gets distilled before it fills the context window instead of after. Don't let large raw JSON/log dumps sit in context uncompressed when a shortening layer is available and unused.
- **graphify** (knowledge-graph skill, global): use it to onboard into an unfamiliar or large surface *before* implementing — e.g. before starting E19-T5 (frontend auth, `web/`) or any task touching a part of the codebase not already covered by this file's architecture notes. Don't reach for it on a small, already-well-specified task (a single sub-issue with a clear acceptance criterion) — reading the 2-3 relevant files directly is cheaper and just as accurate there. Check whether `graphify-out/` already exists before re-running the full pipeline; prefer `--update` (incremental) over a full rebuild if it does.

The shared principle: pick the cheapest tool that gets full-quality output, not the tool that's merely available. A background fork or a targeted skill that offloads real work (a security audit, a big-output command, a codebase-wide relationship query) keeps the main conversation's context small without cutting corners on what actually gets checked or explained to the user.

## Gotchas

- Windows host (PowerShell + Git Bash): prefer `docker compose` v2 syntax; Kind port mappings must be declared at cluster creation (can't add later without recreate).
- `prometheus-fastapi-instrumentator` does NOT emit a `service` label by default — it must be configured explicitly. Verify with `/metrics` before considering any service task done.
- The GitHub Actions tag-bump commit means `workflow_run.head_sha` (original commit) ≠ ArgoCD revision (bump commit). This is expected — it's why the image_tag fallback exists.
- Prometheus `rate()` returns nothing without steady traffic — the load generator (E4-T4) must be running before health scoring can be tested.
- Grafana provisioned datasources/dashboards only load on container start — restart the Grafana container after editing provisioning YAML.
- Grafana dashboards come in **two sets** (`deploy/grafana/dashboards/`, #834): `operator/` is platform-wide (queries the `dora_*` NULL-org views, operator-only, don't add an org filter here); `customer/` is org-scoped by construction — every SQL panel filters `org_id = '$org'`, DORA panels call `dora_*('$org'::uuid)`, and `$org` is a hidden `constant` var the ingest panel proxy sets server-side from `UserContext` (the browser can't override it). Only `customer/` uids may be embedded (`grafana.py::EMBEDDABLE_DASHBOARD_UIDS`).
- `psql`/manual SQL inserts into `services`/`deployments`/`alerts`/`pipeline_events` need an explicit `org_id` since V016 dropped the column DEFAULT — a bare INSERT now fails with a NOT NULL violation.
- The `/api/prom` relay (#832) picks the org's **newest-heartbeated connected cluster** by default; a `customer/` Prometheus panel can pin one with a `cluster="$cluster"` matcher (#836). A relay timeout or a disconnected agent returns a Prometheus *error* envelope (504/502), never empty data — don't "fix" a red panel by swallowing that into a no-data state (gotcha: an empty panel once falsely scored a whole E2E run 100/healthy). Poll cadence is `QUERY_POLL_INTERVAL_SECONDS` (agent, default 3s) vs `PROM_RELAY_TIMEOUT_SECONDS` (ingest, default 20s).
- **Supabase session pooler, not direct connection or transaction pooler** (#817): the direct connection (`db.<ref>.supabase.co:5432`) is IPv6-only unless you've paid for the IPv4 add-on; the transaction-mode pooler (`:6543`) breaks asyncpg's server-side prepared statements and doesn't support `LISTEN/NOTIFY`. `DATABASE_URL` must be the session pooler (`aws-0-<region>.pooler.supabase.com:5432`).
- **Every non-`postgres` Supabase role needs `<role>.<project-ref>` as its pooler username**, not the bare role name — `grafana_ro` connects as `grafana_ro.<project-ref>`, not `grafana_ro`.
- **Never point `*_TEST_DATABASE_URL` (any of them) at Supabase** — `conftest.py` in `services/ingest/tests` refuses at collection time if one is, because their fixture teardowns run `TRUNCATE ... CASCADE` (see the E20-T3 incident this guards against).
- If `V001__base_schema.sql`'s `CREATE ROLE grafana_ro` fails against Supabase (permission denied), create the role manually in the Supabase SQL editor first — the migration's `IF NOT EXISTS` guard makes it a no-op once the role already exists.
- `deploy/docker-compose.yml`'s `depends_on: postgres: required: false` needs **Docker Compose CLI ≥ 2.20** (mid-2023) — an older Compose binary (legacy `docker-compose` v1, or a stale Docker Desktop) fails YAML validation on it and `make up`/`make up-local-db` won't start anything. Check `docker compose version` if that happens.
- The local-db profile's Grafana PostgreSQL panel doesn't work out of the box — `datasources.yml` always points at the `SUPABASE_DB_*` vars with `sslmode: require`, and the local Postgres container has no TLS listener. See `.env.example`'s Local Postgres section for the (uncommitted, local-only) workaround.
