-- V024: cluster_queries — PromQL relay for remote clusters (EPIC-022 / E22-T1-S8/S9).
--
-- Remote clusters aren't directly reachable, so the platform can't run
-- PromQL against them itself. Instead a query is queued here; the
-- agent's GET /api/clusters/:id/queries poll picks up 'pending' rows
-- and POST /api/clusters/:id/results writes the answer back.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V024') THEN
        RAISE NOTICE 'V024 already applied, skipping.';
        RETURN;
    END IF;

    CREATE TABLE IF NOT EXISTS cluster_queries (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cluster_id     UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
        promql         TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed')),
        result         JSONB,
        requested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at   TIMESTAMPTZ
    );

    CREATE INDEX IF NOT EXISTS idx_cluster_queries_pending
        ON cluster_queries (cluster_id) WHERE status = 'pending';

    INSERT INTO schema_versions (version, description)
    VALUES ('V024', 'cluster_queries table for PromQL relay to remote clusters');
END $$;
