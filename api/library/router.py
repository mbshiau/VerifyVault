from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from auth.deps import get_current_user, get_current_user_optional
from auth.schemas import UserOut
from db import get_db
from library import service
from library.schemas import (
    BookmarkRequest,
    PublicAnalysisDetailOut,
    PublicAnalysisListItemOut,
    ProfileOut,
    UpdateProfileRequest,
)
from models import User

router = APIRouter(tags=["library"])


@router.get("/api/public", response_model=list[PublicAnalysisListItemOut])
def list_public_analyses(
    q: str | None = None,
    topic: str | None = None,
    sort: str = "recent",
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if sort not in ("recent", "trending"):
        raise HTTPException(422, "sort must be 'recent' or 'trending'")
    return service.list_public_analyses(db, q=q, topic=topic, sort=sort, limit=limit, offset=offset)


@router.get("/api/public/{analysis_id}", response_model=PublicAnalysisDetailOut)
def get_public_analysis(
    analysis_id: UUID, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    row = service.get_public_analysis_row(db, analysis_id)
    service.record_public_view(db, row)
    bookmark_count = service.count_bookmarks(db, analysis_id)
    bookmarked = service.is_bookmarked(db, user, analysis_id)
    return PublicAnalysisDetailOut.from_orm_analysis(row, bookmark_count=bookmark_count, bookmarked=bookmarked)


@router.get("/api/profile/{username}", response_model=ProfileOut)
def get_profile(
    username: str, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    profile_user, analyses = service.get_profile(db, username, user)
    return ProfileOut.from_orm_user(profile_user, analyses)


@router.patch("/api/profile", response_model=UserOut)
def update_profile(
    payload: UpdateProfileRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    updated = service.update_profile(db, user, payload)
    return UserOut.model_validate(updated)


@router.post("/api/bookmarks", status_code=204)
def add_bookmark(payload: BookmarkRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.add_bookmark(db, user, payload.analysis_id)
    return Response(status_code=204)


@router.delete("/api/bookmarks/{analysis_id}", status_code=204)
def remove_bookmark(analysis_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.remove_bookmark(db, user, analysis_id)
    return Response(status_code=204)


@router.get("/api/bookmarks", response_model=list[PublicAnalysisListItemOut])
def list_bookmarks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_bookmarks(db, user)
