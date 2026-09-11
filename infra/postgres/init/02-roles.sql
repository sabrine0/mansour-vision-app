-- Application and audit roles.
--
-- The separation below is what makes the audit log an audit log rather than a
-- log: the application role holds no UPDATE or DELETE grant on `audit_logs`, so
-- an attacker holding the `administrator` application role still cannot erase
-- their trail (docs/architecture/data-model.md, Operational SRS AUD-001).
--
-- The grants themselves are applied by the Alembic migration that creates the
-- table, in Milestone 3. What is created here is the role, because roles are a
-- cluster-level object and migrations are database-level.

DO $$
BEGIN
    -- The role the services connect as. Owns nothing; granted only what it needs.
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mansour_app') THEN
        CREATE ROLE mansour_app NOLOGIN;
    END IF;

    -- Read-only, for the auditor role in the application. Never granted write.
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mansour_auditor') THEN
        CREATE ROLE mansour_auditor NOLOGIN;
    END IF;
END
$$;

-- Revoke the implicit PUBLIC create privilege: any role could otherwise create
-- objects in the public schema.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
