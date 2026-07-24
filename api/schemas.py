from pydantic import BaseModel


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


class Entity(BaseModel):
    name: str
    type: str  # person | organization | law | program | location
    description: str = ""
    related_claims: list[str] = []
    related_sources: list[Source] = []
