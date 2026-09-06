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
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V014') THEN
        RAISE NOTICE 'V014 already applied, skipping.';
        RETURN;
    END IF;

    INSERT INTO schema_versions (version, description)
    VALUES ('V014', 'Multi-tenancy: org_id on services, deployments, alerts, pipeline_events');
END $$;
