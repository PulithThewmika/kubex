import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const rawDatabaseUrl = process.env.DATABASE_URL ?? "";
// Supabase signs its pooler certs with its own private CA, not a public
// one node's default trust store recognizes — load it explicitly rather
// than disabling verification. The local-dev compose Postgres
// (--profile local-db) has no TLS listener, hence the conditional.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isSupabase = rawDatabaseUrl.includes("supabase");
const ssl = isSupabase
  ? {
      ca: fs.readFileSync(path.join(__dirname, "..", "..", "certs", "supabase-root-2021-ca.pem"), "utf8"),
      rejectUnauthorized: true,
    }
  : undefined;

// pg's connectionString parsing pulls its own ssl config out of a
// sslmode= query param and REPLACES the explicit `ssl` option above
// entirely (verified live against pg 8.13.1) rather than merging with
// or deferring to it — silently discarding the Supabase CA if a
// dashboard-copied connection string happens to include one. Strip any
// ssl-related query params so the explicit `ssl` option above always wins.
let databaseUrl = rawDatabaseUrl;
if (isSupabase) {
  try {
    const parsed = new URL(rawDatabaseUrl);
    for (const key of ["sslmode", "ssl", "sslrootcert", "sslcert", "sslkey"]) {
      parsed.searchParams.delete(key);
    }
    databaseUrl = parsed.toString();
  } catch {
    // Malformed URL — leave it as-is; pg.Pool will surface a clear
    // connection error rather than this silently swallowing it.
  }
}

const pool = new pg.Pool({
  connectionString: databaseUrl,
  max: 10,
  ssl,
});

export async function query<T extends pg.QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<T[]> {
  const result = await pool.query<T>(text, params);
  return result.rows;
}

export async function queryOne<T extends pg.QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows[0] ?? null;
}

export async function testConnection(): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query("SELECT 1");
    console.log("[postgres] connection verified");
  } finally {
    client.release();
  }
}

export async function shutdown(): Promise<void> {
  await pool.end();
}
