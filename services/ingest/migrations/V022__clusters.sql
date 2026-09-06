-- V022: Remote cluster registry (EPIC-022 / E22-T1).
--
-- A "cluster" is a remote Kubernetes cluster running the KubeX agent
-- (E22-T3+) that can't be reached directly by the ingest service, so it
-- authenticates with its own bearer token (bcrypt-hashed, like api_keys)
-- rather than the user session JWT. token_hash_old/token_old_expires_at
-- back the rotate-token grace period (E22-T1-S10): for 10 minutes after
-- rotation, both the new and old token verify, so an agent that hasn't
-- picked up the new token yet doesn't get locked out mid-rotation.
--
-- status is the *last known* connectivity state, written by the
-- heartbeat endpoint and the disconnect-sweep background task
-- (E22-T1-S7/S11) — not derived at read time, since Grafana/API
-- consumers want a stable value between heartbeats.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V022') THEN
        RAISE NOTICE 'V022 already applied, skipping.';
        RETURN;
    END IF;

    CREATE TABLE IF NOT EXISTS clusters (
        id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id                 UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        name                   TEXT NOT NULL,
        token_hash             TEXT NOT NULL,
        token_hash_old         TEXT,
        token_old_expires_at   TIMESTAMPTZ,
        agent_version          TEXT,
        argocd_version         TEXT,
        argocd_status          TEXT,
        prometheus_status      TEXT,
        last_heartbeat         TIMESTAMPTZ,
        status                 TEXT NOT NULL DEFAULT 'pending'
                                   CHECK (status IN ('pending', 'connected', 'disconnected')),
        created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (org_id, name)
    );

    CREATE INDEX IF NOT EXISTS idx_clusters_org ON clusters (org_id);

    INSERT INTO schema_versions (version, description)
    VALUES ('V022', 'Cluster registry for remote agent connectivity');
END $$;
