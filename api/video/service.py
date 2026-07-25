import os
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

import pipeline
from analysis import service as analysis_service
from config import settings
from db import SessionLocal
from models import Analysis, Transcript, User, Video
from video import media


class VideoValidationError(RuntimeError):
    """Raised for a rejected upload (too long, unreadable) so the router can
    turn it into a 400 with a helpful message before any Analysis row exists.
    """


def create_video_analysis(
    db: Session,
    *,
    analysis_id: UUID,
    storage_path: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    speaker: str | None,
    speech_date: date | None,
    user: User | None,
) -> Analysis:
    try:
        info = media.probe_video(storage_path)
    except media.MediaError as e:
        raise VideoValidationError(str(e))

    max_duration = settings.video_max_duration_seconds
    if info["duration_seconds"] > max_duration:
        raise VideoValidationError(f"Video is longer than the {max_duration // 3600}-hour limit.")

    row = Analysis(
        id=analysis_id,
        user_id=user.id if user else None,
        original_text="",
        speaker=speaker,
        speech_date=speech_date,
        source_type="video",
        status="uploading",
    )
    db.add(row)
    db.add(
        Video(
            id=analysis_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            duration_seconds=info["duration_seconds"],
            storage_path=storage_path,
        )
    )
    db.commit()
    db.refresh(row)
    return row


def run_video_pipeline_task(analysis_id: UUID) -> None:
    """Background task: extracts audio, transcribes it, then calls the exact
    same pipeline.run() text analyses use, and maps each resulting claim's
    existing position_in_text through the transcript's segment timings to
    get start_ms/end_ms. Uses its own DB session, like
    analysis.service.run_pipeline_task, since it runs after the request that
    spawned it returns.
    """
    db = SessionLocal()
    try:
        row = db.get(Analysis, analysis_id)
        if row is None:
            return
        video = db.get(Video, analysis_id)
        try:
            row.status = "extracting_audio"
            db.commit()
            audio_path = video.storage_path + ".audio.mp3"
            try:
                media.extract_audio(video.storage_path, audio_path)

                row.status = "transcribing"
                db.commit()
                transcript_result = media.transcribe(audio_path)
            finally:
                if os.path.exists(audio_path):
                    os.remove(audio_path)

            transcript_text = transcript_result["text"].strip()
            if not transcript_text:
                row.status = "failed: no_speech_detected"
                db.commit()
                return

            segments = transcript_result["segments"]
            db.add(Transcript(id=analysis_id, segments=segments))
            row.original_text = transcript_text

            row.status = "detecting_claims"
            db.commit()
            result = pipeline.run(transcript_text, row.speaker, row.speech_date)
            row.title = (result.get("title") or "").strip() or row.title
            row.summary = result.get("summary", "")
            row.topics = result.get("topics", [])
            row.entities = result.get("entities", [])
            row.entity_details = result.get("entity_details", [])
            analysis_service.persist_claims(db, row, result.get("claims", []))
            db.flush()
            for claim in row.claims:
                if claim.position_in_text is None:
                    continue
                claim.start_ms = media.char_offset_to_ms(segments, claim.position_in_text, edge="start")
                claim.end_ms = media.char_offset_to_ms(
                    segments, claim.position_in_text + len(claim.quote), edge="end"
                )
            row.status = "complete"
        except Exception as e:
            row.status = f"failed: {e.__class__.__name__}"
        db.commit()
    finally:
        db.close()
