import { z } from "zod";
import { queryRange, type LokiStream } from "../clients/loki.js";
import { resolveTimestamp, resolveService } from "./query_metrics.js";

const LOG_LEVELS = [
  "error", "warn", "info", "debug", "trace", "fatal", "panic",
] as const;

export const queryLogsSchema = {
  service: z.string().describe("Service name (matches the 'app' label in Loki)"),
  keyword: z
    .string()
    .optional()
    .describe("Optional keyword to filter log lines (case-sensitive substring match)"),
  level: z
    .enum(LOG_LEVELS)
    .optional()
    .describe("Optional log level filter (case-insensitive match)"),
  from: z
    .string()
    .describe("Start time — relative (e.g. '-1h', '-30m') or ISO8601 timestamp"),
  to: z
    .string()
    .optional()
    .describe("End time — relative or ISO8601 (default: 'now')"),
  limit: z
    .number()
    .int()
    .min(1)
    .max(200)
    .default(50)
    .describe("Max log lines to return (default 50, max 200)"),
};

// ── LogQL construction ─────────────────────────────────────────

// Mirrors query_metrics.ts's sanitizeLabel — same escaping rule (LogQL
// label matchers use the same quoting as PromQL's).
function sanitizeLabel(value: string): string {
  return value.replace(/[\\"\n\r]/g, (m) => "\\" + m);
}

export function buildLogQL(
  service: string,
  keyword?: string,
  level?: string,
): string {
  const svc = sanitizeLabel(service);
  let query = `{app="${svc}"}`;

  if (level) {
    query += ` |~ "(?i)${level}"`;
  }

  if (keyword) {
    const kw = sanitizeLabel(keyword);
    query += ` |= "${kw}"`;
  }

  return query;
}

// ── Log line parsing ───────────────────────────────────────────

interface LogEntry {
  ts: string;
  level: string;
  line: string;
}

const LEVEL_RE = /\b(error|warn(?:ing)?|info|debug|trace|fatal|panic)\b/i;

export function detectLevel(line: string): string {
  const match = line.match(LEVEL_RE);
  if (!match) return "unknown";
  const lvl = match[1].toLowerCase();
  if (lvl === "warning") return "warn";
  return lvl;
}

function formatResults(streams: LokiStream[], limit: number): LogEntry[] {
  const entries: LogEntry[] = [];

  for (const stream of streams) {
    for (const [tsNano, line] of stream.values) {
      const epochMs = Number(BigInt(tsNano) / 1_000_000n);
      entries.push({
        ts: new Date(epochMs).toISOString(),
        level: detectLevel(line),
        line,
      });
    }
  }

  entries.sort((a, b) => a.ts.localeCompare(b.ts));

  return entries.slice(0, limit);
}

// ── Summary builder ────────────────────────────────────────────

function buildSummary(
  service: string,
  entries: LogEntry[],
  fromStr: string,
  toStr: string,
  keyword?: string,
  level?: string,
): string {
  if (entries.length === 0) {
    const filters = [
      level ? `level=${level}` : null,
      keyword ? `keyword="${keyword}"` : null,
    ].filter(Boolean).join(", ");
    const suffix = filters ? ` (filters: ${filters})` : "";
    return `No logs found for ${service} from ${fromStr} to ${toStr}${suffix}`;
  }

  const levelCounts = new Map<string, number>();
  for (const e of entries) {
    levelCounts.set(e.level, (levelCounts.get(e.level) ?? 0) + 1);
  }

  const breakdown = Array.from(levelCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([lvl, count]) => `${count} ${lvl}`)
    .join(", ");

  const prefix = level
    ? `Found ${entries.length} ${level}-level log(s)`
    : `Found ${entries.length} log(s)`;

  return `${prefix} for ${service} (${breakdown}) from ${fromStr} to ${toStr}`;
}

// ── Main handler ───────────────────────────────────────────────

export async function queryLogs(input: {
  service: string;
  keyword?: string;
  level?: string;
  from: string;
  to?: string;
  limit: number;
}, orgId: string | null): Promise<{ content: { type: "text"; text: string }[] }> {
  // Resolve against Postgres with the caller's org filter BEFORE building
  // any LogQL — bug fix (#840/H5): this tool used to build {app="<raw
  // input>"} straight from the client-supplied service name with no check
  // that the service belongs to the caller's org, unlike query_metrics
  // (which already resolves through Postgres first). A user in org A could
  // read org B's logs by naming org B's service. Loki itself has no org
  // concept, so this Postgres lookup is the only place that check can
  // happen — matching query_metrics.ts's resolveService pattern exactly.
  const svc = await resolveService(input.service, orgId);
  if (!svc) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          error: `Service "${input.service}" not found`,
          summary: `query_logs failed: service "${input.service}" not found`,
        }),
      }],
    };
  }

  const nowEpoch = Date.now() / 1000;
  const fromStr = input.from;
  const toStr = input.to ?? "now";

  let startEpoch: number;
  let endEpoch: number;
  try {
    startEpoch = parseFloat(resolveTimestamp(fromStr, nowEpoch));
    endEpoch = parseFloat(resolveTimestamp(toStr, nowEpoch));
  } catch (err) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          error: `Invalid time: ${err instanceof Error ? err.message : String(err)}`,
          summary: `query_logs failed: invalid time parameter`,
        }),
      }],
    };
  }

  if (startEpoch >= endEpoch) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({ error: "'from' must be before 'to'", summary: "query_logs failed: 'from' must be before 'to'" }),
      }],
    };
  }

  const logql = buildLogQL(svc.name, input.keyword, input.level);
  const limit = Math.min(input.limit, 200);

  let streams: LokiStream[];
  try {
    streams = await queryRange(
      logql,
      startEpoch.toString(),
      endEpoch.toString(),
      orgId,
      limit,
    );
  } catch (err) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          error: `Loki query failed: ${err instanceof Error ? err.message : String(err)}`,
          summary: `Could not query logs for ${input.service} — Loki unreachable or query error`,
        }),
      }],
    };
  }

  const entries = formatResults(streams, limit);
  const summary = buildSummary(
    input.service, entries, fromStr, toStr, input.keyword, input.level,
  );

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        summary,
        service: input.service,
        logql,
        from: fromStr,
        to: toStr,
        count: entries.length,
        logs: entries,
      }),
    }],
  };
}
