from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=20, max_length=100_000)


class Source(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class Claim(BaseModel):
    text: str
    confidence: float
    sources: list[Source] = []


class Entity(BaseModel):
    name: str
    type: str  # person | organization | law | program | location


class AnalysisOut(BaseModel):
    id: UUID
    status: str
    summary: str
    claims: list[Claim]
    topics: list[str]
    entities: list[Entity]
    created_at: datetime
