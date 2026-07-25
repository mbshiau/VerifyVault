from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from analysis.schemas import ClaimOut
from models import Analysis, User
from schemas import Entity
from video.schemas import TranscriptOut, VideoOut

_USERNAME_PATTERN = r"^[a-z0-9_]{3,30}$"


class UpdateProfileRequest(BaseModel):
    username: str | None = Field(default=None, pattern=_USERNAME_PATTERN)
    bio: str | None = Field(default=None, max_length=280)
    avatar_url: str | None = Field(default=None, max_length=1000)
    profile_visibility: str | None = None


class PublicAnalysisListItemOut(BaseModel):
    id: UUID
    title: str
    source_type: str
    speaker: str | None = None
    author: str | None = None
    claim_count: int
    view_count: int
    bookmark_count: int
    topics: list[str] = []
    created_at: datetime
    published_at: datetime | None = None


class PublicAnalysisDetailOut(BaseModel):
    """Public-library equivalent of SharedAnalysisOut - same read-only
    shape, plus the author/bookmark metadata a library visitor also needs.
    """

    id: UUID
    title: str
    source_type: str
    text: str
    speaker: str | None = None
    speech_date: date | None = None
    summary: str
    claims: list[ClaimOut]
    topics: list[str]
    entities: list[Entity]
    entity_details: list[Entity] = []
    created_at: datetime
    view_count: int
    video: VideoOut | None = None
    transcript: TranscriptOut | None = None
    author: str | None = None
    bookmark_count: int = 0
    bookmarked: bool = False

    @classmethod
    def from_orm_analysis(cls, a: Analysis, *, bookmark_count: int, bookmarked: bool) -> "PublicAnalysisDetailOut":
        return cls(
            id=a.id,
            title=a.title,
            source_type=a.source_type,
            text=a.original_text,
            speaker=a.speaker,
            speech_date=a.speech_date,
            summary=a.summary,
            claims=[ClaimOut.from_orm_claim(c) for c in a.claims],
            topics=a.topics or [],
            entities=a.entities or [],
            entity_details=a.entity_details or [],
            created_at=a.created_at,
            view_count=a.view_count,
            video=VideoOut.from_orm_video(a.video) if a.video else None,
            transcript=TranscriptOut.from_orm_transcript(a.transcript) if a.transcript else None,
            author=a.user.username if a.user else None,
            bookmark_count=bookmark_count,
            bookmarked=bookmarked,
        )


class ProfileOut(BaseModel):
    username: str
    bio: str
    avatar_url: str | None = None
    joined_at: datetime
    public_analysis_count: int
    analyses: list[PublicAnalysisListItemOut]

    @classmethod
    def from_orm_user(cls, u: User, analyses: list[PublicAnalysisListItemOut]) -> "ProfileOut":
        return cls(
            username=u.username or "",
            bio=u.bio,
            avatar_url=u.avatar_url,
            joined_at=u.created_at,
            public_analysis_count=len(analyses),
            analyses=analyses,
        )


class BookmarkRequest(BaseModel):
    analysis_id: UUID
