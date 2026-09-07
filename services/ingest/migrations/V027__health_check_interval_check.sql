-- V027: Enforce services.health_check_interval_s > 0 at the database level.
--
-- The PUT /api/services/:name/health-check endpoint already rejects values
-- below MIN_HEALTH_CHECK_INTERVAL_S (15s), but nothing stopped a direct
-- database write of 0 or negative — which reaches the detection agent's
-- _buffer_capacity() (services/agent/agent/health_check.py) as a divisor
-- and raises ZeroDivisionError.
--
-- Idempotent — safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_versions WHERE version = 'V027') THEN
        RAISE NOTICE 'V027 already applied, skipping.';
        RETURN;
    END IF;

    ALTER TABLE services DROP CONSTRAINT IF EXISTS services_health_check_interval_s_check;
    ALTER TABLE services ADD CONSTRAINT services_health_check_interval_s_check
        CHECK (health_check_interval_s > 0);

    INSERT INTO schema_versions (version, description)
    VALUES ('V027', 'Enforce services.health_check_interval_s > 0');
END $$;
