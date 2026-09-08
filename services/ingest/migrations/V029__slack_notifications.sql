-- V029: Multi-tenant Slack notifications (E23-T5).
--
-- Each org connects its OWN Slack workspace via OAuth against the one
-- KubeX Slack app (mirrors the GitHub App: one app, N per-org installs).
--
--   slack_workspaces      — one row per (org, Slack workspace) OAuth install.
--                           Holds the bot token, encrypted at rest with
--                           INTEGRATION_ENC_KEY (Fernet) by the app layer;
--                           the DB only ever sees ciphertext (BYTEA).
--   notification_channels — which channels in that workspace get which
--                           events. service_id NULL = all services in the
--                           org. event_types defaults to deploy health
--                           alerts; the column exists now so adding
--                           safety-score / DORA-digest routing later needs
--                           no migration.
--
-- org_id is duplicated onto notification_channels (not only reachable via
-- workspace_id) so the agent's per-deploy delivery lookup is one indexed
-- filter — consistent with CLAUDE.md decision 9. The org_id FK omits
-- ON DELETE CASCADE for the same reason the other tenant tables do:
-- deleting an org is an explicit application decision. workspace_id DOES
-- cascade — a channel has no meaning without its workspace.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V029') THEN
        RAISE NOTICE 'V029 already applied, skipping.';
        RETURN;
    END IF;

    CREATE TABLE IF NOT EXISTS slack_workspaces (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id              UUID NOT NULL REFERENCES organizations(id),
        slack_team_id       TEXT NOT NULL,
        slack_team_name     TEXT,
        bot_token_encrypted BYTEA NOT NULL,
        bot_user_id         TEXT,
        connected_by        UUID REFERENCES users(id) ON DELETE SET NULL,
        installed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        uninstalled_at      TIMESTAMPTZ,
        UNIQUE (org_id, slack_team_id)
    );

    CREATE INDEX IF NOT EXISTS idx_slack_workspaces_org ON slack_workspaces (org_id);

    CREATE TABLE IF NOT EXISTS notification_channels (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id              UUID NOT NULL REFERENCES organizations(id),
        workspace_id        UUID NOT NULL REFERENCES slack_workspaces(id) ON DELETE CASCADE,
        slack_channel_id    TEXT NOT NULL,
        slack_channel_name  TEXT NOT NULL,
        service_id          INTEGER REFERENCES services(id) ON DELETE CASCADE,
        event_types         JSONB NOT NULL DEFAULT '["deploy_health"]'::jsonb,
        enabled             BOOLEAN NOT NULL DEFAULT true,
        last_delivery_at    TIMESTAMPTZ,
        last_delivery_error TEXT,
        created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- Partial unique: at most one row per channel per routing scope. Two
    -- NULLs are distinct under a plain UNIQUE, so the all-services scope
    -- (service_id IS NULL) needs its own expression index to dedupe.
    CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_channels_scoped
        ON notification_channels (workspace_id, slack_channel_id, service_id)
        WHERE service_id IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_channels_all_services
        ON notification_channels (workspace_id, slack_channel_id)
        WHERE service_id IS NULL;

    CREATE INDEX IF NOT EXISTS idx_notification_channels_org ON notification_channels (org_id);

    INSERT INTO schema_versions (version, description)
    VALUES ('V029', 'Multi-tenant Slack notifications: slack_workspaces + notification_channels');
END $$;
