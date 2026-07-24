from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import pipeline
from config import settings
from db import Base, SessionLocal, engine, get_db
from models import Analysis
from schemas import (
    AnalysisOut,
    AnalyzeRequest,
    AnalyzeSelectedClaimRequest,
    AnalyzeSelectedClaimResponse,
    CleanTextRequest,
    CleanTextResponse,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="VerifyVault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_pipeline(analysis_id: UUID, text: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(Analysis, analysis_id)
        if row is None:
            return
        try:
            result = pipeline.run(text, row.speaker, row.speech_date)
            row.summary = result.get("summary", "")
            row.topics = result.get("topics", [])
            row.claims = result.get("claims", [])
            row.entities = result.get("entities", [])
            row.entity_details = result.get("entity_details", [])
            row.status = "complete"
        except Exception as e:
            row.status = f"failed: {e.__class__.__name__}"
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/clean", response_model=CleanTextResponse)
def clean_text(payload: CleanTextRequest):
    without_hashes = payload.text.replace("#", "").strip()
    without_both = payload.text.replace("#", "").replace("*", "").strip()
    return CleanTextResponse(
        without_hashes=without_hashes,
        without_hashes_and_asterisks=without_both
    )


@app.post("/analyze", response_model=AnalysisOut)
def create_analysis(
    payload: AnalyzeRequest,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    row = Analysis(
        input_text=payload.text,
        speaker=payload.speaker,
        speech_date=payload.speech_date,
        status="processing",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    tasks.add_task(_run_pipeline, row.id, payload.text)
    return AnalysisOut(
        id=row.id,
        status=row.status,
        text=row.input_text,
        speaker=row.speaker,
        speech_date=row.speech_date,
        summary="",
        claims=[],
        topics=[],
        entities=[],
        entity_details=[],
        created_at=row.created_at,
    )


@app.get("/analyze/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: UUID, db: Session = Depends(get_db)):
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(404, "not found")
    return AnalysisOut(
        id=row.id,
        status=row.status,
        text=row.input_text,
        speaker=row.speaker,
        speech_date=row.speech_date,
        summary=row.summary,
        claims=row.claims,
        topics=row.topics,
        entities=row.entities,
        entity_details=row.entity_details,
        created_at=row.created_at,
    )


@app.post("/analyze/{analysis_id}/claim", response_model=AnalyzeSelectedClaimResponse)
def analyze_selected_claim(analysis_id: UUID, payload: AnalyzeSelectedClaimRequest, db: Session = Depends(get_db)):
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(404, "not found")
    if row.status != "complete":
        raise HTTPException(409, "analysis is not complete yet")
    try:
        result = pipeline.analyze_selected_claim(row.input_text, payload.selected_text, row.speaker, row.speech_date)
    except Exception:
        raise HTTPException(500, "failed to analyze selected claim")
    return AnalyzeSelectedClaimResponse(
        is_claim=bool(result.get("is_claim")),
        reason=result.get("reason", ""),
        claim=result.get("claim"),
    )
