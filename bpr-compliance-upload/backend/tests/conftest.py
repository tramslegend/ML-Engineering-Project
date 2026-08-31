import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import text

from app.db import Base, SessionLocal, engine
from app.init_db import AUDIT_IMMUTABILITY_SQL


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Tests run against the same local Postgres instance used for manual
    verification (postgresql://bpr:bpr@localhost:5433/bpr_compliance) —
    this is a portfolio project, not a CI environment with test containers,
    so we reuse the already-running local cluster rather than requiring a
    second one."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(AUDIT_IMMUTABILITY_SQL))
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
