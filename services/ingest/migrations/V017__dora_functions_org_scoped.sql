-- V017: Convert the four dora_* views into org-parameterized SQL functions
-- (E20-T3, CLAUDE.md decision #6 — DORA logic stays SQL, single authoritative
-- source, no duplication between API/MCP/Grafana).
--
-- Each function takes p_org_id UUID: a real org UUID scopes to that org
-- (API and MCP always pass one), NULL means "no org filter" (platform-wide).
--
-- The views keep their old names and row shapes unchanged — they now just
-- call their function with NULL — so the two Grafana dashboards that query
-- dora_deploy_frequency/dora_lead_time/dora_change_failure_rate/dora_mttr
-- directly (deploy/grafana/dashboards/dora-scorecard.json,
-- platform-overview.json) keep working unmodified as a platform-wide admin
-- view. This is deliberately not "drop the views" — Grafana has no org
-- concept and updating its dashboards to call functions with a real org_id
-- is out of scope for this task's sub-issues (#602-610), which only cover
-- the API, MCP server, and agent. A view and a function CAN share the same
-- name in Postgres (pg_class vs pg_proc are separate namespaces), so no
-- rename was needed.
--
-- Functions are plain CREATE OR REPLACE FUNCTION (naturally idempotent, and
-- CREATE OR REPLACE FUNCTION cannot rerun-fail the way CREATE OR REPLACE VIEW
-- can on a column shape change — see V008/V009/V015's history). The views
-- themselves use DROP VIEW + CREATE VIEW rather than CREATE OR REPLACE VIEW
-- for the same reason V008 does: Postgres rejects a CREATE OR REPLACE that
-- changes a view column's data type, and EXTRACT(EPOCH FROM ...)'s numeric
-- return type is easy to redeclare as double precision by mistake (caught
-- while first applying this migration against the live dev database).
--
-- Idempotent — safe to run multiple times.

CREATE OR REPLACE FUNCTION dora_deploy_frequency(p_org_id UUID)
RETURNS TABLE (
    deploy_date  date,
    service_name text,
    deploy_count bigint
) AS $$
    SELECT
        d.finished_at::date AS deploy_date,
        s.name              AS service_name,
        COUNT(*)            AS deploy_count
    FROM deployments d
    JOIN services s ON s.id = d.service_id
    WHERE d.status IN ('deployed', 'assessed')
      AND d.finished_at IS NOT NULL
      AND (p_org_id IS NULL OR s.org_id = p_org_id)
    GROUP BY d.finished_at::date, s.name
    ORDER BY deploy_date DESC, service_name;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION dora_lead_time(p_org_id UUID)
RETURNS TABLE (
    service_name      text,
    finished_at       timestamptz,
    lead_time_seconds numeric
) AS $$
    SELECT
        s.name AS service_name,
        d.finished_at,
        EXTRACT(EPOCH FROM (d.finished_at - d.commit_at)) AS lead_time_seconds
    FROM deployments d
    JOIN services s ON s.id = d.service_id
    WHERE d.status IN ('deployed', 'assessed')
      AND d.commit_at   IS NOT NULL
      AND d.finished_at IS NOT NULL
      AND (p_org_id IS NULL OR s.org_id = p_org_id);
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION dora_change_failure_rate(p_org_id UUID)
RETURNS TABLE (
    service_name text,
    started_at   timestamptz,
    is_failure   boolean
) AS $$
    SELECT
        s.name AS service_name,
        d.started_at,
        CASE
            WHEN d.status IN ('build_failed', 'sync_failed')
              OR ha.verdict IN ('failed', 'degraded')
            THEN true
            ELSE false
        END AS is_failure
    FROM deployments d
    JOIN services s ON s.id = d.service_id
    LEFT JOIN health_assessments ha ON ha.deployment_id = d.id
    WHERE d.status IN ('deployed', 'assessed', 'build_failed', 'sync_failed')
      AND (p_org_id IS NULL OR s.org_id = p_org_id);
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION dora_mttr(p_org_id UUID)
RETURNS TABLE (
    service_name text,
    fired_at     timestamptz,
    mttr_seconds numeric
) AS $$
    SELECT
        s.name AS service_name,
        a.fired_at,
        EXTRACT(EPOCH FROM (a.resolved_at - a.fired_at)) AS mttr_seconds
    FROM alerts a
    JOIN services s ON s.id = a.service_id
    WHERE a.resolved_at IS NOT NULL
      AND (p_org_id IS NULL OR s.org_id = p_org_id);
$$ LANGUAGE sql STABLE;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V017') THEN
        RAISE NOTICE 'V017 already applied, skipping.';
        RETURN;
    END IF;

    DROP VIEW IF EXISTS dora_deploy_frequency;
    CREATE VIEW dora_deploy_frequency AS
    SELECT * FROM dora_deploy_frequency(NULL);

    DROP VIEW IF EXISTS dora_lead_time;
    CREATE VIEW dora_lead_time AS
    SELECT * FROM dora_lead_time(NULL);

    DROP VIEW IF EXISTS dora_change_failure_rate;
    CREATE VIEW dora_change_failure_rate AS
    SELECT * FROM dora_change_failure_rate(NULL);

    DROP VIEW IF EXISTS dora_mttr;
    CREATE VIEW dora_mttr AS
    SELECT * FROM dora_mttr(NULL);

    GRANT SELECT ON dora_deploy_frequency     TO grafana_ro;
    GRANT SELECT ON dora_lead_time            TO grafana_ro;
    GRANT SELECT ON dora_change_failure_rate  TO grafana_ro;
    GRANT SELECT ON dora_mttr                 TO grafana_ro;

    INSERT INTO schema_versions (version, description)
    VALUES ('V017', 'Convert dora_* views to org-parameterized SQL functions; views become NULL-org wrappers for Grafana');
END $$;
