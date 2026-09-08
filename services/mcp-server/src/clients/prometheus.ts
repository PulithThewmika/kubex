// Routed through ingest's org-scoped telemetry relay (#840) rather than a
// direct PROM_URL — see clients/ingest-relay.ts for why. Exported function
// signatures are unchanged except for the added `orgId` parameter, so
// query_metrics.ts/compare_deploys.ts/generate_incident_report.ts only
// need to thread orgId through, not change their import shape.

import { relayGet, pingIngest } from "./ingest-relay.js";

export interface PromInstantResult {
  metric: Record<string, string>;
  value: [number, string];
}

export interface PromRangeResult {
  metric: Record<string, string>;
  values: [number, string][];
}

interface PromResponse<T> {
  status: string;
  data: {
    resultType: string;
    result: T[];
  };
}

export async function instantQuery(
  query: string,
  time: string | undefined,
  orgId: string | null,
): Promise<PromInstantResult[]> {
  const params = new URLSearchParams({ query });
  if (time) params.set("time", time);

  const body = await relayGet<PromResponse<PromInstantResult>>(
    "/internal/relay/prometheus/query",
    params,
    orgId,
  );
  if (body.status !== "success") {
    throw new Error(`Prometheus query error: ${JSON.stringify(body)}`);
  }
  return body.data.result;
}

export async function rangeQuery(
  query: string,
  start: string,
  end: string,
  step: string,
  orgId: string | null,
): Promise<PromRangeResult[]> {
  const params = new URLSearchParams({ query, start, end, step });

  const body = await relayGet<PromResponse<PromRangeResult>>(
    "/internal/relay/prometheus/query_range",
    params,
    orgId,
  );
  if (body.status !== "success") {
    throw new Error(`Prometheus range query error: ${JSON.stringify(body)}`);
  }
  return body.data.result;
}

export async function testConnection(): Promise<void> {
  // Confirms ingest itself is reachable at boot. It does NOT confirm the
  // relay end-to-end (that needs a real org_id + a connected cluster,
  // neither of which exist at server startup) — call sites still need to
  // handle a relay failure at request time, same as before.
  await pingIngest();
  console.log("[prometheus] ingest relay reachable");
}
