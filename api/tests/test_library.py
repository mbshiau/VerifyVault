TEXT = "Senator Jane Smith said today that the state cut education funding by ten percent last year."


def _register_and_login(client, email="owner@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_public_analysis(client, token, text=TEXT):
    r = client.post("/api/analysis", json={"text": text}, headers=_auth_headers(token))
    analysis_id = r.json()["id"]
    r = client.patch(
        f"/api/analysis/{analysis_id}/visibility", json={"visibility": "public"}, headers=_auth_headers(token)
    )
    assert r.status_code == 200
    return analysis_id


def test_only_public_analyses_are_listed(client, patch_pipeline):
    token = _register_and_login(client)
    public_id = _create_public_analysis(client, token)

    private_created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    private_id = private_created.json()["id"]

    unlisted_created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    unlisted_id = unlisted_created.json()["id"]
    client.patch(
        f"/api/analysis/{unlisted_id}/visibility", json={"visibility": "unlisted"}, headers=_auth_headers(token)
    )

    ids = {item["id"] for item in client.get("/api/public").json()}
    assert public_id in ids
    assert private_id not in ids
    assert unlisted_id not in ids


def test_public_detail_view_increments_view_count_and_shows_author(client, patch_pipeline):
    token = _register_and_login(client)
    client.patch("/api/profile", json={"username": "janedoe"}, headers=_auth_headers(token))
    analysis_id = _create_public_analysis(client, token)

    r1 = client.get(f"/api/public/{analysis_id}")
    assert r1.status_code == 200
    assert r1.json()["author"] == "janedoe"
    assert r1.json()["view_count"] == 1

    r2 = client.get(f"/api/public/{analysis_id}")
    assert r2.json()["view_count"] == 2


def test_private_and_unlisted_detail_404_from_public_endpoint(client, patch_pipeline):
    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]
    assert client.get(f"/api/public/{analysis_id}").status_code == 404

    client.patch(f"/api/analysis/{analysis_id}/visibility", json={"visibility": "unlisted"}, headers=_auth_headers(token))
    assert client.get(f"/api/public/{analysis_id}").status_code == 404


def test_unpublishing_removes_from_public_listing(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create_public_analysis(client, token)
    assert analysis_id in {item["id"] for item in client.get("/api/public").json()}

    client.patch(f"/api/analysis/{analysis_id}/visibility", json={"visibility": "private"}, headers=_auth_headers(token))
    assert analysis_id not in {item["id"] for item in client.get("/api/public").json()}
    assert client.get(f"/api/public/{analysis_id}").status_code == 404


def test_search_matches_title_and_claim_text(client, patch_pipeline):
    token = _register_and_login(client)
    _create_public_analysis(client, token)

    matches = client.get("/api/public", params={"q": "education funding"}).json()
    assert len(matches) == 1

    no_matches = client.get("/api/public", params={"q": "unrelated gibberish topic"}).json()
    assert len(no_matches) == 0


def test_topic_filter(client, patch_pipeline):
    token = _register_and_login(client)
    analysis_id = _create_public_analysis(client, token)
    assert client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).json()["topics"] == ["Test Topic"]

    matches = client.get("/api/public", params={"topic": "Test Topic"}).json()
    assert analysis_id in {item["id"] for item in matches}

    no_matches = client.get("/api/public", params={"topic": "Nonexistent Topic"}).json()
    assert analysis_id not in {item["id"] for item in no_matches}


def test_trending_orders_by_views_and_bookmarks(client, patch_pipeline):
    token = _register_and_login(client)
    bookmarker_token = _register_and_login(client, "bookmarker@example.com")

    low_id = _create_public_analysis(client, token, text=TEXT)
    high_id = _create_public_analysis(client, token, text="A different statement about healthcare policy reform today.")

    # Give high_id more views and a bookmark so it should outrank low_id.
    client.get(f"/api/public/{high_id}")
    client.get(f"/api/public/{high_id}")
    client.post("/api/bookmarks", json={"analysis_id": high_id}, headers=_auth_headers(bookmarker_token))

    ranked = client.get("/api/public", params={"sort": "trending"}).json()
    ranked_ids = [item["id"] for item in ranked]
    assert ranked_ids.index(high_id) < ranked_ids.index(low_id)


