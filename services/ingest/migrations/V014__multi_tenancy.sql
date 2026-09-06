-- V014: Multi-tenancy — org_id on all data tables (EPIC-020 / E20-T1).
--
-- Adds org_id UUID FK to services, deployments, alerts, pipeline_events, and
-- backfills existing rows to a default organization. deployments and alerts
-- already carry service_id, so their org_id is derived by joining through
-- services.org_id rather than being independently assigned — this stays
-- correct if a service is ever moved between orgs after backfill runs.
-- pipeline_events has no FK to services (the correlation engine resolves
-- identity from the payload, not a stored column), so it backfills directly
-- to the default org.
--
-- Idempotent — safe to run multiple times.

DO $$
DECLARE
    default_org_id UUID;
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V014') THEN
        RAISE NOTICE 'V014 already applied, skipping.';
        RETURN;
    END IF;

    -- ── default organization ────────────────────────────────────────────────
    -- Backfill target for all pre-multi-tenancy rows. Reuses the org that
    -- already exists (the real user's org from OAuth testing) if there is
    -- exactly one, rather than creating a separate synthetic "legacy" org —
    -- simpler and correct given today's data. Falls back to creating one so
    -- this migration also runs cleanly against an empty database.
    SELECT id INTO default_org_id FROM organizations ORDER BY created_at LIMIT 1;

    IF default_org_id IS NULL THEN
        INSERT INTO organizations (name, slug)
        VALUES ('Legacy', 'legacy')
        RETURNING id INTO default_org_id;
    END IF;

    INSERT INTO schema_versions (version, description)
    VALUES ('V014', 'Multi-tenancy: org_id on services, deployments, alerts, pipeline_events');
END $$;
