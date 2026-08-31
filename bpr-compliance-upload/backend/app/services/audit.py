from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(db: Session, actor: str, action: str, entity_ref: str | None = None, rationale: str | None = None) -> AuditLog:
    """Append-only audit write. This is the ONLY path FR-11 permits for writing
    audit entries — every mutating route/service must call this rather than
    constructing AuditLog rows itself, so the append-only guarantee has a
    single choke point to reason about (backed by a DB-level trigger, see
    init_db.py, so the guarantee doesn't rely solely on this discipline).
    """
    entry = AuditLog(actor=actor, action=action, entity_ref=entity_ref, rationale=rationale)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
