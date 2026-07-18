from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=20, max_length=100_000)
    speaker: str | None = Field(default=None, max_length=200)


class CleanTextRequest(BaseModel):
    text: str


class CleanTextResponse(BaseModel):
    without_hashes: str
    without_hashes_and_asterisks: str


class Source(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    relation: str = ""


class Claim(BaseModel):
    text: str
    quote: str = ""
    explanation: str = ""
    context: str = ""
    related_entities: list[str] = []
    confidence: float
    confidence_explanation: str = ""
    sources: list[Source] = []


class Entity(BaseModel):
    name: str
    type: str  # person | organization | law | program | location
    description: str = ""
    related_claims: list[str] = []
    related_sources: list[Source] = []


class AnalysisOut(BaseModel):
    id: UUID
    status: str
    text: str
    speaker: str | None = None
    summary: str
    claims: list[Claim]
    topics: list[str]
    entities: list[Entity]
    entity_details: list[Entity] = []
    created_at: datetime
