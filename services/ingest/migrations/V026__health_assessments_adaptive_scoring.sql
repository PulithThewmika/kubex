-- V026: Allow health_assessments to record adaptive/unavailable scoring (E23-T2).
--
-- Adaptive health scoring can produce no score at all when a service has
-- neither Prometheus nor a configured health check — record that as
-- score=NULL, verdict='unknown' instead of skipping the row.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V026') THEN
        RAISE NOTICE 'V026 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE health_assessments ALTER COLUMN score DROP NOT NULL;

    ALTER TABLE health_assessments DROP CONSTRAINT IF EXISTS health_assessments_verdict_check;
    ALTER TABLE health_assessments ADD CONSTRAINT health_assessments_verdict_check
        CHECK (verdict IN ('healthy', 'degraded', 'failed', 'unknown'));

    INSERT INTO schema_versions (version, description)
    VALUES ('V026', 'health_assessments: score nullable, verdict allows unknown (adaptive scoring)');
END $$;
