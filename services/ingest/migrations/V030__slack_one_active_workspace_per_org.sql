-- V030: at most one *active* Slack workspace per org (E23-T5, CodeRabbit).
--
-- slack_install already 409s when an active workspace exists, but that
-- leaves a race between two concurrent installs. This partial unique index
-- is the real guard; historical (uninstalled_at IS NOT NULL) rows are
-- unconstrained so reconnect history is preserved.
--
-- If duplicate active rows already exist, keep the most recently installed
-- one and mark the rest uninstalled before creating the index.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V030') THEN
        RAISE NOTICE 'V030 already applied, skipping.';
        RETURN;
    END IF;

    UPDATE slack_workspaces w
    SET uninstalled_at = now()
    WHERE uninstalled_at IS NULL
      AND EXISTS (
          SELECT 1 FROM slack_workspaces w2
          WHERE w2.org_id = w.org_id
            AND w2.uninstalled_at IS NULL
            AND (w2.installed_at, w2.id) > (w.installed_at, w.id)
      );

    CREATE UNIQUE INDEX IF NOT EXISTS uq_slack_workspaces_active_per_org
        ON slack_workspaces (org_id)
        WHERE uninstalled_at IS NULL;

    INSERT INTO schema_versions (version, description)
    VALUES ('V030', 'At most one active Slack workspace per org');
END $$;
