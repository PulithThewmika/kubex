import { describe, it, expect, vi, beforeEach } from "vitest";
import { queryOne } from "../clients/postgres.js";
import { queryRange } from "../clients/loki.js";
import { buildLogQL, detectLevel, queryLogs } from "./query_logs.js";
import { sanitizeLabel } from "./query_metrics.js";
import { parseResult } from "./test-utils.js";

vi.mock("../clients/postgres.js", () => ({
  queryOne: vi.fn(),
}));

vi.mock("../clients/loki.js", () => ({
  queryRange: vi.fn(),
}));

const mockedQueryOne = vi.mocked(queryOne);
const mockedQueryRange = vi.mocked(queryRange);

beforeEach(() => {
  mockedQueryOne.mockReset();
  mockedQueryRange.mockReset();
});

describe("LogQL construction", () => {
  it("builds basic service selector", () => {
    const q = buildLogQL("orders");
    expect(q).toBe('{app="orders"}');
  });

  it("adds keyword filter", () => {
    const q = buildLogQL("orders", "timeout");
    expect(q).toBe('{app="orders"} |= "timeout"');
  });

  it("adds level filter with case-insensitive regex", () => {
    const q = buildLogQL("orders", undefined, "error");
    expect(q).toBe('{app="orders"} |~ "(?i)error"');
  });

  it("adds both level and keyword filters", () => {
    const q = buildLogQL("payments", "connection refused", "error");
    expect(q).toBe('{app="payments"} |~ "(?i)error" |= "connection refused"');
  });

  it("escapes double quotes in service name", () => {
    const q = buildLogQL('my"service');
    expect(q).toBe('{app="my\\"service"}');
  });

  it("escapes double quotes in keyword", () => {
    const q = buildLogQL("orders", 'key="value"');
    expect(q).toBe('{app="orders"} |= "key=\\"value\\""');
  });

  it("escapes backslash in service name via sanitizeLabel", () => {
    const q = buildLogQL("orders\\malicious");
    expect(q).toBe('{app="orders\\\\malicious"}');
  });
});

describe("sanitizeLabel (reused from query_metrics)", () => {
  it("escapes backslash and double quotes", () => {
    expect(sanitizeLabel('foo"bar')).toBe('foo\\"bar');
    expect(sanitizeLabel("foo\\bar")).toBe("foo\\\\bar");
  });

  it("passes clean strings through", () => {
    expect(sanitizeLabel("orders")).toBe("orders");
  });
});

describe("level detection", () => {
  it("detects error level", () => {
    expect(detectLevel("2024-01-01 ERROR connection failed")).toBe("error");
  });

  it("detects warn level", () => {
    expect(detectLevel("WARN: high latency")).toBe("warn");
  });

  it("normalizes warning to warn", () => {
    expect(detectLevel("[WARNING] disk nearly full")).toBe("warn");
  });

  it("detects info level", () => {
    expect(detectLevel("INFO server started on port 8000")).toBe("info");
  });

  it("returns unknown for unrecognized", () => {
    expect(detectLevel("just some output")).toBe("unknown");
  });

  it("detects fatal level", () => {
    expect(detectLevel("FATAL: out of memory")).toBe("fatal");
  });
});

describe("log entry formatting", () => {
  it("converts Loki nanosecond timestamps to ISO8601 with BigInt precision", () => {
    const tsNano = "1700000000000000000";
    const epochMs = Number(BigInt(tsNano) / 1_000_000n);
    const iso = new Date(epochMs).toISOString();
    expect(iso).toBe("2023-11-14T22:13:20.000Z");
  });

  it("preserves sub-second precision in nanosecond timestamps", () => {
    const tsNano = "1700000000123456789";
    const epochMs = Number(BigInt(tsNano) / 1_000_000n);
    const iso = new Date(epochMs).toISOString();
    expect(iso).toBe("2023-11-14T22:13:20.123Z");
  });

  it("caps entries at limit", () => {
    const entries = Array.from({ length: 300 }, (_, i) => ({
      ts: new Date(i * 1000).toISOString(),
      level: "info",
      line: `log line ${i}`,
    }));
    const capped = entries.slice(0, 200);
    expect(capped).toHaveLength(200);
  });
});


describe("queryLogs org scoping (#840/H5)", () => {
  it("resolves the service against Postgres with the caller's org filter before querying Loki", async () => {
    mockedQueryOne.mockResolvedValue({ name: "orders", namespace: "kubex" });
    mockedQueryRange.mockResolvedValue([]);

    await queryLogs({ service: "orders", from: "-1h", limit: 50 }, "org-a");

    const [sql, params] = mockedQueryOne.mock.calls[0];
    expect(sql).toContain("org_id = $2");
    expect(params).toEqual(["orders", "org-a"]);
  });

  it("never calls Loki for a service that does not belong to the caller's org", async () => {
    // Postgres finds nothing because the org filter excludes org B's
    // service — this is the regression test for the original gap, where
    // queryLogs built {app="<raw input>"} and queried Loki directly with
    // no org check at all.
    mockedQueryOne.mockResolvedValue(null);

    const result = await queryLogs({ service: "org-b-service", from: "-1h", limit: 50 }, "org-a");
    const parsed = parseResult(result);

    expect(parsed.error).toContain("not found");
    expect(mockedQueryRange).not.toHaveBeenCalled();
  });

  it("passes orgId=null through unfiltered for the stdio/admin transport", async () => {
    mockedQueryOne.mockResolvedValue({ name: "orders", namespace: "kubex" });
    mockedQueryRange.mockResolvedValue([]);

    await queryLogs({ service: "orders", from: "-1h", limit: 50 }, null);

    const [sql, params] = mockedQueryOne.mock.calls[0];
    expect(sql).not.toContain("org_id");
    expect(params).toEqual(["orders"]);
  });

  it("builds LogQL from the resolved service name, not the raw input", async () => {
    mockedQueryOne.mockResolvedValue({ name: "orders", namespace: "kubex" });
    mockedQueryRange.mockResolvedValue([]);

    const result = await queryLogs({ service: "orders", from: "-1h", limit: 50 }, "org-a");
    const parsed = parseResult(result);

    expect(parsed.logql).toBe('{app="orders"}');
  });
});
