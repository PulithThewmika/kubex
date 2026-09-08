-- V032: cluster_queries — allow 'logql' as a relay query kind (#840).
--
-- Landed concurrently with V031 (#831/#832, which adds `kind`/`params` so
-- Grafana's PromQL range queries can be relayed) on a separate branch, so
-- this migration cannot assume V031 has already run — CI on this branch
-- applies migrations against a database that has never seen V031, and a
-- hard dependency here (as an earlier revision of this file had) fails
-- that run outright. Instead this creates `kind`/`params` itself if
-- missing (matching V031's exact shape) and widens the CHECK to also
-- allow 'logql' either way, so the cluster-agent's query relay can carry
-- Loki log queries alongside Prometheus ones (see cluster_agent's
-- _query_relay_tick dispatch and app/routers/relay_internal.py's
-- loki_range_query) regardless of whether V031 lands before or after
-- this one.
--
-- Idempotent — safe to run multiple times, and safe in either merge
-- order relative to V031.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V032') THEN
        RAISE NOTICE 'V032 already applied, skipping.';
        RETURN;
    END IF;

    -- Same shape as V031's ADD COLUMN — a no-op if V031 already ran.
    ALTER TABLE cluster_queries ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'instant';
    ALTER TABLE cluster_queries ADD COLUMN IF NOT EXISTS params JSONB;

    ALTER TABLE cluster_queries DROP CONSTRAINT IF EXISTS cluster_queries_kind_check;
    ALTER TABLE cluster_queries
        ADD CONSTRAINT cluster_queries_kind_check CHECK (kind IN ('instant', 'range', 'logql'));

    INSERT INTO schema_versions (version, description)
    VALUES ('V032', 'cluster_queries.kind/params, widened to allow logql for the Loki relay (#840)');
END $$;
