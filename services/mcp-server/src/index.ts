import { createServer, type IncomingMessage, type ServerResponse } from "node:http";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

import * as postgres from "./clients/postgres.js";
import * as prometheus from "./clients/prometheus.js";
import * as loki from "./clients/loki.js";
import { UUID_RE, isValidBearerToken } from "./http-auth.js";
import {
  listDeploymentsSchema,
  listDeployments,
} from "./tools/list_deployments.js";
import {
  getDeploymentSchema,
  getDeployment,
} from "./tools/get_deployment.js";
import {
  getDeployHealthSchema,
  getDeployHealth,
} from "./tools/get_deploy_health.js";
import {
  compareDeploysSchema,
  compareDeploys,
} from "./tools/compare_deploys.js";
import {
  queryMetricsSchema,
  queryMetrics,
} from "./tools/query_metrics.js";
import {
  queryLogsSchema,
  queryLogs,
} from "./tools/query_logs.js";
import {
  getDoraMetricsSchema,
  getDoraMetrics,
} from "./tools/get_dora_metrics.js";
import {
  getActiveAlertsSchema,
  getActiveAlerts,
} from "./tools/get_active_alerts.js";
import {
  getSafetyScoreSchema,
  getSafetyScore,
} from "./tools/get_safety_score.js";
import {
  generateIncidentReportSchema,
  generateIncidentReport,
} from "./tools/generate_incident_report.js";
import {
  getBlastRadiusSchema,
  getBlastRadius,
} from "./tools/get_blast_radius.js";
import { wrapTool } from "./tools/wrap-tool.js";

const TOOL_COUNT = 11;

// A fresh McpServer per connection — see createMcpServer() call sites below
// for why this is a factory rather than a module-level singleton.
//
// orgId scopes every tool's Postgres queries to one organization: null means
// no filter, which is the deliberate behavior for the stdio transport (see
// its call site in main() below) — everything else must pass a real org_id.
function createMcpServer(orgId: string | null): McpServer {
  const server = new McpServer({
    name: "kubex",
    version: "0.1.0",
  });

  // ── Tool: list_deployments ────────────────────────────────────
  server.tool(
    "list_deployments",
    "List recent deployments, optionally filtered by service name or status. Returns a summary highlighting any unhealthy deploys.",
    listDeploymentsSchema,
    wrapTool("list_deployments", (input) => listDeployments(input, orgId)),
  );

  // ── Tool: get_deployment ───────────────────────────────────────
  server.tool(
    "get_deployment",
    "Get full details of a specific deployment by ID, including service info, pipeline timeline, and health assessment",
    getDeploymentSchema,
    wrapTool("get_deployment", (input) => getDeployment(input, orgId)),
  );

  // ── Tool: get_deploy_health ────────────────────────────────────
  server.tool(
    "get_deploy_health",
    "Get the health assessment for a deployment with score breakdown and metric evidence (error rate, latency, restarts)",
    getDeployHealthSchema,
    wrapTool("get_deploy_health", (input) => getDeployHealth(input, orgId)),
  );

  // ── Tool: compare_deploys ──────────────────────────────────────
  server.tool(
    "compare_deploys",
    "Compare two deployments side by side — status, health score, and live Prometheus metrics (error rate, p99 latency, restarts) with change percentages",
    compareDeploysSchema,
    wrapTool("compare_deploys", (input) => compareDeploys(input, orgId)),
  );

  // ── Tool: query_metrics ────────────────────────────────────────
  server.tool(
    "query_metrics",
    "Query Prometheus metrics for a service by intent (metric enum), not raw PromQL. Returns time series, unit, the actual PromQL executed, and a human-readable summary.",
    queryMetricsSchema,
    wrapTool("query_metrics", (input) => queryMetrics(input, orgId)),
  );

  // ── Tool: query_logs ───────────────────────────────────────────
  // No org filter: query_logs never touches Postgres — it reads Loki by
  // service name label only, and Loki has no org concept.
  server.tool(
    "query_logs",
    "Query application logs from Loki by service name with optional keyword and log-level filters. Returns timestamped log lines, the LogQL query executed, and a summary with level breakdown.",
    queryLogsSchema,
    wrapTool("query_logs", queryLogs),
  );

  // ── Tool: get_dora_metrics ─────────────────────────────────────
  server.tool(
    "get_dora_metrics",
    "Get DORA metrics (deploy frequency, lead time, change failure rate, MTTR) aggregated over a configurable period. Reads from the authoritative SQL views.",
    getDoraMetricsSchema,
    wrapTool("get_dora_metrics", (input) => getDoraMetrics(input, orgId)),
  );

  // ── Tool: get_active_alerts ────────────────────────────────────
  server.tool(
    "get_active_alerts",
    "Get currently active (unresolved) alerts with deployment linkage, optionally filtered by service or severity.",
    getActiveAlertsSchema,
    wrapTool("get_active_alerts", (input) => getActiveAlerts(input, orgId)),
  );

  // ── Tool: get_safety_score ──────────────────────────────────────
  server.tool(
    "get_safety_score",
    "Get the pre-deploy safety score (0-100, rule-based, not ML) for a deployment with its risk factor breakdown (change-failure-rate, files changed, day/time, cluster load, last deploy health).",
    getSafetyScoreSchema,
    wrapTool("get_safety_score", (input) => getSafetyScore(input, orgId)),
  );

  // ── Tool: generate_incident_report ──────────────────────────────
  server.tool(
    "generate_incident_report",
    "Generate a chronological markdown incident report for an alert — deployment details, metric timeline, error logs, and alert metadata, assembled directly from Postgres, Prometheus, and Loki. Useful as-is for pasting into an incident channel.",
    generateIncidentReportSchema,
    wrapTool("generate_incident_report", (input) => generateIncidentReport(input, orgId)),
  );

  // ── Tool: get_blast_radius ────────────────────────────────────────
  server.tool(
    "get_blast_radius",
    "Get the downstream services/components that depend on a given service or component (discovered from Kubernetes Service/Deployment config, e.g. 'orders calls payments'), each with its current deployment health status — useful for assessing what else might be affected if a service degrades.",
    getBlastRadiusSchema,
    wrapTool("get_blast_radius", (input) => getBlastRadius(input, orgId)),
  );

  return server;
}

