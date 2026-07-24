from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

import pipeline
from analysis import service
from analysis.schemas import (
    AnalysisListItemOut,
    AnalysisOut,
    AnalyzeRequest,
    AnalyzeSelectedClaimRequest,
    AnalyzeSelectedClaimResponse,
    ClaimOut,
    RenameAnalysisRequest,
)
from auth.deps import get_current_user, get_current_user_optional
from db import get_db
from models import Analysis, User

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("", response_model=AnalysisOut)
def create_analysis(
    payload: AnalyzeRequest,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    row = service.create_analysis(db, payload, user)
    tasks.add_task(service.run_pipeline_task, row.id, payload.text)
    return AnalysisOut.from_orm_analysis(row)


@router.get("", response_model=list[AnalysisListItemOut])
def list_analyses(q: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [
        AnalysisListItemOut(
            id=a.id,
            title=a.title,
            status=a.status,
            source_type=a.source_type,
            speaker=a.speaker,
            claim_count=count,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a, count in service.list_analyses(db, user, q)
    ]


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: UUID, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    row = service.get_accessible_analysis(db, analysis_id, user)
    return AnalysisOut.from_orm_analysis(row)


@router.patch("/{analysis_id}", response_model=AnalysisOut)
def rename_analysis(
    analysis_id: UUID,
    payload: RenameAnalysisRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    row = service.get_accessible_analysis(db, analysis_id, user)
    row = service.rename_analysis(db, row, payload.title)
    return AnalysisOut.from_orm_analysis(row)


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(
    analysis_id: UUID, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    row = service.get_accessible_analysis(db, analysis_id, user)
    service.delete_analysis(db, row)
    return Response(status_code=204)


@router.post("/{analysis_id}/claim-sentence", response_model=AnalyzeSelectedClaimResponse)
def analyze_selected_claim(
    analysis_id: UUID,
    payload: AnalyzeSelectedClaimRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    row = service.get_accessible_analysis(db, analysis_id, user)
    if row.status != "complete":
        raise HTTPException(409, "analysis is not complete yet")
    try:
        result = pipeline.analyze_selected_claim(row.original_text, payload.selected_text, row.speaker, row.speech_date)
    except Exception:
        raise HTTPException(500, "failed to analyze selected claim")
    if not result.get("is_claim"):
        return AnalyzeSelectedClaimResponse(is_claim=False, reason=result.get("reason", ""), claim=None)
    claim_row = service.persist_user_selected_claim(db, row, result["claim"])
    return AnalyzeSelectedClaimResponse(is_claim=True, reason="", claim=ClaimOut.from_orm_claim(claim_row))


@router.post("/{analysis_id}/claim-ownership", response_model=AnalysisOut)
def claim_ownership(analysis_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(404, "not found")
    row = service.claim_ownership(db, row, user)
    return AnalysisOut.from_orm_analysis(row)
