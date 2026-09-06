-- V021: Idempotent generic deploy notifications (E21-T3).
--
-- 1. Adds a partial unique index on (commit_sha, service_id). The existing
--    idx_deployments_sha (V001) is non-unique, so the new generic deploy
--    notification endpoint (POST /api/deployments/notify) and the GitHub
--    App's deployment_status orphan-creation path (webhooks_github_app.py)
--    both had no real ON CONFLICT target to upsert against, risking
--    duplicate rows on a redelivered/duplicate notification with no prior
--    correlating deployment — the same gap E21-T2 deferred with a ponytail
--    comment. Not org_id-scoped: service_id already implies a single org
--    (services are org-scoped as of V018), and commit_sha alone isn't
--    unique enough to scope by.
--
-- 2. Allows source='generic' in pipeline_events, for the new endpoint's
--    audit trail — same convention V020 used for 'github_app'.
--
-- Idempotent — safe to run multiple times.

DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V021') THEN
        RAISE NOTICE 'V021 already applied, skipping.';
        RETURN;
    END IF;

    -- deployments has never been constrained on (commit_sha, service_id)
    -- before now, so pre-existing data could already violate it. Fail
    -- loudly with the actual count instead of an opaque unique-violation
    -- from the CREATE UNIQUE INDEX below.
    SELECT count(*) INTO dup_count FROM (
        SELECT commit_sha, service_id FROM deployments WHERE commit_sha IS NOT NULL
        GROUP BY commit_sha, service_id HAVING count(*) > 1
    ) d;
    IF dup_count > 0 THEN
        RAISE EXCEPTION
            'V021: % (commit_sha, service_id) pair(s) already duplicated — resolve manually before migrating',
            dup_count;
    END IF;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_deployments_commit_service
        ON deployments (commit_sha, service_id)
        WHERE commit_sha IS NOT NULL;

    ALTER TABLE pipeline_events DROP CONSTRAINT IF EXISTS pipeline_events_source_check;
    ALTER TABLE pipeline_events ADD CONSTRAINT pipeline_events_source_check
        CHECK (source IN ('github_actions', 'argocd', 'github_app', 'generic'));

    INSERT INTO schema_versions (version, description)
    VALUES ('V021', 'Partial unique index on deployments(commit_sha, service_id); allow generic pipeline_events source');
END $$;