async function main(): Promise<void> {
  await postgres.testConnection();
  try {
    await prometheus.testConnection();
  } catch (err) {
    console.warn("[prometheus] not reachable — tools needing it will degrade at call time:", (err as Error).message);
  }
  try {
    await loki.testConnection();
  } catch (err) {
    console.warn("[loki] not reachable — tools needing it will degrade at call time:", (err as Error).message);
  }

  console.log(`MCP server ready, ${TOOL_COUNT} tools registered`);

  if (process.env.MCP_TRANSPORT === "http") {
    // Streamable HTTP transport: lets the ingest service (a separate
    // container with no shared process/stdio) reach this server over
    // the docker-compose network.
    //
    // Each request gets its own McpServer + StreamableHTTPServerTransport
    // pair, created and torn down on the spot. This is NOT an
    // optimization — it's required. The SDK's Protocol.connect() throws
    // "Already connected to a transport" if the same Server instance is
    // reused across connections, and even a fresh transport reused
    // across requests rejects a second `initialize` call in stateless
    // mode (sessionIdGenerator: undefined). Tool registration is pure
    // (no I/O — the Postgres/Prometheus/Loki clients are separate
    // pooled-connection modules imported once above), so a new
    // McpServer per request is cheap.
    const port = Number(process.env.MCP_HTTP_PORT ?? 3001);
    const internalToken = process.env.MCP_INTERNAL_TOKEN;
    if (!internalToken) {
      throw new Error("MCP_INTERNAL_TOKEN is required when MCP_TRANSPORT=http");
    }
    const httpServer = createServer(
      (req: IncomingMessage, res: ServerResponse) => {
        if (req.url !== "/mcp") {
          res.writeHead(404).end();
          return;
        }

        // Shared bearer token, same pattern as the ArgoCD/Alertmanager
        // webhook checks in services/ingest/app/auth.py — this is the only
        // caller ingest's mcp_client.py authenticates itself with before
        // this server trusts the X-Org-Id header below. Without this, any
        // container on the compose network could forge X-Org-Id and read
        // another org's data (this container has no published port, but
        // that alone isn't caller authentication).
        if (!isValidBearerToken(req.headers.authorization, internalToken)) {
          res.writeHead(401, { "Content-Type": "application/json" })
            .end(JSON.stringify({ error: "Missing or invalid Authorization bearer token" }));
          return;
        }

        // X-Org-Id is set by every caller over this transport — see
        // services/ingest/app/mcp_client.py's mcp_session(). Required (not
        // defaulted to null) because HTTP is how ingest's chat proxy reaches
        // this server on behalf of a real authenticated user; a request with
        // no org context here is a bug in the caller, not a legitimate
        // platform-wide query (that's what the stdio path below is for).
        // ingest only ever sets it from the JWT-verified user.org_id in
        // chat_engine.py, never from client-supplied input.
        const orgIdHeader = req.headers["x-org-id"];
        const orgId = Array.isArray(orgIdHeader) ? orgIdHeader[0] : orgIdHeader;
        if (!orgId) {
          res.writeHead(400, { "Content-Type": "application/json" })
            .end(JSON.stringify({ error: "Missing required X-Org-Id header" }));
          return;
        }
        // Node joins a repeated non-list header ("X-Org-Id: a" twice) into
        // one comma-separated string, which would otherwise pass the
        // truthiness check above and only fail later as an opaque Postgres
        // UUID-cast error. Validate the shape here so a malformed or
        // duplicated header gets a clean 400 instead.
        if (!UUID_RE.test(orgId)) {
          res.writeHead(400, { "Content-Type": "application/json" })
            .end(JSON.stringify({ error: "X-Org-Id must be a single UUID" }));
          return;
        }

        const transport = new StreamableHTTPServerTransport({
          sessionIdGenerator: undefined,
        });
        const server = createMcpServer(orgId);
        server
          .connect(transport)
          .then(() => transport.handleRequest(req, res))
          .catch((err) => {
            console.error("Error handling MCP request:", err);
            if (!res.headersSent) {
              res.writeHead(500).end();
            }
          })
          .finally(() => {
            transport.close();
            server.close();
          });
      },
    );
    httpServer.listen(port, () => {
      console.log(`MCP server listening on http://0.0.0.0:${port}/mcp`);
    });
  } else {
    // Stdio transport: local/CLI usage (see mcp_client.py's docstring) with
    // no HTTP request to read an org header from, and no other session
    // context to derive one from either. Decision: treat it as a trusted
    // local-admin tool and pass orgId=null (no filter, same as the Grafana
    // dashboards' NULL-org queries) rather than inventing an env var for a
    // single org — this transport isn't reachable from the multi-tenant
    // chat proxy at all, only from a developer's own terminal.
    // ponytail: platform-wide, no per-org stdio mode; upgrade to an
    // MCP_STDIO_ORG_ID env var if a non-admin CLI user ever needs this
    // transport scoped to one org.
    const server = createMcpServer(null);
    const transport = new StdioServerTransport();
    await server.connect(transport);
  }
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
