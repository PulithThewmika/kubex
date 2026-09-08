-- V016: Drop the org_id column DEFAULT installed as a stopgap by V014.
--
-- V014's own header said this explicitly: "org_id also gets a column
-- DEFAULT ... E20-T2 (org-scoped API queries) hasn't landed yet ... The
-- DEFAULT is a stopgap E20-T2 should remove once every insert path
-- resolves org_id explicitly."
--
-- E20-T2 now resolves org_id explicitly on every insert path into these
-- four tables: the GitHub and ArgoCD webhook handlers (services,
-- deployments, pipeline_events) and the detection agent's fire_alert
-- (alerts) — the latter was found, during E20-T2's own code review,
-- to still be relying on the DEFAULT, silently misattributing every
-- agent-fired alert to the default org regardless of which org the
-- underlying deployment belonged to. With that fixed, the DEFAULT no
-- longer protects anything — it only means a future insert path that
-- forgets org_id fails silently (wrong org) instead of loudly (NOT NULL
-- violation). Dropping it converts that failure mode.
--
-- Idempotent — safe to run multiple times.

DO $$
DECLARE
    tbl TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V016') THEN
        RAISE NOTICE 'V016 already applied, skipping.';
        RETURN;
    END IF;

    FOR tbl IN SELECT unnest(ARRAY['services', 'deployments', 'alerts', 'pipeline_events'])
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN org_id DROP DEFAULT', tbl);
    END LOOP;

    INSERT INTO schema_versions (version, description)
    VALUES ('V016', 'Drop org_id column DEFAULT stopgap now that every insert path sets it explicitly');
END $$;