def test_profile_requires_username_and_respects_visibility(client, patch_pipeline):
    token = _register_and_login(client)
    assert client.get("/api/profile/nobody").status_code == 404

    client.patch("/api/profile", json={"username": "publicprofile"}, headers=_auth_headers(token))
    analysis_id = _create_public_analysis(client, token)

    r = client.get("/api/profile/publicprofile")
    assert r.status_code == 200
    body = r.json()
    assert body["public_analysis_count"] == 1
    assert body["analyses"][0]["id"] == analysis_id

    # Case-insensitive lookup.
    assert client.get("/api/profile/PublicProfile").status_code == 200

    client.patch("/api/profile", json={"profile_visibility": "private"}, headers=_auth_headers(token))
    assert client.get("/api/profile/publicprofile").status_code == 404
    # Owner can still see their own profile even while private.
    assert client.get("/api/profile/publicprofile", headers=_auth_headers(token)).status_code == 200


def test_username_must_be_unique(client, patch_pipeline):
    token1 = _register_and_login(client, "user1@example.com")
    token2 = _register_and_login(client, "user2@example.com")
    client.patch("/api/profile", json={"username": "takenname"}, headers=_auth_headers(token1))

    r = client.patch("/api/profile", json={"username": "takenname"}, headers=_auth_headers(token2))
    assert r.status_code == 409


def test_bookmark_add_remove_and_list(client, patch_pipeline):
    owner_token = _register_and_login(client, "creator@example.com")
    reader_token = _register_and_login(client, "reader@example.com")
    analysis_id = _create_public_analysis(client, owner_token)

    r = client.post("/api/bookmarks", json={"analysis_id": analysis_id}, headers=_auth_headers(reader_token))
    assert r.status_code == 204

    # Idempotent - bookmarking twice doesn't error or duplicate.
    client.post("/api/bookmarks", json={"analysis_id": analysis_id}, headers=_auth_headers(reader_token))

    bookmarks = client.get("/api/bookmarks", headers=_auth_headers(reader_token)).json()
    assert len(bookmarks) == 1
    assert bookmarks[0]["id"] == analysis_id
    assert bookmarks[0]["bookmark_count"] == 1

    r = client.delete(f"/api/bookmarks/{analysis_id}", headers=_auth_headers(reader_token))
    assert r.status_code == 204
    assert client.get("/api/bookmarks", headers=_auth_headers(reader_token)).json() == []


def test_cannot_bookmark_non_public_analysis(client, patch_pipeline):
    owner_token = _register_and_login(client, "owner4@example.com")
    reader_token = _register_and_login(client, "reader4@example.com")
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(owner_token))
    analysis_id = created.json()["id"]

    r = client.post("/api/bookmarks", json={"analysis_id": analysis_id}, headers=_auth_headers(reader_token))
    assert r.status_code == 404


def test_unpublishing_removes_bookmarked_analysis_from_my_library(client, patch_pipeline):
    owner_token = _register_and_login(client, "owner5@example.com")
    reader_token = _register_and_login(client, "reader5@example.com")
    analysis_id = _create_public_analysis(client, owner_token)
    client.post("/api/bookmarks", json={"analysis_id": analysis_id}, headers=_auth_headers(reader_token))
    assert len(client.get("/api/bookmarks", headers=_auth_headers(reader_token)).json()) == 1

    client.patch(f"/api/analysis/{analysis_id}/visibility", json={"visibility": "private"}, headers=_auth_headers(owner_token))
    assert client.get("/api/bookmarks", headers=_auth_headers(reader_token)).json() == []
