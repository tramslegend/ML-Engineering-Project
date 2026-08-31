import uuid

import pytest
from fastapi import HTTPException

from app.auth import hash_password, require_roles, verify_password
from app.models import Role, User


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed)
    assert not verify_password("wrong", hashed)


def _user(db, role: Role) -> User:
    u = User(
        name="Test User",
        role=role,
        auth_provider_id=f"rbactest-{uuid.uuid4().hex[:8]}",
        hashed_password=hash_password("x"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_require_roles_allows_matching_role(db):
    user = _user(db, Role.auditor)
    dependency = require_roles(Role.auditor)
    result = dependency(user=user)
    assert result is user


def test_require_roles_blocks_wrong_role(db):
    user = _user(db, Role.loan_officer)
    dependency = require_roles(Role.auditor)
    with pytest.raises(HTTPException) as exc_info:
        dependency(user=user)
    assert exc_info.value.status_code == 403
