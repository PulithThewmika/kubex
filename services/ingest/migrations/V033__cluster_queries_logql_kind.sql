-- V033: cluster_queries — allow 'logql' as a relay query kind (#840).
--
-- V031 (#831/#832) already added `kind`/`params` so Grafana's PromQL
-- range queries can be relayed. This widens that same CHECK to also
-- allow 'logql', so the cluster-agent's query relay can carry Loki log
-- queries alongside Prometheus ones (see cluster_agent's
-- _query_relay_tick dispatch and app/routers/relay_internal.py's
-- loki_range_query).
--
-- Also creates `kind`/`params` itself if somehow missing (matching
-- V031's exact shape) rather than assuming V031 ran first — kept from
-- an earlier revision of this migration, harmless now that V031 has
-- landed, and cheap insurance against migration order drift.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V033') THEN
        RAISE NOTICE 'V033 already applied, skipping.';
        RETURN;
    END IF;

    -- Same shape as V031's ADD COLUMN — a no-op if V031 already ran.
    ALTER TABLE cluster_queries ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'instant';
    ALTER TABLE cluster_queries ADD COLUMN IF NOT EXISTS params JSONB;

    ALTER TABLE cluster_queries DROP CONSTRAINT IF EXISTS cluster_queries_kind_check;
    ALTER TABLE cluster_queries
        ADD CONSTRAINT cluster_queries_kind_check CHECK (kind IN ('instant', 'range', 'logql'));

    INSERT INTO schema_versions (version, description)
    VALUES ('V033', 'cluster_queries.kind/params, widened to allow logql for the Loki relay (#840)');
END $$;
