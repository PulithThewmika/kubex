-- V019: GitHub App installations table (EPIC-021 / E21-T1).
--
-- Tracks which orgs have installed the DeployLens GitHub App, so
-- E21-T2+ can auto-provision webhooks on install rather than requiring
-- manual per-repo GITHUB_WEBHOOK_SECRET setup. github_installation_id is
-- the id GitHub sends on installation/deployment_status/workflow_run
-- events — the join key back to this table. repos is a flat TEXT[]
-- rather than a child table since the app only needs repo names to
-- scope webhook delivery, not per-repo metadata.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V019') THEN
        RAISE NOTICE 'V019 already applied, skipping.';
        RETURN;
    END IF;

    CREATE TABLE IF NOT EXISTS installations (
        id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id                 UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        github_installation_id BIGINT NOT NULL UNIQUE,
        account_login          TEXT NOT NULL,
        repos                  TEXT[] NOT NULL DEFAULT '{}',
        status                 TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'removed')),
        created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_installations_org ON installations (org_id);

    INSERT INTO schema_versions (version, description)
    VALUES ('V019', 'GitHub App installations table');
END $$;
