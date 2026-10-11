from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from auth.oauth import find_or_create_google_user, oauth
from auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from config import settings
from db import get_db
from models import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
# Scoped to "/" rather than "/auth": the frontend's middleware.ts needs to
# see this cookie on requests to *any* path (e.g. /dashboard) to gate
# protected routes. It's httpOnly and only ever consumed by /auth/refresh
# and /auth/logout server-side, so the wider path doesn't add real exposure.
REFRESH_COOKIE_PATH = "/"


def _cookie_is_secure() -> bool:
    return not settings.frontend_url.startswith("http://localhost")


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime, remember_me: bool) -> None:
    max_age = int((expires_at - datetime.now(timezone.utc)).total_seconds()) if remember_me else None
    # For local development keep Lax so the browser will accept the cookie without HTTPS.
    # For cross-site production deployments set SameSite=None and Secure=True so
    # cookies are sent on cross-origin fetch requests with credentials.
    samesite_val = "lax" if settings.frontend_url.startswith("http://localhost") else "none"
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_cookie_is_secure(),
        samesite=samesite_val,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
    )


def _issue_tokens(response: Response, db: Session, user: User, remember_me: bool = False) -> TokenResponse:
    access_token = create_access_token(user.id)
    refresh_token, jti, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
    db.commit()
    _set_refresh_cookie(response, refresh_token, expires_at, remember_me)
    return TokenResponse(access_token=access_token, user=UserOut.model_validate(user))


def _revoke_refresh_token(db: Session, token: str) -> None:
    try:
        payload = decode_token(token)
    except Exception:
        return
    jti = payload.get("jti")
    if not jti:
        return
    stored = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(409, "An account with this email already exists")
    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        auth_provider="password",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(response, db, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.password_hash is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return _issue_tokens(response, db, user, remember_me=payload.remember_me)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "No refresh token")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    stored = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    now = datetime.now(timezone.utc)
    if stored is None or stored.revoked_at is not None or stored.expires_at < now:
        raise HTTPException(401, "Refresh token expired or revoked")
    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "User not found")
    # Rotate on every use: revoke the presented token, issue a fresh pair -
    # limits the blast radius if a refresh token is ever stolen/replayed.
    stored.revoked_at = now
    db.commit()
    return _issue_tokens(response, db, user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token:
        _revoke_refresh_token(db, token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.get("/google/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        raise HTTPException(400, "Google authentication failed")
    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("sub") or not userinfo.get("email"):
        raise HTTPException(400, "Google account missing required info")

    user = find_or_create_google_user(db, userinfo)

    # Set the refresh cookie on the redirect itself, then send the browser to
    # the frontend - no token ever appears in a URL/query string. The
    # frontend calls /auth/refresh immediately after landing to mint an
    # access token into memory from that cookie.
    redirect = RedirectResponse(url=f"{settings.frontend_url}/auth/callback")
    _issue_tokens(redirect, db, user)
    return redirect
