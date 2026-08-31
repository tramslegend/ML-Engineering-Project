from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.auth_provider_id == payload.auth_provider_id).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        # FR-15: all authentication events are logged, including failures.
        write_audit(db, actor=payload.auth_provider_id, action="login_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user)
    write_audit(db, actor=user.name, action="login_success")
    return LoginResponse(access_token=token, role=user.role, name=user.name)
