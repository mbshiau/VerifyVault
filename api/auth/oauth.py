from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models import User

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def find_or_create_google_user(db: Session, userinfo: dict) -> User:
    """Find-or-create/link a User from a verified Google id_token's userinfo claims.

    Looked up first by google_sub (the stable identifier across logins), then
    by email to link a Google login onto an existing password account rather
    than creating a duplicate - the PRD asks each user to have one account,
    not one per auth method.
    """
    google_sub = userinfo["sub"]
    email = userinfo["email"].lower()

    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if user is not None:
        return user

    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        user.google_sub = google_sub
        user.name = user.name or userinfo.get("name")
        user.profile_picture_url = user.profile_picture_url or userinfo.get("picture")
        db.commit()
        db.refresh(user)
        return user

    user = User(
        email=email,
        name=userinfo.get("name"),
        profile_picture_url=userinfo.get("picture"),
        auth_provider="google",
        google_sub=google_sub,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
