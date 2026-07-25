"""
Dev-only bearer-token auth. Stands in for a real IdP/OIDC-backed principal
with an explicit re-identify permission (F7.2). Two scopes: general analyst
access, and the narrower re-identify permission — modeled as two separate
tokens so the distinction is visible in every call site, even though a real
deployment would express this as IAM/IdP roles and claims, not shared
secrets.
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import settings


def require_analyst(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.dev_api_token:
        raise HTTPException(status_code=401, detail="invalid or missing analyst token")
    return "analyst:dev-user"


def require_reidentify_permission(authorization: str = Header(default="")) -> str:
    """F7.2: explicit re-identify permission, distinct from general analyst access."""
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.dev_reidentify_token:
        raise HTTPException(status_code=403, detail="missing re-identify permission")
    return "reidentifier:dev-user"
