TEXT = "Senator Jane Smith said today that the state cut education funding by ten percent last year."


def _register_and_login(client, email="owner@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token):
    r = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    assert r.status_code == 200
    return r.json()["id"]


def test_default_visibility_is_private(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)
    body = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).json()
    assert body["visibility"] == "private"
    assert body["share_token"] is None
    assert body["published_at"] is None
    assert body["view_count"] == 0


def test_only_owner_can_change_visibility(client, patch_pipeline):
    owner_token = _register_and_login(client, "owner3@example.com")
    other_token = _register_and_login(client, "other3@example.com")
    analysis_id = _create(client, owner_token)

    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "public"},
        headers=_auth_headers(other_token),
    )
    assert r.status_code == 404

    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "public"},
        headers=_auth_headers(owner_token),
    )
    assert r.status_code == 200
    assert r.json()["visibility"] == "public"


def test_share_endpoint_generates_token_idempotently(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)

    r1 = client.post(f"/api/analysis/{analysis_id}/share", headers=_auth_headers(token))
    assert r1.status_code == 200
    share_token = r1.json()["share_token"]
    assert share_token

    r2 = client.post(f"/api/analysis/{analysis_id}/share", headers=_auth_headers(token))
    assert r2.json()["share_token"] == share_token


def test_visibility_change_auto_generates_share_token(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)

    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "unlisted"},
        headers=_auth_headers(token),
    )
    assert r.json()["share_token"]


def test_shared_link_404s_while_private(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)
    share_token = client.post(f"/api/analysis/{analysis_id}/share", headers=_auth_headers(token)).json()[
        "share_token"
    ]

    assert client.get(f"/share/{share_token}").status_code == 404
    assert client.get("/share/does-not-exist").status_code == 404


def test_shared_link_works_when_unlisted_or_public_and_counts_views(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)
    client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "unlisted"},
        headers=_auth_headers(token),
    )
    share_token = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).json()["share_token"]

    # No auth header at all - a true anonymous visitor.
    r1 = client.get(f"/share/{share_token}")
    assert r1.status_code == 200
    body = r1.json()
    assert body["title"] == "Test Analysis Title"
    assert len(body["claims"]) == 1
    assert "user_id" not in body
    assert "share_token" not in body
    assert body["view_count"] == 1

    r2 = client.get(f"/share/{share_token}")
    assert r2.json()["view_count"] == 2


def test_published_at_set_on_first_publish_and_kept_on_unpublish(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)

    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "public"},
        headers=_auth_headers(token),
    )
    published_at = r.json()["published_at"]
    assert published_at is not None

    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "private"},
        headers=_auth_headers(token),
    )
    assert r.json()["published_at"] == published_at


def test_invalid_visibility_value_rejected(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create(client, token)
    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility",
        json={"visibility": "friends-only"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 422


def test_guest_analysis_can_still_be_shared(client, patch_pipeline):
    created = client.post("/api/analysis", json={"text": TEXT})
    analysis_id = created.json()["id"]

    r = client.patch(f"/api/analysis/{analysis_id}/visibility", json={"visibility": "public"})
    assert r.status_code == 200
    share_token = r.json()["share_token"]
    assert client.get(f"/share/{share_token}").status_code == 200
