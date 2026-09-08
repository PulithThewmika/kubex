// Shared HTTP client for ingest's org-scoped telemetry relay (#840).
//
// Both prometheus.ts and loki.ts route through this rather than
// connecting to a Prometheus/Loki directly — a customer's metrics only
// ever exist behind their own cluster-agent relay (EPIC-022), reached via
// ingest's /internal/relay/* endpoints, never via a PROM_URL/LOKI_URL this
// container could reach on its own.
//
// Auth mirrors the pattern this codebase already uses for the reverse
// direction (ingest -> this server, see index.ts's isValidBearerToken
// check): one shared MCP_INTERNAL_TOKEN, since without it any container
// on the compose network could pass an arbitrary org_id.

const INGEST_URL = process.env.INGEST_URL ?? "http://ingest:8000";
const INTERNAL_TOKEN = process.env.MCP_INTERNAL_TOKEN;

export class RelayError extends Error {
  constructor(
    message: string,
    public readonly errorType: string,
    public readonly statusCode: number,
  ) {
    super(message);
    this.name = "RelayError";
  }
}

// The relay needs a real org_id to resolve which customer cluster to ask
// — there's no "platform-wide" cluster. The stdio/admin transport passes
// orgId=null (see index.ts's own comment on that transport), which has no
// cluster to resolve against, so this fails fast and explicitly rather
// than silently returning an empty result a caller could misread as "no
// data" instead of "not supported over this transport".
function requireOrgId(orgId: string | null): string {
  if (orgId === null) {
    throw new Error(
      "Metrics/logs are unavailable over the stdio (no-org) transport — the relay needs a real org_id to resolve a connected cluster",
    );
  }
  return orgId;
}

export async function relayGet<T>(path: string, params: URLSearchParams, orgId: string | null): Promise<T> {
  const org = requireOrgId(orgId);
  if (!INTERNAL_TOKEN) {
    throw new Error("MCP_INTERNAL_TOKEN is not set — cannot call the ingest relay");
  }
  params.set("org_id", org);

  const url = `${INGEST_URL}${path}?${params}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${INTERNAL_TOKEN}` },
  });

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new Error(`Relay request failed: ${res.status} ${res.statusText}`);
  }

  if (!res.ok) {
    const errBody = body as { errorType?: string; error?: string };
    throw new RelayError(
      errBody.error ?? `Relay request failed: ${res.status}`,
      errBody.errorType ?? "unknown",
      res.status,
    );
  }

  return body as T;
}

export async function pingIngest(): Promise<void> {
  const res = await fetch(`${INGEST_URL}/healthz`);
  if (!res.ok) {
    throw new Error(`ingest unreachable: ${res.status}`);
  }
}
