# KubeX
Deployment-aware observability platform — correlates GitHub Actions, ArgoCD, and Kubernetes health per deployment, scores every release autonomously, and exposes the full surface through an MCP interface.

## Development

All common workflow commands are wrapped in the top-level `Makefile`. Run `make help` to see the full list.

### Cluster (Kind)

| Target | What it does |
|---|---|
| `make cluster-up` | Create the Kind cluster from `deploy/kind-config.yaml` |
| `make cluster-down` | Delete the Kind cluster |
| `make cluster-status` | Show cluster info and node list |

### Database (Supabase)

The platform database is a managed Supabase Postgres instance, not a container — see `.env.example`'s Supabase section for what to fill in and where each value comes from in the Supabase dashboard. `DATABASE_URL` must be the **session pooler** connection string (Settings → Database → Connection string → "Session pooler" tab), not "Direct connection" or "Transaction pooler".

Offline/no-Supabase dev is still possible via an opt-in local Postgres container — see `make up-local-db` below.

### Central Platform (docker-compose)

| Target | What it does |
|---|---|
| `make up` | Start the compose stack (ingest, agent, mcp-server, grafana) — connects to Supabase via `DATABASE_URL` |
| `make up-local-db` | Same, plus the opt-in local Postgres container (`--profile local-db`) for offline dev |
| `make down` | Stop the compose stack |
| `make logs` | Tail docker-compose logs |
| `make db-shell` | Open `psql` into `DATABASE_URL` (Supabase by default) |
| `make db-shell-local` | Open `psql` into the local-db profile container instead |
| `make migrate` | Run SQL migrations against `DATABASE_URL` (Supabase by default) |
| `make migrate-local` | Run SQL migrations against the local-db profile container instead |

### Cluster Port-Forwards

Prometheus, Loki, and Alertmanager run in-cluster but are consumed by services outside the cluster (Grafana, ingest, detection agent). Port-forwards bridge them to the host.

| Target | What it does |
|---|---|
| `make forwards` | Start background port-forwards (Prometheus 9090, Loki 3100, Alertmanager 9093). PIDs tracked in `.pids/` |
| `make forwards-stop` | Kill tracked port-forward processes |
| `make argocd-forward` | Port-forward ArgoCD UI to `localhost:8443` (foreground) |

### GitHub Webhook Tunnel

The ingest service runs locally but needs to receive `workflow_run` events from GitHub. An ngrok tunnel exposes it.

| Target | What it does |
|---|---|
| `make tunnel` | Start ngrok on port 8000 (foreground) |
| `make webhook-update` | Read the active ngrok URL and patch the GitHub repo webhook to point at it |

Typical session flow: `make tunnel` in one terminal, then `make webhook-update` in another once ngrok is up.
