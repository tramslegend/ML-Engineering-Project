import pytest
from sqlalchemy.exc import DBAPIError

from app.services.audit import write_audit


def test_audit_log_update_rejected_at_db_level(db):
    entry = write_audit(db, actor="tester", action="test_action")

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(
            __import__("sqlalchemy").text("UPDATE audit_log SET action = 'tampered' WHERE id = :id"),
            {"id": entry.id},
        )
        db.commit()
    db.rollback()


def test_audit_log_delete_rejected_at_db_level(db):
    entry = write_audit(db, actor="tester", action="test_action_2")

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(
            __import__("sqlalchemy").text("DELETE FROM audit_log WHERE id = :id"),
            {"id": entry.id},
        )
        db.commit()
    db.rollback()
