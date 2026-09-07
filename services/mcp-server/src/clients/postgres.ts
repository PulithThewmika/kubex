import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const SUPABASE_HOST_SUFFIXES = [".supabase.co", ".supabase.com"];

const rawDatabaseUrl = process.env.DATABASE_URL ?? "";
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Node's URL does NOT lowercase the hostname for non-"special" schemes
// like postgres:/postgresql: (only http/https/ws/wss/ftp/file get that
// normalization) — lowercase it ourselves before comparing, and check
// an actual hostname suffix rather than a raw "supabase" in url
// substring (case-sensitive, and could match a password or path segment
// that isn't the host).
let parsedUrl: URL | null = null;
try {
  parsedUrl = new URL(rawDatabaseUrl);
} catch {
  // Malformed URL — treated as non-Supabase below; pg.Pool will surface
  // a clear connection error rather than this silently swallowing it.
}
const isSupabase = parsedUrl !== null
  && SUPABASE_HOST_SUFFIXES.some((suffix) => parsedUrl!.hostname.toLowerCase().endsWith(suffix));

// Supabase signs its pooler certs with its own private CA, not a public
// one node's default trust store recognizes — load it explicitly rather
// than disabling verification. The local-dev compose Postgres
// (--profile local-db) has no TLS listener, hence the conditional.
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
if (isSupabase && parsedUrl) {
  for (const key of ["sslmode", "ssl", "sslrootcert", "sslcert", "sslkey"]) {
    parsedUrl.searchParams.delete(key);
  }
  databaseUrl = parsedUrl.toString();
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
