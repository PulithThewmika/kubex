-- V028: Add organizations.onboarding_completed (E24-T2-S6).
--
-- Drives the frontend onboarding wizard: while false, the React shell
-- redirects first login to /app/onboarding. Set true when the user finishes
-- or skips the wizard (POST /api/settings/onboarding/complete).
--
-- Every org that exists at migration time is already using the product
-- (including legacy per-repo-webhook orgs with no installations/clusters
-- rows), so backfill those to true: ADD COLUMN with DEFAULT true, then flip
-- the default to false so only orgs created *after* this migration see the
-- wizard.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V028') THEN
        RAISE NOTICE 'V028 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE organizations
        ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT true;
    ALTER TABLE organizations
        ALTER COLUMN onboarding_completed SET DEFAULT false;

    INSERT INTO schema_versions (version, description)
    VALUES ('V028', 'Add organizations.onboarding_completed');
END $$;
