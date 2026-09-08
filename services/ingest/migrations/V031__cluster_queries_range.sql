-- V031: cluster_queries — carry range-query params (#832).
--
-- The PromQL relay (V024) only carried an instant-query string. Grafana's
-- Prometheus datasource also issues /api/v1/query_range (query + start +
-- end + step) for every time-series panel. Add a `kind` discriminator and
-- a `params` JSONB so the agent knows which Prometheus endpoint to hit.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V031') THEN
        RAISE NOTICE 'V031 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE cluster_queries
        ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'instant'
            CHECK (kind IN ('instant', 'range'));
    ALTER TABLE cluster_queries
        ADD COLUMN IF NOT EXISTS params JSONB;

    INSERT INTO schema_versions (version, description)
    VALUES ('V031', 'cluster_queries.kind + params for range queries');
END $$;
