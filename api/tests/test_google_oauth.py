from auth.oauth import find_or_create_google_user
from models import User


def test_creates_new_user_from_google_userinfo(db_session):
    userinfo = {"sub": "google-sub-1", "email": "newgoogle@example.com", "name": "New Googler", "picture": "https://pic"}
    user = find_or_create_google_user(db_session, userinfo)
    assert user.email == "newgoogle@example.com"
    assert user.google_sub == "google-sub-1"
    assert user.auth_provider == "google"


def test_same_google_sub_returns_same_user(db_session):
    userinfo = {"sub": "google-sub-2", "email": "repeat@example.com", "name": "Repeat", "picture": None}
    user1 = find_or_create_google_user(db_session, userinfo)
    user2 = find_or_create_google_user(db_session, {**userinfo, "name": "Changed Name"})
    assert user1.id == user2.id
    # Second call shouldn't create a duplicate row.
    assert db_session.query(User).filter(User.google_sub == "google-sub-2").count() == 1


def test_links_google_login_to_existing_password_account_by_email(db_session):
    from auth.security import hash_password

    existing = User(
        email="linkme@example.com",
        name=None,
        password_hash=hash_password("password123"),
        auth_provider="password",
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    userinfo = {"sub": "google-sub-3", "email": "linkme@example.com", "name": "Linked Name", "picture": "https://pic"}
    linked = find_or_create_google_user(db_session, userinfo)

    assert linked.id == existing.id
    assert linked.google_sub == "google-sub-3"
    assert linked.auth_provider == "password"  # original provider preserved, not overwritten
    assert linked.name == "Linked Name"  # filled in since it was previously empty
