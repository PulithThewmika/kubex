// Cross-org isolation for the MCP layer — the acceptance test for E20-T3
// sub-issue #610 (and the MCP half of EPIC-020's "Cross-org data isolation
// verified with tests" criterion).
//
// Runs against a real Postgres (the same lesson as
// services/ingest/tests/test_org_isolation.py: mocks can't catch a missing
// WHERE org_id = ... clause). Uses whatever DATABASE_URL already points at
// — the live kubex-postgres in local dev, or CI's Postgres service — rather
// than spinning up a disposable container, since this service has no
// existing testcontainers dependency and the schema is already applied
// there. Seeds two real orgs/services/deployments with unique names so it
// can run safely against a database with existing data, and cleans up
// everything it inserted.
import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { query, queryOne, shutdown } from "../clients/postgres.js";
import { listDeployments } from "./list_deployments.js";
import { parseResult } from "./test-utils.js";

const DATABASE_URL = process.env.DATABASE_URL;

describe.skipIf(!DATABASE_URL)("list_deployments cross-org isolation (real Postgres)", () => {
  let orgA: { id: string; serviceId: number; deploymentId: number };
  let orgB: { id: string; serviceId: number; deploymentId: number };

  async function seedOrg(label: string) {
    const suffix = randomUUID().slice(0, 8);
    const org = await queryOne<{ id: string }>(
      `INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id`,
      [`${label}-${suffix}`, `${label}-${suffix}`],
    );
    const service = await queryOne<{ id: number }>(
      `INSERT INTO services (org_id, name, repo) VALUES ($1, $2, $3) RETURNING id`,
      [org!.id, `${label}-service-${suffix}`, `acme/${label}-${suffix}`],
    );
    const deployment = await queryOne<{ id: number }>(
      `INSERT INTO deployments (org_id, service_id, commit_sha, status, finished_at)
       VALUES ($1, $2, $3, 'deployed', now()) RETURNING id`,
      [org!.id, service!.id, `${suffix}sha`],
    );
    return { id: org!.id, serviceId: service!.id, deploymentId: deployment!.id };
  }

  beforeAll(async () => {
    orgA = await seedOrg("org-a-mcp");
    orgB = await seedOrg("org-b-mcp");
  });

  afterAll(async () => {
    for (const org of [orgA, orgB]) {
      await query(`DELETE FROM deployments WHERE id = $1`, [org.deploymentId]);
      await query(`DELETE FROM services WHERE id = $1`, [org.serviceId]);
      await query(`DELETE FROM organizations WHERE id = $1`, [org.id]);
    }
    await shutdown();
  });

  it("returns only org A's deployment when called with org A's id", async () => {
    const result = await listDeployments({ limit: 50 }, orgA.id);
    const parsed = parseResult(result);
    const ids = parsed.deployments.map((d: { id: number }) => d.id);

    expect(ids).toContain(orgA.deploymentId);
    expect(ids).not.toContain(orgB.deploymentId);
  });

  it("returns only org B's deployment when called with org B's id", async () => {
    const result = await listDeployments({ limit: 50 }, orgB.id);
    const parsed = parseResult(result);
    const ids = parsed.deployments.map((d: { id: number }) => d.id);

    expect(ids).toContain(orgB.deploymentId);
    expect(ids).not.toContain(orgA.deploymentId);
  });

  it("returns both orgs' deployments when called with orgId=null (stdio/admin mode)", async () => {
    const result = await listDeployments({ limit: 50 }, null);
    const parsed = parseResult(result);
    const ids = parsed.deployments.map((d: { id: number }) => d.id);

    expect(ids).toContain(orgA.deploymentId);
    expect(ids).toContain(orgB.deploymentId);
  });
});
