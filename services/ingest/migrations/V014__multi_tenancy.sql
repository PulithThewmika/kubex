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
-- org_id FKs intentionally omit ON DELETE CASCADE (unlike org_memberships and
-- api_keys in V012) — these four tables hold real deployment/alert history,
-- and silently wiping it when an org row is deleted would be worse than
-- forcing an explicit decision (reassign or cascade) in application code.
--
-- org_id also gets a column DEFAULT of the resolved default org, not just a
-- one-time backfill. E20-T2 (org-scoped API queries) hasn't landed yet, so
-- services/ingest and the detection agent still insert into these tables
-- without setting org_id — without a DEFAULT, this migration's NOT NULL
-- constraint would break every webhook and alert write the moment it's
-- applied. The DEFAULT is a stopgap E20-T2 should remove once every insert
-- path resolves org_id explicitly.
--
-- Idempotent — safe to run multiple times.

DO $$
DECLARE
    default_org_id UUID;
    org_count      INTEGER;
    tbl            TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V014') THEN
        RAISE NOTICE 'V014 already applied, skipping.';
        RETURN;
    END IF;

    -- ── default organization ────────────────────────────────────────────────
    -- Backfill target for all pre-multi-tenancy rows. Reuses the org that
    -- already exists (the real user's org from OAuth testing) if there is
    -- exactly one, rather than creating a separate synthetic "legacy" org —
    -- simpler and correct given today's data. Refuses to guess if more than
    -- one org exists by the time this runs, since silently picking one would
    -- misattribute another tenant's data with no error. Falls back to
    -- creating one so this migration also runs cleanly against an empty
    -- database.
    SELECT count(*) INTO org_count FROM organizations;
    IF org_count > 1 THEN
        RAISE EXCEPTION
            'V014: % organizations exist — refusing to guess a default backfill target. Resolve manually.',
            org_count;
    END IF;

    SELECT id INTO default_org_id FROM organizations LIMIT 1;

    IF default_org_id IS NULL THEN
        INSERT INTO organizations (name, slug)
        VALUES ('Legacy', 'legacy')
        RETURNING id INTO default_org_id;
    END IF;

    -- ── services ────────────────────────────────────────────────────────────
    ALTER TABLE services ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
    UPDATE services SET org_id = default_org_id WHERE org_id IS NULL;

    -- ── deployments ─────────────────────────────────────────────────────────
    -- Derived via service_id → services.org_id rather than the default org
    -- directly, so a deployment always agrees with its own service's org.
    ALTER TABLE deployments ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
    UPDATE deployments d SET org_id = s.org_id
        FROM services s
        WHERE d.service_id = s.id AND d.org_id IS NULL;

    -- ── alerts ──────────────────────────────────────────────────────────────
    ALTER TABLE alerts ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
    UPDATE alerts a SET org_id = s.org_id
        FROM services s
        WHERE a.service_id = s.id AND a.org_id IS NULL;

    -- ── pipeline_events ─────────────────────────────────────────────────────
    -- No FK to services exists here (see header) — backfills to the default
    -- org directly. E20-T2 must resolve org_id from the payload at insert
    -- time for new rows, since there is nothing to join through afterward.
    ALTER TABLE pipeline_events ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
    UPDATE pipeline_events SET org_id = default_org_id WHERE org_id IS NULL;

    -- ── NOT NULL (after backfill), with a DEFAULT stopgap until E20-T2 ─────
    -- DDL can't take a plpgsql variable directly, hence EXECUTE format(%L).
    FOR tbl IN SELECT unnest(ARRAY['services', 'deployments', 'alerts', 'pipeline_events'])
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN org_id SET DEFAULT %L', tbl, default_org_id);
        EXECUTE format('ALTER TABLE %I ALTER COLUMN org_id SET NOT NULL', tbl);
    END LOOP;

    -- ── indexes ─────────────────────────────────────────────────────────────
    CREATE INDEX IF NOT EXISTS idx_services_org ON services (org_id);
    CREATE INDEX IF NOT EXISTS idx_deployments_org ON deployments (org_id);
    CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts (org_id);
    CREATE INDEX IF NOT EXISTS idx_pipeline_events_org ON pipeline_events (org_id);

    INSERT INTO schema_versions (version, description)
    VALUES ('V014', 'Multi-tenancy: org_id on services, deployments, alerts, pipeline_events');
END $$;
