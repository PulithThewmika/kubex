-- V025: Add services.health_check_url and health_check_interval_s (E23-T1-S1).
--
-- Fallback health signal for services without Prometheus: an HTTP URL the
-- detection agent pings periodically. NULL url means the fallback is
-- disabled for that service.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V025') THEN
        RAISE NOTICE 'V025 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE services ADD COLUMN IF NOT EXISTS health_check_url TEXT;
    ALTER TABLE services ADD COLUMN IF NOT EXISTS health_check_interval_s INT NOT NULL DEFAULT 30;

    INSERT INTO schema_versions (version, description)
    VALUES ('V025', 'Add services.health_check_url and health_check_interval_s');
END $$;
