from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from library.schemas import PublicAnalysisListItemOut, UpdateProfileRequest
from models import Analysis, Bookmark, Claim, User

PROFILE_VISIBILITY_LEVELS = ("public", "private")


def _bookmark_count_subquery():
    return (
        select(func.count(Bookmark.id))
        .where(Bookmark.analysis_id == Analysis.id)
        .correlate(Analysis)
        .scalar_subquery()
    )


def _claim_count_subquery():
    return select(func.count(Claim.id)).where(Claim.analysis_id == Analysis.id).correlate(Analysis).scalar_subquery()


def _to_list_item(a: Analysis, claim_count: int, bookmark_count: int) -> PublicAnalysisListItemOut:
    return PublicAnalysisListItemOut(
        id=a.id,
        title=a.title,
        source_type=a.source_type,
        speaker=a.speaker,
        author=a.user.username if a.user else None,
        claim_count=claim_count,
        view_count=a.view_count,
        bookmark_count=bookmark_count,
        topics=a.topics or [],
        created_at=a.created_at,
        published_at=a.published_at,
    )


def list_public_analyses(
    db: Session,
    q: str | None = None,
    topic: str | None = None,
    sort: str = "recent",
    limit: int = 20,
    offset: int = 0,
) -> list[PublicAnalysisListItemOut]:
    claim_count = _claim_count_subquery()
    bookmark_count = _bookmark_count_subquery()
    stmt = (
        select(Analysis, claim_count.label("claim_count"), bookmark_count.label("bookmark_count"))
        .where(Analysis.visibility == "public")
        .where(Analysis.status == "complete")
        .options(selectinload(Analysis.user))
    )

    q = (q or "").strip()
    if q:
        tsquery = func.plainto_tsquery("english", q)
        claim_match = (
            select(Claim.id)
            .where(Claim.analysis_id == Analysis.id)
            .where(func.to_tsvector("english", Claim.extracted_claim).op("@@")(tsquery))
            .correlate(Analysis)
            .exists()
        )
        stmt = stmt.where(or_(Analysis.search_vector.op("@@")(tsquery), claim_match))

    if topic:
        stmt = stmt.where(Analysis.topics.contains([topic]))

    if sort == "trending":
        # Simple V1 scoring, per the PRD's own "a simple scoring system is
        # sufficient for Version 1" note - views plus bookmarks weighted
        # higher (a deliberate save is a stronger signal than a view),
        # tie-broken by recency.
        score = Analysis.view_count + bookmark_count * 3
        stmt = stmt.order_by(score.desc(), Analysis.created_at.desc())
    else:
        # published_at is always set for a row that's currently "public"
        # (set_visibility only ever sets visibility="public" together with
        # published_at), so this alone is a safe recency ordering.
        stmt = stmt.order_by(Analysis.published_at.desc())

    stmt = stmt.limit(limit).offset(offset)
    return [_to_list_item(a, cc, bc) for a, cc, bc in db.execute(stmt).all()]


def get_public_analysis_row(db: Session, analysis_id: UUID) -> Analysis:
    row = db.get(
        Analysis,
        analysis_id,
        options=[
            selectinload(Analysis.claims).selectinload(Claim.sources),
            selectinload(Analysis.user),
        ],
    )
    if row is None or row.visibility != "public":
        raise HTTPException(404, "not found")
    return row


def record_public_view(db: Session, analysis: Analysis) -> None:
    analysis.view_count += 1
    db.commit()
    db.refresh(analysis)


def count_bookmarks(db: Session, analysis_id: UUID) -> int:
    return db.execute(select(func.count(Bookmark.id)).where(Bookmark.analysis_id == analysis_id)).scalar_one()


def is_bookmarked(db: Session, user: User | None, analysis_id: UUID) -> bool:
    if user is None:
        return False
    return (
        db.execute(
            select(Bookmark.id).where(Bookmark.user_id == user.id, Bookmark.analysis_id == analysis_id)
        ).first()
        is not None
    )


def update_profile(db: Session, user: User, payload: UpdateProfileRequest) -> User:
    if payload.username is not None:
        existing = db.execute(
            select(User.id).where(func.lower(User.username) == payload.username.lower(), User.id != user.id)
        ).first()
        if existing is not None:
            raise HTTPException(409, "username already taken")
        user.username = payload.username
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    if payload.profile_visibility is not None:
        if payload.profile_visibility not in PROFILE_VISIBILITY_LEVELS:
            raise HTTPException(422, f"profile_visibility must be one of {PROFILE_VISIBILITY_LEVELS}")
        user.profile_visibility = payload.profile_visibility
    db.commit()
    db.refresh(user)
    return user


def get_profile(db: Session, username: str, current_user: User | None) -> tuple[User, list[PublicAnalysisListItemOut]]:
    user = db.execute(select(User).where(func.lower(User.username) == username.lower())).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "not found")
    is_self = current_user is not None and current_user.id == user.id
    if user.profile_visibility == "private" and not is_self:
        raise HTTPException(404, "not found")

    claim_count = _claim_count_subquery()
    bookmark_count = _bookmark_count_subquery()
    stmt = (
        select(Analysis, claim_count.label("claim_count"), bookmark_count.label("bookmark_count"))
        .where(Analysis.user_id == user.id, Analysis.visibility == "public")
        .options(selectinload(Analysis.user))
        .order_by(Analysis.published_at.desc().nullslast(), Analysis.created_at.desc())
    )
    analyses = [_to_list_item(a, cc, bc) for a, cc, bc in db.execute(stmt).all()]
    return user, analyses


def add_bookmark(db: Session, user: User, analysis_id: UUID) -> None:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or analysis.visibility != "public":
        raise HTTPException(404, "not found")
    existing = db.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.analysis_id == analysis_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(Bookmark(user_id=user.id, analysis_id=analysis_id))
    db.commit()


def remove_bookmark(db: Session, user: User, analysis_id: UUID) -> None:
    existing = db.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.analysis_id == analysis_id)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()


def list_bookmarks(db: Session, user: User) -> list[PublicAnalysisListItemOut]:
    claim_count = _claim_count_subquery()
    bookmark_count = _bookmark_count_subquery()
    stmt = (
        select(Analysis, claim_count.label("claim_count"), bookmark_count.label("bookmark_count"))
        .join(Bookmark, Bookmark.analysis_id == Analysis.id)
        .where(Bookmark.user_id == user.id, Analysis.visibility == "public")
        .options(selectinload(Analysis.user))
        .order_by(Bookmark.created_at.desc())
    )
    return [_to_list_item(a, cc, bc) for a, cc, bc in db.execute(stmt).all()]
