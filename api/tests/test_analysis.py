TEXT = "Senator Jane Smith said today that the state cut education funding by ten percent last year."


def _register_and_login(client, email="owner@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_guest_create_and_read(client, patch_pipeline):
    r = client.post("/api/analysis", json={"text": TEXT})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] is None
    assert body["status"] == "processing"  # POST response body predates the background task

    # The background task runs synchronously under TestClient's in-process
    # transport, so a follow-up GET immediately after already sees the result.
    get_r = client.get(f"/api/analysis/{body['id']}")
    assert get_r.status_code == 200
    fetched = get_r.json()
    assert fetched["id"] == body["id"]
    assert fetched["status"] == "complete"
    assert fetched["title"] == "Test Analysis Title"
    assert len(fetched["claims"]) == 1
    assert fetched["claims"][0]["sources"][0]["url"] == "https://example.gov/a"


def test_authenticated_create_auto_attaches_user(client, patch_pipeline):
    token = _register_and_login(client)
    r = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.json()["user_id"] is not None

    listed = client.get("/api/analysis", headers=_auth_headers(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["claim_count"] == 1


def test_cross_user_access_is_404(client, patch_pipeline):
    owner_token = _register_and_login(client, "owner2@example.com")
    other_token = _register_and_login(client, "other2@example.com")

    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(owner_token))
    analysis_id = created.json()["id"]

    assert client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(other_token)).status_code == 404
    assert (
        client.patch(
            f"/api/analysis/{analysis_id}", json={"title": "hijack"}, headers=_auth_headers(other_token)
        ).status_code
        == 404
    )
    assert client.delete(f"/api/analysis/{analysis_id}", headers=_auth_headers(other_token)).status_code == 404

    # Owner can still access it fine.
    assert client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(owner_token)).status_code == 200


def test_guest_analysis_readable_by_anyone_until_claimed(client, patch_pipeline):
    created = client.post("/api/analysis", json={"text": TEXT})
    analysis_id = created.json()["id"]

    # Unauthenticated read of a guest analysis succeeds (id-as-secret trust model).
    assert client.get(f"/api/analysis/{analysis_id}").status_code == 200


def test_claim_ownership_is_single_use(client, patch_pipeline):
    guest = client.post("/api/analysis", json={"text": TEXT})
    analysis_id = guest.json()["id"]

    token = _register_and_login(client)
    first = client.post(f"/api/analysis/{analysis_id}/claim-ownership", headers=_auth_headers(token))
    assert first.status_code == 200
    assert first.json()["user_id"] is not None

    second = client.post(f"/api/analysis/{analysis_id}/claim-ownership", headers=_auth_headers(token))
    assert second.status_code == 409

    # Now that it's owned, unauthenticated reads should 404.
    assert client.get(f"/api/analysis/{analysis_id}").status_code == 404


def test_rename_analysis(client, patch_pipeline):
    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]

    renamed = client.patch(f"/api/analysis/{analysis_id}", json={"title": "My Title"}, headers=_auth_headers(token))
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "My Title"


def test_delete_cascades_to_claims_and_sources(client, patch_pipeline, db_session):
    from models import Claim, Source

    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]
    fetched = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).json()
    claim_id = fetched["claims"][0]["id"]

    delete_r = client.delete(f"/api/analysis/{analysis_id}", headers=_auth_headers(token))
    assert delete_r.status_code == 204

    assert client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).status_code == 404
    assert db_session.get(Claim, claim_id) is None
    assert db_session.query(Source).count() == 0


def test_claim_sentence_endpoint_persists_user_selected_claim(client, patch_pipeline):
    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]

    r = client.post(
        f"/api/analysis/{analysis_id}/claim-sentence",
        json={"selected_text": "the state cut education funding by ten percent last year"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_claim"] is True
    assert body["claim"]["source"] == "user_selected"

    refreshed = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token))
    sources = [c["source"] for c in refreshed.json()["claims"]]
    assert sources.count("pipeline") == 1
    assert sources.count("user_selected") == 1


def test_delete_claim(client, patch_pipeline, db_session):
    from models import Claim, Source

    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]
    fetched = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).json()
    claim_id = fetched["claims"][0]["id"]

    delete_r = client.delete(f"/api/analysis/{analysis_id}/claims/{claim_id}", headers=_auth_headers(token))
    assert delete_r.status_code == 204

    refreshed = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token))
    assert refreshed.json()["claims"] == []
    assert db_session.get(Claim, claim_id) is None
    assert db_session.query(Source).count() == 0


def test_delete_claim_cross_user_is_404(client, patch_pipeline):
    owner_token = _register_and_login(client, "claimowner@example.com")
    other_token = _register_and_login(client, "claimother@example.com")

    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(owner_token))
    analysis_id = created.json()["id"]
    fetched = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(owner_token)).json()
    claim_id = fetched["claims"][0]["id"]

    r = client.delete(f"/api/analysis/{analysis_id}/claims/{claim_id}", headers=_auth_headers(other_token))
    assert r.status_code == 404

    # Owner can still see the claim untouched.
    still_there = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(owner_token))
    assert len(still_there.json()["claims"]) == 1


def test_add_more_sources(client, patch_pipeline):
    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]
    fetched = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token)).json()
    claim = fetched["claims"][0]
    claim_id = claim["id"]
    original_urls = {s["url"] for s in claim["sources"]}

    r = client.post(f"/api/analysis/{analysis_id}/claims/{claim_id}/more-sources", headers=_auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    new_urls = {s["url"] for s in body["sources"]}
    assert original_urls <= new_urls
    assert "https://example.gov/more" in new_urls

    refreshed = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(token))
    refreshed_claim = next(c for c in refreshed.json()["claims"] if c["id"] == claim_id)
    assert "https://example.gov/more" in {s["url"] for s in refreshed_claim["sources"]}


def test_add_more_sources_cross_user_is_404(client, patch_pipeline):
    owner_token = _register_and_login(client, "moresrc-owner@example.com")
    other_token = _register_and_login(client, "moresrc-other@example.com")

    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(owner_token))
    analysis_id = created.json()["id"]
    fetched = client.get(f"/api/analysis/{analysis_id}", headers=_auth_headers(owner_token)).json()
    claim_id = fetched["claims"][0]["id"]

    r = client.post(
        f"/api/analysis/{analysis_id}/claims/{claim_id}/more-sources", headers=_auth_headers(other_token)
    )
    assert r.status_code == 404


def test_delete_unknown_claim_id_is_404(client, patch_pipeline):
    token = _register_and_login(client)
    created = client.post("/api/analysis", json={"text": TEXT}, headers=_auth_headers(token))
    analysis_id = created.json()["id"]

    r = client.delete(
        f"/api/analysis/{analysis_id}/claims/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert r.status_code == 404
