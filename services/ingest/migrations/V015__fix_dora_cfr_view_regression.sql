-- V015: Fix dora_change_failure_rate — V009 regressed it back to the
-- aggregated V003 shape, undoing V008's row-level rewrite.
--
-- V008 replaced dora_change_failure_rate with a row-level view (one row
-- per deployment: service_name/started_at/is_failure) so API/MCP/Grafana
-- consumers could filter by period themselves (see V008's own header).
-- V009 (assessed-verdict CFR fix) was apparently written before V008
-- landed and never rebased onto it: it recreates the OLD aggregated shape
-- (service_name/total_deploys/failed_deploys/failure_rate), which has no
-- started_at or is_failure column at all. Any database where V009 ran
-- after V008 has had a broken dora_change_failure_rate ever since --
-- GET /api/dora's CFR query (WHERE is_failure ... WHERE started_at >= ...)
-- fails with "column does not exist" against that shape.
--
-- This restores the row-level shape. V009's actual goal (count 'degraded'
-- verdicts as failures, not just 'failed') was already present in V008's
-- version of this view -- V009 didn't need to touch it at all.
--
-- Found while building the E20-T2 cross-org isolation test (#600), which
-- is the first thing to apply the full migration history end-to-end
-- rather than against a hand-rolled or partially-migrated schema.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V015') THEN
        RAISE NOTICE 'V015 already applied, skipping.';
        RETURN;
    END IF;

    DROP VIEW IF EXISTS dora_change_failure_rate;
    CREATE VIEW dora_change_failure_rate AS
    SELECT
        s.name                              AS service_name,
        d.started_at,
        CASE
            WHEN d.status IN ('build_failed', 'sync_failed')
              OR ha.verdict IN ('failed', 'degraded')
            THEN true
            ELSE false
        END                                 AS is_failure
    FROM deployments d
    JOIN services s ON s.id = d.service_id
    LEFT JOIN health_assessments ha ON ha.deployment_id = d.id
    WHERE d.status IN ('deployed', 'assessed', 'build_failed', 'sync_failed');

    GRANT SELECT ON dora_change_failure_rate TO grafana_ro;

    INSERT INTO schema_versions (version, description)
    VALUES ('V015', 'Fix dora_change_failure_rate regression from V009 back to row-level shape');
END $$;
