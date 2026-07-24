from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth.security import decode_token
from db import get_db
from models import User


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def _user_from_access_token(token: str, db: Session) -> User | None:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        user_id = UUID(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer_token(request)
    user = _user_from_access_token(token, db) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = _extract_bearer_token(request)
    if not token:
        return None
    return _user_from_access_token(token, db)
