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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="user")


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
