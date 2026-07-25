import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="password")
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Public-profile fields (V3) - username is nullable because it doesn't
    # exist until a user sets one in settings; a profile is only reachable
    # (GET /api/profile/{username}) once it's set.
    username: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    bio: Mapped[str] = mapped_column(String(280), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    profile_visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="user")
    bookmarks: Mapped[list["Bookmark"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Untitled Analysis")
    source_type: Mapped[str] = mapped_column(String(10), nullable=False, default="text")
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(200), nullable=True)
    speech_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entity_details: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # "private" (default, owner-only), "unlisted" (accessible only via
    # share_token), "public" (also listed/searchable in the future library).
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="private")
    share_token: Mapped[str | None] = mapped_column(String(48), unique=True, nullable=True)
    # Set the first time visibility transitions to "public"; left untouched
    # on later private<->public/unlisted toggles so it reflects most-recent
    # publish time rather than being cleared.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # DB-generated (not set from Python) - kept in sync automatically by
    # Postgres whenever title/original_text change, so search never goes stale.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(original_text, ''))", persisted=True),
        nullable=True,
    )

    user: Mapped["User | None"] = relationship(back_populates="analyses")
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="Claim.materiality.desc()"
    )
    video: Mapped["Video | None"] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    bookmarks: Mapped[list["Bookmark"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_analyses_user_id_created_at", "user_id", "created_at"),
        Index("ix_analyses_search_vector", "search_vector", postgresql_using="gin"),
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extracted_claim: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    related_entities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    time_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    materiality: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    position_in_text: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="pipeline")
    # Only populated when the parent analysis is a video - derived from
    # position_in_text via the transcript's segment timings (see
    # video/media.py:char_offset_to_ms), not stored redundantly elsewhere.
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["Analysis"] = relationship(back_populates="claims")
    sources: Mapped[list["Source"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="Source.retrieval_score.desc()"
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="sources")


class Video(Base):
    """One-to-one with Analysis, sharing its primary key - "video id" and
    "analysis id" are always the same value. user_id/status/created_at are
    deliberately not duplicated here since they already live on Analysis.
    """

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Null for url-sourced rows ("youtube"/"twitter") - only an uploaded file
    # is ever persisted to disk; a URL source is never downloaded/re-hosted,
    # only its audio is briefly fetched for transcription (see video/media.py).
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="upload")
    # The id needed to embed the original player for a url-sourced row - a
    # YouTube video id for "youtube", a tweet/status id for "twitter". Null
    # for "upload".
    external_video_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["Analysis"] = relationship(back_populates="video")


class Transcript(Base):
    """One-to-one with Analysis, sharing its primary key. Holds only the
    timing metadata - the transcript text itself lives in
    Analysis.original_text so claim quote-matching (_add_claim_row) has a
    single place to look, exactly like text analyses.
    """

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True
    )
    # list of {text, start_ms, end_ms, confidence, start_char, end_char}, in order.
    segments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["Analysis"] = relationship(back_populates="transcript")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="bookmarks")
    analysis: Mapped["Analysis"] = relationship(back_populates="bookmarks")

    __table_args__ = (UniqueConstraint("user_id", "analysis_id", name="uq_bookmarks_user_analysis"),)
