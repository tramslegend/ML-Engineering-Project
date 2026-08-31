"""Creates all tables and installs the append-only guarantee on audit_log
at the database level (FR-12): a trigger that raises on any UPDATE/DELETE
against audit_log, so the guarantee doesn't depend solely on API discipline
(app/services/audit.py is the only code path that writes to it, but even a
direct psql session or a future bug can't mutate history once this trigger
is in place).
"""
from urllib.parse import urlsplit

from sqlalchemy import text

from app.config import settings
from app.db import Base, engine
import app.models  # noqa: F401 - ensures all models are registered on Base before create_all

AUDIT_IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();

DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;
CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
"""


def _provision_readonly_analyst_role():
    """Creates/repassword the bpr_analyst_ro role used exclusively by the
    Compliance Analysis LangChain SQL Agent (app/agents/analysis.py). It gets
    SELECT-only on compliance-relevant tables and, notably, is never granted
    anything on `users` -- the SQL agent must never be able to read
    auth_provider_id/hashed_password, even via a crafted question.
    """
    dbname = (urlsplit(settings.database_url).path or "/bpr_compliance").lstrip("/")
    role_sql = text(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bpr_analyst_ro') THEN
                CREATE ROLE bpr_analyst_ro LOGIN PASSWORD :password;
            ELSE
                ALTER ROLE bpr_analyst_ro WITH PASSWORD :password;
            END IF;
        END
        $$;
        """
    ).bindparams(password=settings.analyst_ro_password)
    with engine.begin() as conn:
        conn.execute(role_sql)
        conn.execute(text(f'GRANT CONNECT ON DATABASE "{dbname}" TO bpr_analyst_ro'))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO bpr_analyst_ro"))
        conn.execute(
            text(
                "GRANT SELECT ON customers, transactions, flags, loan_decisions, "
                "report_drafts, audit_log TO bpr_analyst_ro"
            )
        )
    print("Read-only analyst role provisioned: bpr_analyst_ro (SELECT-only, no access to users).")


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(AUDIT_IMMUTABILITY_SQL))
    _provision_readonly_analyst_role()
    print("Database initialized: tables created, audit_log immutability trigger installed.")


if __name__ == "__main__":
    init_db()
