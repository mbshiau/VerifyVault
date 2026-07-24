import os
import sys
from pathlib import Path

# Must happen before any `api` package module (config.py in particular) is
# imported anywhere - pydantic-settings reads DATABASE_URL from the real
# process environment with higher priority than .env, so setting it here
# first is what keeps tests off the real dev database.
API_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/verifyvault_test"
)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("CORS_ORIGIN", "http://localhost:3000")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")

sys.path.insert(0, str(API_DIR))

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url


def _ensure_test_db_exists(database_url: str) -> None:
    url = make_url(database_url)
    conn = psycopg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname="postgres",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_db():
    from config import settings

    _ensure_test_db_exists(settings.database_url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    from db import engine

    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE TABLE refresh_tokens, sources, claims, analyses, users RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def client():
    from main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def fake_pipeline_run(text: str, speaker=None, speech_date=None) -> dict:
    """Stand-in for pipeline.run() - deterministic, no real LLM/Tavily calls."""
    return {
        "title": "Test Analysis Title",
        "summary": "Test summary.",
        "topics": ["Test Topic"],
        "entities": [{"name": "Jane Doe", "type": "person"}],
        "entity_details": [],
        "claims": [
            {
                "text": "the state cut funding",
                "quote": text[:20],
                "explanation": "explanation",
                "context": "context",
                "related_entities": ["Jane Doe"],
                "time_reference": "2024",
                "materiality": 0.8,
                "confidence": 0.7,
                "confidence_explanation": "test",
                "sources": [
                    {
                        "title": "Test Source",
                        "url": "https://example.gov/a",
                        "snippet": "snippet",
                        "score": 0.9,
                        "relation": "supports",
                    }
                ],
            }
        ],
    }


def fake_analyze_selected_claim(text: str, selected_text: str, speaker=None, speech_date=None) -> dict:
    return {
        "is_claim": True,
        "reason": "",
        "claim": {
            "text": selected_text,
            "quote": selected_text,
            "explanation": "explanation",
            "context": "context",
            "related_entities": [],
            "time_reference": "2024",
            "materiality": 0.6,
            "confidence": 0.6,
            "confidence_explanation": "test",
            "sources": [],
        },
    }


@pytest.fixture
def patch_pipeline(monkeypatch):
    import pipeline

    monkeypatch.setattr(pipeline, "run", fake_pipeline_run)
    monkeypatch.setattr(pipeline, "analyze_selected_claim", fake_analyze_selected_claim)
