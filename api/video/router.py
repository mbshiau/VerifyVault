import os
import re
import uuid
from datetime import date
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from analysis import service as analysis_service
from analysis.schemas import AnalysisOut
from auth.deps import get_current_user_optional
from config import settings
from db import get_db
from models import Analysis, User
from video import service
from video.schemas import VideoStatusResponse, VideoUploadResponse

router = APIRouter(prefix="/api/video", tags=["video"])

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    tasks: BackgroundTasks,
    file: UploadFile = File(...),
    speaker: str | None = Form(default=None),
    speech_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file format '{ext or 'unknown'}'. "
            f"Please upload one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    parsed_speech_date: date | None = None
    if speech_date:
        try:
            parsed_speech_date = date.fromisoformat(speech_date)
        except ValueError:
            raise HTTPException(400, "speech_date must be an ISO date (YYYY-MM-DD).")

    analysis_id = uuid.uuid4()
    storage_dir = Path(settings.video_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{analysis_id}{ext}"

    max_bytes = settings.video_max_size_mb * 1024 * 1024
    size = 0
    try:
        with open(storage_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"Video exceeds the {settings.video_max_size_mb}MB upload limit.")
                out.write(chunk)
    except HTTPException:
        storage_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        row = service.create_video_analysis(
            db,
            analysis_id=analysis_id,
            storage_path=str(storage_path),
            filename=file.filename or storage_path.name,
            content_type=file.content_type or "",
            size_bytes=size,
            speaker=(speaker or "").strip() or None,
            speech_date=parsed_speech_date,
            user=user,
        )
    except service.VideoValidationError as e:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(400, str(e))

    tasks.add_task(service.run_video_pipeline_task, row.id)
    return VideoUploadResponse(id=str(row.id))


@router.get("/{analysis_id}/status", response_model=VideoStatusResponse)
def get_video_status(
    analysis_id: UUID, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    row = analysis_service.get_accessible_analysis(db, analysis_id, user)
    return VideoStatusResponse(status=row.status)


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_video_analysis(
    analysis_id: UUID, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    row = analysis_service.get_accessible_analysis(db, analysis_id, user)
    return AnalysisOut.from_orm_analysis(row)


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
_STREAM_CHUNK = 1024 * 1024


@router.get("/{analysis_id}/file")
def get_video_file(analysis_id: UUID, request: Request, db: Session = Depends(get_db)):
    """Starlette's FileResponse in the installed version doesn't honor Range
    requests (always 200s the whole file), which breaks seeking on anything
    but a fully-buffered video - so Range handling is implemented by hand here.

    Deliberately does not enforce the owner-only check get_accessible_analysis
    applies elsewhere: a browser <video> tag has no way to attach a bearer
    token to its request, so enforcing ownership here would 404 the video for
    any logged-in owner while still working for guests (whose analyses are
    already "id is the secret" accessible to anyone). This endpoint extends
    that same id-as-capability trust to the raw video bytes for owned
    analyses too - the full analysis JSON (claims/sources/transcript/title)
    remains strictly owner-protected on every other endpoint.
    """
    row = db.get(Analysis, analysis_id)
    if row is None or row.video is None or not os.path.exists(row.video.storage_path):
        raise HTTPException(404, "not found")

    path = row.video.storage_path
    media_type = row.video.content_type or "video/mp4"
    file_size = os.path.getsize(path)
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})

    match = _RANGE_RE.match(range_header)
    if not match or (not match.group(1) and not match.group(2)):
        raise HTTPException(416, "Invalid Range header")
    range_start, range_end = match.group(1), match.group(2)
    if range_start:
        start = int(range_start)
        end = int(range_end) if range_end else file_size - 1
    else:
        # Suffix range (e.g. "bytes=-500") - the last N bytes of the file.
        start = max(0, file_size - int(range_end))
        end = file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        raise HTTPException(416, "Invalid Range header")
    length = end - start + 1

    def iterfile():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(_STREAM_CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return StreamingResponse(iterfile(), status_code=206, media_type=media_type, headers=headers)
