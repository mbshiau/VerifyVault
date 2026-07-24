import pytest


def _login(client, email="searchuser@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    return r.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_analyses(client, monkeypatch):
    import pipeline

    def fake_run_highway(text, speaker=None, speech_date=None):
        return {
            "title": "Highway infrastructure bill",
            "summary": "About roads.",
            "topics": [],
            "entities": [],
            "entity_details": [],
            "claims": [
                {
                    "text": "the bill adds 200 miles of highway",
                    "quote": text[:20],
                    "explanation": "",
                    "context": "",
                    "related_entities": [],
                    "time_reference": "2024",
                    "materiality": 0.5,
                    "confidence": 0.5,
                    "confidence_explanation": "",
                    "sources": [],
                }
            ],
        }

    def fake_run_healthcare(text, speaker=None, speech_date=None):
        return {
            "title": "Healthcare reform plan",
            "summary": "About prescription drug prices.",
            "topics": [],
            "entities": [],
            "entity_details": [],
            "claims": [
                {
                    "text": "prescription drug prices dropped for seniors",
                    "quote": text[:20],
                    "explanation": "",
                    "context": "",
                    "related_entities": [],
                    "time_reference": "2024",
                    "materiality": 0.5,
                    "confidence": 0.5,
                    "confidence_explanation": "",
                    "sources": [],
                }
            ],
        }

    token = _login(client)

    monkeypatch.setattr(pipeline, "run", fake_run_highway)
    a1 = client.post(
        "/api/analysis",
        json={"text": "Governor Bob Jones announced a new highway infrastructure funding bill this week."},
        headers=_headers(token),
    ).json()

    monkeypatch.setattr(pipeline, "run", fake_run_healthcare)
    a2 = client.post(
        "/api/analysis",
        json={"text": "Senator Alice Brown discussed her healthcare reform plan for prescription drugs."},
        headers=_headers(token),
    ).json()

    return client, token, a1, a2


def test_search_matches_title_and_text(two_analyses):
    client, token, a1, a2 = two_analyses

    highway_results = client.get("/api/analysis?q=highway", headers=_headers(token)).json()
    assert [r["id"] for r in highway_results] == [a1["id"]]

    healthcare_results = client.get("/api/analysis?q=healthcare", headers=_headers(token)).json()
    assert [r["id"] for r in healthcare_results] == [a2["id"]]


def test_search_matches_claim_text(two_analyses):
    client, token, a1, a2 = two_analyses

    # "seniors" only appears in analysis 2's claim text, not its title.
    results = client.get("/api/analysis?q=seniors", headers=_headers(token)).json()
    assert [r["id"] for r in results] == [a2["id"]]


def test_search_no_match_returns_empty(two_analyses):
    client, token, _a1, _a2 = two_analyses
    results = client.get("/api/analysis?q=zzz_no_such_term", headers=_headers(token)).json()
    assert results == []


def test_empty_query_returns_all(two_analyses):
    client, token, a1, a2 = two_analyses
    results = client.get("/api/analysis", headers=_headers(token)).json()
    assert {r["id"] for r in results} == {a1["id"], a2["id"]}
