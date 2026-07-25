from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models import Analysis, Claim
from schemas import Entity
from video.schemas import TranscriptOut, VideoOut


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=20, max_length=100_000)
    speaker: str | None = Field(default=None, max_length=200)
    speech_date: date | None = None


class AnalyzeSelectedClaimRequest(BaseModel):
    selected_text: str = Field(min_length=8, max_length=2_000)


class RenameAnalysisRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    url: str
    publisher: str | None = None
    snippet: str = ""
    retrieval_score: float | None = None
    relation: str = ""


class ClaimOut(BaseModel):
    id: UUID
    text: str
    quote: str = ""
    explanation: str = ""
    context: str = ""
    related_entities: list[str] = []
    time_reference: str | None = None
    confidence: float
    confidence_explanation: str = ""
    materiality: float = 0.5
    position_in_text: int | None = None
    source: str = "pipeline"
    start_ms: int | None = None
    end_ms: int | None = None
    sources: list[SourceOut] = []

    @classmethod
    def from_orm_claim(cls, claim: Claim) -> "ClaimOut":
        return cls(
            id=claim.id,
            text=claim.extracted_claim,
            quote=claim.quote,
            explanation=claim.explanation,
            context=claim.context,
            related_entities=claim.related_entities or [],
            time_reference=claim.time_reference,
            confidence=claim.confidence,
            confidence_explanation=claim.confidence_explanation,
            materiality=claim.materiality,
            position_in_text=claim.position_in_text,
            source=claim.source,
            start_ms=claim.start_ms,
            end_ms=claim.end_ms,
            sources=[SourceOut.model_validate(s) for s in claim.sources],
        )


class AnalysisOut(BaseModel):
    id: UUID
    status: str
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
    user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    video: VideoOut | None = None
    transcript: TranscriptOut | None = None

    @classmethod
    def from_orm_analysis(cls, a: Analysis) -> "AnalysisOut":
        return cls(
            id=a.id,
            status=a.status,
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
            user_id=a.user_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            video=VideoOut.from_orm_video(a.video) if a.video else None,
            transcript=TranscriptOut.from_orm_transcript(a.transcript) if a.transcript else None,
        )


class AnalysisListItemOut(BaseModel):
    id: UUID
    title: str
    status: str
    source_type: str
    speaker: str | None = None
    claim_count: int
    created_at: datetime
    updated_at: datetime


class AnalyzeSelectedClaimResponse(BaseModel):
    is_claim: bool
    reason: str = ""
    claim: ClaimOut | None = None
