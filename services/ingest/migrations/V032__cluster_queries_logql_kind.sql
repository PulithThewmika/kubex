-- V032: cluster_queries — allow 'logql' as a relay query kind (#840).
--
-- Depends on V031 (#832), which added the `kind` column (CHECK IN
-- ('instant', 'range')) so Grafana's PromQL range queries could be
-- relayed. This migration widens that same CHECK to also allow 'logql',
-- so the cluster-agent's query relay can carry Loki log queries alongside
-- Prometheus ones (see cluster_agent's _query_relay_tick dispatch and
-- app/routers/relay_internal.py's loki_range_query).
--
-- Idempotent — safe to run multiple times, and safe to run whether or not
-- V031 has landed yet (drops the constraint if present before recreating
-- it, rather than assuming V031's exact constraint name).

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V032') THEN
        RAISE NOTICE 'V032 already applied, skipping.';
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cluster_queries' AND column_name = 'kind'
    ) THEN
        RAISE EXCEPTION 'V032 requires V031 (cluster_queries.kind) to be applied first';
    END IF;

    ALTER TABLE cluster_queries DROP CONSTRAINT IF EXISTS cluster_queries_kind_check;
    ALTER TABLE cluster_queries
        ADD CONSTRAINT cluster_queries_kind_check CHECK (kind IN ('instant', 'range', 'logql'));

    INSERT INTO schema_versions (version, description)
    VALUES ('V032', 'cluster_queries.kind allows logql for the Loki relay (#840)');
END $$;
