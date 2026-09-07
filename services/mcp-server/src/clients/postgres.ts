import pg from "pg";

const databaseUrl = process.env.DATABASE_URL ?? "";
// Supabase requires TLS; its pooler cert chain isn't always in node's
// default trust store, so don't rely on the URL alone to negotiate it.
// The local-dev compose Postgres (--profile local-db) has no TLS listener.
const ssl = databaseUrl.includes("supabase") ? { rejectUnauthorized: false } : undefined;

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
