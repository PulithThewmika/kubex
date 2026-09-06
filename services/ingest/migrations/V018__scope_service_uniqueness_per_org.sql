-- V018: Scope services.name/repo/argocd_app uniqueness per org (#792).
--
-- V001 gave services.name a bare global UNIQUE constraint, and repo/argocd_app
-- were never constrained at all. Post-multi-tenancy (V014), that lets two
-- orgs with a same-named service collide: resolve_service()'s name fallback
-- (services/ingest/app/correlation/engine.py) can match another org's row by
-- name alone, and a same-name auto-registration from a second org would 500
-- on the global UNIQUE violation.
--
-- Fix: drop the bare UNIQUE(name) and replace with UNIQUE(org_id, name);
-- add partial unique indexes on (org_id, repo) / (org_id, argocd_app) since
-- those columns are nullable — same partial-unique-index convention as
-- V002's deployment idempotency indexes.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V018') THEN
        RAISE NOTICE 'V018 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE services DROP CONSTRAINT IF EXISTS services_name_key;

    ALTER TABLE services ADD CONSTRAINT uq_services_org_name UNIQUE (org_id, name);

    CREATE UNIQUE INDEX IF NOT EXISTS uq_services_org_repo
        ON services (org_id, repo)
        WHERE repo IS NOT NULL;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_services_org_argocd_app
        ON services (org_id, argocd_app)
        WHERE argocd_app IS NOT NULL;

    INSERT INTO schema_versions (version, description)
    VALUES ('V018', 'Scope services.name/repo/argocd_app uniqueness to (org_id, ...) instead of bare global uniqueness');
END $$;
