-- V032: record where each cluster's Prometheus lives (#836).
--
-- The cluster agent already discovers the in-cluster Prometheus Service
-- (cluster_agent/prometheus.discover -> namespace + service_name); it just
-- never reported it. Persisting it here gives a multi-cluster org a way to
-- attribute a panel to a specific cluster and gives operators visibility
-- into what the agent found.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V032') THEN
        RAISE NOTICE 'V032 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE clusters ADD COLUMN IF NOT EXISTS prometheus_namespace TEXT;
    ALTER TABLE clusters ADD COLUMN IF NOT EXISTS prometheus_service   TEXT;

    INSERT INTO schema_versions (version, description)
    VALUES ('V032', 'clusters.prometheus_namespace + prometheus_service');
END $$;
