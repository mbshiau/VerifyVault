def _register(client, email="user@example.com", password="password123", name="Test User"):
    return client.post("/auth/register", json={"email": email, "password": password, "name": name})


def test_register_login_me_refresh_logout_refresh_fails(client):
    r = _register(client)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "user@example.com"
    access_token = body["access_token"]
    assert client.cookies.get("refresh_token")

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    login = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    logout = client.post("/auth/logout")
    assert logout.status_code == 200

    refresh_after_logout = client.post("/auth/refresh")
    assert refresh_after_logout.status_code == 401


def test_register_duplicate_email_rejected(client):
    assert _register(client).status_code == 200
    dup = _register(client)
    assert dup.status_code == 409


def test_login_wrong_password_rejected(client):
    _register(client)
    bad = client.post("/auth/login", json={"email": "user@example.com", "password": "wrongpassword"})
    assert bad.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_refresh_rotates_token(client):
    _register(client)
    first = client.post("/auth/refresh")
    refresh_cookie_1 = client.cookies.get("refresh_token")
    second = client.post("/auth/refresh")
    refresh_cookie_2 = client.cookies.get("refresh_token")
    assert first.status_code == 200 and second.status_code == 200
    # Rotation issues a new refresh token each time - the cookie value changes.
    assert refresh_cookie_1 != refresh_cookie_2
