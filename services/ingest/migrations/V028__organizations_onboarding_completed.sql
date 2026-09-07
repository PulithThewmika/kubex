-- V028: Add organizations.onboarding_completed (E24-T2-S6).
--
-- Drives the frontend onboarding wizard: while false (and the org has no
-- GitHub App installations and no clusters), the React shell redirects first
-- login to /app/onboarding. Set true when the user finishes or skips the
-- wizard (POST /api/settings/onboarding/complete). Existing orgs default to
-- false, but the installation/cluster checks keep the wizard from showing to
-- orgs that are already set up.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V028') THEN
        RAISE NOTICE 'V028 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE organizations
        ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT false;

    INSERT INTO schema_versions (version, description)
    VALUES ('V028', 'Add organizations.onboarding_completed');
END $$;
