-- V020: Allow GitHub App webhook events into pipeline_events (E21-T2).
--
-- Two changes needed for the /webhooks/github/app handler:
--
-- 1. pipeline_events.source has a CHECK constraint from V001 limited to
--    ('github_actions', 'argocd') — inserting source='github_app' violates
--    it on every single delivery.
--
-- 2. pipeline_events.org_id is NOT NULL (V014), but an installation/workflow
--    event can arrive for an account/installation_id this platform doesn't
--    recognize yet (no matching organization, or an unknown installation_id)
--    — the handler logs it and stores org_id=NULL rather than guessing an
--    org, per this table's existing convention of failing loudly instead of
--    misattributing. That requires org_id to actually accept NULL.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V020') THEN
        RAISE NOTICE 'V020 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE pipeline_events DROP CONSTRAINT IF EXISTS pipeline_events_source_check;
    ALTER TABLE pipeline_events ADD CONSTRAINT pipeline_events_source_check
        CHECK (source IN ('github_actions', 'argocd', 'github_app'));

    ALTER TABLE pipeline_events ALTER COLUMN org_id DROP NOT NULL;

    INSERT INTO schema_versions (version, description)
    VALUES ('V020', 'Allow github_app source and NULL org_id in pipeline_events');
END $$;
