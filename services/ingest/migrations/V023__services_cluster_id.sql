-- V023: Add services.cluster_id (EPIC-022 / E22-T1-S3).
--
-- Links a service to the remote cluster it runs on, once that cluster
-- is registered (V022). Nullable — most services still run in the
-- local Kind cluster and have no associated `clusters` row.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V023') THEN
        RAISE NOTICE 'V023 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE services ADD COLUMN IF NOT EXISTS cluster_id UUID REFERENCES clusters(id) ON DELETE SET NULL;
    CREATE INDEX IF NOT EXISTS idx_services_cluster ON services (cluster_id);

    INSERT INTO schema_versions (version, description)
    VALUES ('V023', 'Add services.cluster_id linking services to remote clusters');
END $$;
