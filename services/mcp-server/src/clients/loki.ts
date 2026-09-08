// Routed through ingest's org-scoped telemetry relay (#840) rather than a
// direct LOKI_URL — see clients/ingest-relay.ts for why, and
// cluster_agent/loki.py + run.py's "logql" kind dispatch for how a
// relayed LogQL query actually gets executed against the customer's own
// Loki.

import { relayGet, pingIngest } from "./ingest-relay.js";

export interface LokiStream {
  stream: Record<string, string>;
  values: [string, string][];
}

interface LokiResponse {
  status: string;
  data: {
    resultType: string;
    result: LokiStream[];
  };
}

export async function queryRange(
  query: string,
  start: string,
  end: string,
  orgId: string | null,
  limit = 1000,
  direction: "forward" | "backward" = "forward",
): Promise<LokiStream[]> {
  const params = new URLSearchParams({
    query,
    start,
    end,
    limit: String(limit),
    direction,
  });

  const body = await relayGet<LokiResponse>("/internal/relay/loki/query_range", params, orgId);
  if (body.status !== "success") {
    throw new Error(`Loki query error: ${JSON.stringify(body)}`);
  }
  return body.data.result;
}

export async function testConnection(): Promise<void> {
  // See prometheus.ts's testConnection for why this only confirms ingest
  // itself is reachable, not the relay end-to-end.
  await pingIngest();
  console.log("[loki] ingest relay reachable");
}
