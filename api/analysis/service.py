import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

import pipeline
from analysis.schemas import AnalyzeRequest
from db import SessionLocal
from models import Analysis, Claim, Source, User

VISIBILITY_LEVELS = ("private", "unlisted", "public")


def create_analysis(db: Session, payload: AnalyzeRequest, user: User | None) -> Analysis:
    row = Analysis(
        user_id=user.id if user else None,
        original_text=payload.text,
        speaker=payload.speaker,
        speech_date=payload.speech_date,
        source_type="text",
        status="processing",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_accessible_analysis(db: Session, analysis_id: UUID, user: User | None) -> Analysis:
    """Load an analysis for read/write, enforcing the same trust model everywhere:
    guest (unowned) analyses are accessible id-as-secret to anyone, owned
    analyses only to their owner. 404 (not 403) either way, so a request
    never reveals whether another user's analysis exists.
    """
    row = db.get(
        Analysis,
        analysis_id,
        options=[selectinload(Analysis.claims).selectinload(Claim.sources)],
    )
    if row is None:
        raise HTTPException(404, "not found")
    if row.user_id is not None and (user is None or row.user_id != user.id):
        raise HTTPException(404, "not found")
    return row


def list_analyses(db: Session, user: User, q: str | None = None) -> list[tuple[Analysis, int]]:
    claim_count = (
        select(func.count(Claim.id))
        .where(Claim.analysis_id == Analysis.id)
        .correlate(Analysis)
        .scalar_subquery()
    )
    stmt = select(Analysis, claim_count.label("claim_count")).where(Analysis.user_id == user.id)
    q = (q or "").strip()
    if q:
        tsquery = func.plainto_tsquery("english", q)
        # Matches on the analysis's own generated tsvector (title +
        # original_text) OR on any of its claims' text - claims don't have
        # their own indexed tsvector column (personal-scale data, so a plain
        # to_tsvector() call per row here is fine without a dedicated index).
        claim_match = (
            select(Claim.id)
            .where(Claim.analysis_id == Analysis.id)
            .where(func.to_tsvector("english", Claim.extracted_claim).op("@@")(tsquery))
            .correlate(Analysis)
            .exists()
        )
        stmt = stmt.where(or_(Analysis.search_vector.op("@@")(tsquery), claim_match))
    stmt = stmt.order_by(Analysis.created_at.desc())
    return [(a, count) for a, count in db.execute(stmt).all()]


def rename_analysis(db: Session, analysis: Analysis, title: str) -> Analysis:
    analysis.title = title.strip() or analysis.title
    db.commit()
    db.refresh(analysis)
    return analysis


def delete_analysis(db: Session, analysis: Analysis) -> None:
    db.delete(analysis)
    db.commit()


def get_claim_in_analysis(analysis: Analysis, claim_id: UUID) -> Claim:
    for c in analysis.claims:
        if c.id == claim_id:
            return c
    raise HTTPException(404, "not found")


def delete_claim(db: Session, claim: Claim) -> None:
    db.delete(claim)
    db.commit()


def add_more_sources(db: Session, claim: Claim, speaker: str | None, limit: int = 3) -> Claim:
    """Search for and attach up to `limit` additional sources for a claim,
    skipping URLs it already has, then recompute confidence over the merged
    set. Analysis-level jurisdiction isn't persisted (see run_pipeline_task),
    so this follows the same jurisdiction=None precedent as user-selected
    claims rather than trying to re-derive it.
    """
    exclude_urls = {s.url for s in claim.sources}
    claim_dict = {
        "text": claim.extracted_claim,
        "quote": claim.quote,
        "context": claim.context,
        "related_entities": claim.related_entities or [],
        "time_reference": claim.time_reference,
    }
    new_sources = pipeline.find_more_sources(claim_dict, speaker, None, exclude_urls, limit=limit)
    for s in new_sources:
        claim.sources.append(
            Source(
                url=s.get("url", ""),
                title=s.get("title", ""),
                publisher=_derive_publisher(s.get("url", "")),
                snippet=s.get("snippet", ""),
                retrieval_score=s.get("score"),
                relation=s.get("relation", ""),
            )
        )
    if new_sources:
        all_relations = {s.url: (s.relation or "") for s in claim.sources}
        confidence, confidence_explanation = pipeline.calculate_confidence(
            claim_dict, list(claim.sources), all_relations, speaker=speaker
        )
        claim.confidence = confidence
        claim.confidence_explanation = confidence_explanation
    db.commit()
    db.refresh(claim)
    return claim


def _new_share_token() -> str:
    return secrets.token_urlsafe(24)


def ensure_share_token(db: Session, analysis: Analysis) -> Analysis:
    """Idempotently assigns a share token. The token itself grants no access
    on its own - GET /share/{token} still enforces visibility != "private" -
    it just needs to exist before a link can be handed out.
    """
    if analysis.share_token is None:
        analysis.share_token = _new_share_token()
        db.commit()
        db.refresh(analysis)
    return analysis


def set_visibility(db: Session, analysis: Analysis, visibility: str) -> Analysis:
    if visibility not in VISIBILITY_LEVELS:
        raise HTTPException(422, f"visibility must be one of {VISIBILITY_LEVELS}")
    if visibility != "private" and analysis.share_token is None:
        analysis.share_token = _new_share_token()
    if visibility == "public" and analysis.visibility != "public":
        analysis.published_at = datetime.now(timezone.utc)
    analysis.visibility = visibility
    db.commit()
    db.refresh(analysis)
    return analysis


def get_analysis_by_share_token(db: Session, token: str) -> Analysis:
    """Public, unauthenticated lookup for GET /share/{token}. 404 (not 403)
    for both "no such token" and "token exists but analysis is private", so
    a request never reveals whether a private analysis exists behind a
    guessed/stale token.
    """
    row = db.execute(
        select(Analysis)
        .where(Analysis.share_token == token)
        .options(selectinload(Analysis.claims).selectinload(Claim.sources))
    ).scalar_one_or_none()
    if row is None or row.visibility == "private":
        raise HTTPException(404, "not found")
    row.view_count += 1
    db.commit()
    db.refresh(row)
    return row


def claim_ownership(db: Session, analysis: Analysis, user: User) -> Analysis:
    if analysis.user_id is not None:
        raise HTTPException(409, "analysis already has an owner")
    analysis.user_id = user.id
    db.commit()
    db.refresh(analysis)
    return analysis


def _derive_publisher(url: str) -> str | None:
    if not url:
        return None
    return urlparse(url).netloc or None


# The model sometimes emits a claim's quote with "smart"/typographic
# punctuation (curly quotes, en/em dashes, non-breaking hyphens) even when
# the source text uses the plain ASCII form (or vice versa), which makes an
# exact substring .find() miss a quote that's really there character-for-
# character otherwise - concretely observed with "El-Sayed" (plain hyphen)
# in the source vs "El‑Sayed" (U+2011 non-breaking hyphen) in the quote,
# silently leaving position_in_text (and therefore claim ordering) null.
# Every mapping here is one character to one character, so translating
# both sides can't shift any offsets - a match's index is still valid
# against the original, untranslated text.
_QUOTE_MATCH_TRANSLATION = str.maketrans(
    {
        "‘": "'", "’": "'",  # ‘ ’
        "“": '"', "”": '"',  # “ ”
        "–": "-", "—": "-", "‑": "-", "−": "-",  # – — ‑ −
        " ": " ",  # nbsp
    }
)


def _normalize_for_match(s: str) -> str:
    return s.translate(_QUOTE_MATCH_TRANSLATION)


def _add_claim_row(db: Session, analysis: Analysis, claim: dict, source: str) -> Claim:
    quote = (claim.get("quote") or claim.get("text") or "").strip()
    position = (
        _normalize_for_match(analysis.original_text).find(_normalize_for_match(quote)) if quote else -1
    )
    claim_row = Claim(
        analysis_id=analysis.id,
        extracted_claim=claim.get("text", ""),
        quote=quote,
        explanation=claim.get("explanation", ""),
        context=claim.get("context", ""),
        related_entities=claim.get("related_entities") or [],
        time_reference=claim.get("time_reference"),
        confidence=float(claim.get("confidence", 0.5)),
        confidence_explanation=claim.get("confidence_explanation", ""),
        materiality=float(claim.get("materiality", 0.5)),
        position_in_text=position if position >= 0 else None,
        source=source,
    )
    db.add(claim_row)
    db.flush()  # assign claim_row.id so Source rows below can reference it
    for s in claim.get("sources") or []:
        db.add(
            Source(
                claim_id=claim_row.id,
                url=s.get("url", ""),
                title=s.get("title", ""),
                publisher=_derive_publisher(s.get("url", "")),
                snippet=s.get("snippet", ""),
                retrieval_score=s.get("score"),
                relation=s.get("relation", ""),
            )
        )
    return claim_row


def persist_claims(db: Session, analysis: Analysis, claims: list[dict]) -> None:
    for c in claims:
        _add_claim_row(db, analysis, c, source="pipeline")


def persist_user_selected_claim(db: Session, analysis: Analysis, claim: dict) -> Claim:
    claim_row = _add_claim_row(db, analysis, claim, source="user_selected")
    db.commit()
    db.refresh(claim_row)
    return claim_row


def run_pipeline_task(analysis_id: UUID, text: str) -> None:
    """Background task: runs the AI pipeline and persists results. Uses its
    own DB session since it runs after the request that spawned it returns.
    """
    db = SessionLocal()
    try:
        row = db.get(Analysis, analysis_id)
        if row is None:
            return
        try:
            result = pipeline.run(text, row.speaker, row.speech_date)
            row.title = (result.get("title") or "").strip() or row.title
            row.summary = result.get("summary", "")
            row.topics = result.get("topics", [])
            row.entities = result.get("entities", [])
            row.entity_details = result.get("entity_details", [])
            persist_claims(db, row, result.get("claims", []))
            row.status = "complete"
        except Exception as e:
            row.status = f"failed: {e.__class__.__name__}"
        db.commit()
    finally:
        db.close()
