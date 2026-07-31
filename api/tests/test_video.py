import pytest

SEG1 = "The president said the sky is blue."
SEG2 = "The economy grew ten percent last year."
FULL_TRANSCRIPT_TEXT = SEG1 + " " + SEG2
FAKE_SEGMENTS = [
    {
        "text": SEG1,
        "start_ms": 0,
        "end_ms": 3000,
        "confidence": 0.9,
        "start_char": 0,
        "end_char": len(SEG1),
    },
    {
        "text": SEG2,
        "start_ms": 3000,
        "end_ms": 6000,
        "confidence": 0.8,
        "start_char": len(SEG1) + 1,
        "end_char": len(SEG1) + 1 + len(SEG2),
    },
]


def _register_and_login(client, email="video-owner@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _isolate_video_storage(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "video_storage_dir", str(tmp_path / "videos"))


@pytest.fixture
def patch_media(monkeypatch):
    from video import media

    monkeypatch.setattr(media, "probe_video", lambda path: {"duration_seconds": 5.0, "has_audio": True})

    def fake_extract_audio(video_path, out_path):
        with open(out_path, "wb") as f:
            f.write(b"fake-audio")

    monkeypatch.setattr(media, "extract_audio", fake_extract_audio)
    monkeypatch.setattr(
        media, "transcribe", lambda audio_path: {"text": FULL_TRANSCRIPT_TEXT, "segments": FAKE_SEGMENTS}
    )


def test_video_upload_rejects_bad_format(client):
    r = client.post("/api/video/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_video_upload_rejects_oversized(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "video_max_size_mb", 0)
    r = client.post("/api/video/upload", files={"file": ("speech.mp4", b"x" * 100, "video/mp4")})
    assert r.status_code == 413


def test_video_upload_happy_path(client, patch_media, patch_pipeline):
    r = client.post("/api/video/upload", files={"file": ("speech.mp4", b"fake-video-bytes", "video/mp4")})
    assert r.status_code == 200
    video_id = r.json()["id"]

    # TestClient runs BackgroundTasks synchronously in-process, so processing
    # has already finished by the time the upload response above returned.
    status_r = client.get(f"/api/video/{video_id}/status")
    assert status_r.status_code == 200
    assert status_r.json()["status"] == "complete"

    get_r = client.get(f"/api/video/{video_id}")
    assert get_r.status_code == 200
    body = get_r.json()
    assert body["source_type"] == "video"
    assert body["text"] == FULL_TRANSCRIPT_TEXT
    assert body["video"]["filename"] == "speech.mp4"
    assert body["transcript"]["segments"][0]["text"] == SEG1
    assert len(body["claims"]) == 1
    claim = body["claims"][0]
    # The fake pipeline's claim quote is text[:20], a prefix that falls
    # entirely inside SEG1 - so both the claim's start and end should map to
    # SEG1's timing.
    assert claim["start_ms"] == 0
    assert claim["end_ms"] == 3000

    file_r = client.get(f"/api/video/{video_id}/file")
    assert file_r.status_code == 200


def test_claim_quote_ending_at_segment_boundary_still_gets_end_ms(client, patch_media, monkeypatch):
    """Regression test: a claim quote that exactly matches SEG1 (the
    realistic case - claim quotes are usually whole sentences, so they
    almost always end exactly at a segment boundary) must still resolve an
    end_ms, not None. position_in_text + len(quote) is one-past-the-end,
    which used to land exactly on the inter-segment gap.
    """
    import pipeline

    def fake_run(text, speaker=None, speech_date=None):
        return {
            "title": "Boundary Test",
            "summary": "",
            "topics": [],
            "entities": [],
            "entity_details": [],
            "claims": [
                {
                    "text": SEG1,
                    "quote": SEG1,
                    "explanation": "",
                    "context": "",
                    "related_entities": [],
                    "time_reference": None,
                    "materiality": 0.5,
                    "confidence": 0.5,
                    "confidence_explanation": "",
                    "sources": [],
                }
            ],
        }

    monkeypatch.setattr(pipeline, "run", fake_run)

    r = client.post("/api/video/upload", files={"file": ("speech.mp4", b"fake-video-bytes", "video/mp4")})
    video_id = r.json()["id"]

    body = client.get(f"/api/video/{video_id}").json()
    claim = body["claims"][0]
    assert claim["start_ms"] == 0
    assert claim["end_ms"] == 3000


def test_video_claims_ordered_chronologically_not_by_materiality(client, patch_media, monkeypatch):
    """Video claims should come back in the order they're spoken (start_ms
    ascending), even when a later-spoken claim has higher materiality -
    text analyses keep materiality-first ordering (models.py's relationship
    default), but that's the wrong order for a video transcript.
    """
    import pipeline

    def fake_run(text, speaker=None, speech_date=None):
        return {
            "title": "Ordering Test",
            "summary": "",
            "topics": [],
            "entities": [],
            "entity_details": [],
            "claims": [
                # Spoken second (SEG2), but higher materiality - would sort
                # first under materiality-desc ordering.
                {
                    "text": SEG2,
                    "quote": SEG2,
                    "explanation": "",
                    "context": "",
                    "related_entities": [],
                    "time_reference": None,
                    "materiality": 0.9,
                    "confidence": 0.5,
                    "confidence_explanation": "",
                    "sources": [],
                },
                # Spoken first (SEG1), lower materiality.
                {
                    "text": SEG1,
                    "quote": SEG1,
                    "explanation": "",
                    "context": "",
                    "related_entities": [],
                    "time_reference": None,
                    "materiality": 0.2,
                    "confidence": 0.5,
                    "confidence_explanation": "",
                    "sources": [],
                },
            ],
        }

    monkeypatch.setattr(pipeline, "run", fake_run)

    r = client.post("/api/video/upload", files={"file": ("speech.mp4", b"fake-video-bytes", "video/mp4")})
    video_id = r.json()["id"]

    body = client.get(f"/api/video/{video_id}").json()
    claims = body["claims"]
    assert [c["text"] for c in claims] == [SEG1, SEG2]
    assert claims[0]["start_ms"] < claims[1]["start_ms"]


def test_video_no_speech_detected(client, monkeypatch, patch_pipeline):
    from video import media

    monkeypatch.setattr(media, "probe_video", lambda path: {"duration_seconds": 5.0, "has_audio": True})
    monkeypatch.setattr(media, "extract_audio", lambda video_path, out_path: open(out_path, "wb").close())
    monkeypatch.setattr(media, "transcribe", lambda audio_path: {"text": "   ", "segments": []})

    r = client.post("/api/video/upload", files={"file": ("silent.mp4", b"bytes", "video/mp4")})
    assert r.status_code == 200
    video_id = r.json()["id"]

    status_r = client.get(f"/api/video/{video_id}/status")
    assert status_r.json()["status"] == "failed: no_speech_detected"


@pytest.fixture
def patch_url_media(monkeypatch):
    """Generic fixture for both YouTube and Twitter/X url-sourced flows -
    media.py has no platform-specific functions left, only fetch_url_video_info
    and download_remote_audio, shared by every URL source.
    """
    from video import media

    def _apply(info: dict):
        monkeypatch.setattr(media, "fetch_url_video_info", lambda url: info)

        def fake_download_remote_audio(url, out_path):
            with open(out_path, "wb") as f:
                f.write(b"fake-audio")

        monkeypatch.setattr(media, "download_remote_audio", fake_download_remote_audio)
        monkeypatch.setattr(
            media, "transcribe", lambda audio_path: {"text": FULL_TRANSCRIPT_TEXT, "segments": FAKE_SEGMENTS}
        )

    return _apply


def test_from_url_rejects_unsupported_host(client):
    r = client.post("/api/video/from-url", json={"url": "https://example.com/some-video"})
    assert r.status_code == 400


def test_from_url_rejects_too_long_duration(client, monkeypatch):
    from config import settings
    from video import media

    monkeypatch.setattr(settings, "video_max_duration_seconds", 60)
    monkeypatch.setattr(
        media,
        "fetch_url_video_info",
        lambda url: {"duration_seconds": 999, "title": "Long video", "uploader": "x", "external_video_id": "abc123"},
    )
    r = client.post("/api/video/from-url", json={"url": "https://www.youtube.com/watch?v=abc123"})
    assert r.status_code == 400


def test_youtube_happy_path(client, patch_url_media, patch_pipeline):
    patch_url_media(
        {
            "duration_seconds": 5.0,
            "title": "Test YouTube Speech",
            "uploader": "Test Channel",
            "external_video_id": "dQw4w9WgXcQ",
        }
    )
    r = client.post(
        "/api/video/from-url",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "speaker": "Jane Smith"},
    )
    assert r.status_code == 200
    video_id = r.json()["id"]

    # TestClient runs BackgroundTasks synchronously in-process, so processing
    # has already finished by the time the response above returned.
    status_r = client.get(f"/api/video/{video_id}/status")
    assert status_r.json()["status"] == "complete"

    get_r = client.get(f"/api/video/{video_id}")
    assert get_r.status_code == 200
    body = get_r.json()
    assert body["source_type"] == "video"
    # The initial fetched title is just a placeholder while processing -
    # pipeline.run()'s own generated title wins once complete, exactly like
    # the upload flow.
    assert body["title"] == "Test Analysis Title"
    assert body["video"]["source"] == "youtube"
    assert body["video"]["external_video_id"] == "dQw4w9WgXcQ"
    assert len(body["claims"]) == 1
    assert body["claims"][0]["start_ms"] == 0
    assert body["claims"][0]["end_ms"] == 3000

    # No file is ever downloaded/stored for a url-sourced analysis.
    file_r = client.get(f"/api/video/{video_id}/file")
    assert file_r.status_code == 404


def test_twitter_happy_path(client, patch_url_media, patch_pipeline):
    patch_url_media(
        {
            "duration_seconds": 3.17,
            "title": "Captain America - a tweet",
            "uploader": "Captain America",
            # display_id (the tweet/status id), not the underlying media
            # asset's `id` - see fetch_url_video_info's docstring.
            "external_video_id": "719944021058060289",
        }
    )
    r = client.post(
        "/api/video/from-url",
        json={"url": "https://twitter.com/captainamerica/status/719944021058060289"},
    )
    assert r.status_code == 200
    video_id = r.json()["id"]

    status_r = client.get(f"/api/video/{video_id}/status")
    assert status_r.json()["status"] == "complete"

    get_r = client.get(f"/api/video/{video_id}")
    body = get_r.json()
    assert body["video"]["source"] == "twitter"
    assert body["video"]["external_video_id"] == "719944021058060289"
    assert len(body["claims"]) == 1

    file_r = client.get(f"/api/video/{video_id}/file")
    assert file_r.status_code == 404


def test_from_url_accepts_x_dot_com_host(client, patch_url_media, patch_pipeline):
    patch_url_media(
        {"duration_seconds": 3.0, "title": "x.com tweet", "uploader": "x", "external_video_id": "111"}
    )
    r = client.post("/api/video/from-url", json={"url": "https://x.com/someone/status/111"})
    assert r.status_code == 200
    body = client.get(f"/api/video/{r.json()['id']}").json()
    assert body["video"]["source"] == "twitter"


def test_video_cross_user_access_is_404(client, patch_media, patch_pipeline):
    owner_token = _register_and_login(client, "video-owner2@example.com")
    other_token = _register_and_login(client, "video-other2@example.com")

    r = client.post(
        "/api/video/upload",
        files={"file": ("speech.mp4", b"bytes", "video/mp4")},
        headers=_auth_headers(owner_token),
    )
    assert r.status_code == 200
    video_id = r.json()["id"]

    assert client.get(f"/api/video/{video_id}", headers=_auth_headers(other_token)).status_code == 404
    assert client.get(f"/api/video/{video_id}", headers=_auth_headers(owner_token)).status_code == 200

    # The raw video file is deliberately NOT owner-restricted: a browser
    # <video> tag can't attach an Authorization header, so this endpoint
    # extends the same "id is the secret" trust guest analyses already get to
    # the video bytes of owned analyses too - only the full analysis JSON
    # (claims/sources/transcript) stays strictly owner-protected.
    assert client.get(f"/api/video/{video_id}/file").status_code == 200
    assert client.get(f"/api/video/{video_id}/file", headers=_auth_headers(other_token)).status_code == 200
