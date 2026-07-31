import os
import tempfile
from datetime import date
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session
import re

import pipeline
from analysis import service as analysis_service
from config import settings
from db import SessionLocal
from models import Analysis, Transcript, User, Video
from video import media

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}
_TWITTER_HOSTS = {"twitter.com", "www.twitter.com", "mobile.twitter.com", "x.com", "www.x.com"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}


class VideoValidationError(RuntimeError):
    """Raised for a rejected upload (too long, unreadable) so the router can
    turn it into a 400 with a helpful message before any Analysis row exists.
    """


def detect_url_source(url: str) -> str | None:
    """Returns platform string for a recognized host (youtube/twitter/instagram), else None.
    Adding a new URL-based platform is just adding another host set + branch here -
    everything downstream (media.py, run_video_pipeline_task) is already
    generic over "any non-upload source".
    """
    host = (urlparse(url).hostname or "").lower()
    if host in _YOUTUBE_HOSTS:
        return "youtube"
    if host in _TWITTER_HOSTS:
        return "twitter"
    if host in _INSTAGRAM_HOSTS:
        return "instagram"
    return None


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


def create_url_analysis(
    db: Session,
    *,
    analysis_id: UUID,
    url: str,
    speaker: str | None,
    speech_date: date | None,
    user: User | None,
) -> Analysis:
    source = detect_url_source(url)
    if source is None:
        raise VideoValidationError("Please provide a YouTube, X/Twitter, or Instagram video link.")

    try:
        info = media.fetch_url_video_info(url)
    except media.MediaError as e:
        msg = str(e)
        # Common Instagram-specific failure: requires authentication/cookies
        if "Instagram sent an empty media response" in msg or "[Instagram]" in msg:
            raise VideoValidationError(
                "Instagram content often requires a logged-in session. Provide a public Instagram reel accessible without login or use YouTube/X."
            )
        raise VideoValidationError(msg)

    max_duration = settings.video_max_duration_seconds
    if info["duration_seconds"] > max_duration:
        raise VideoValidationError(f"Video is longer than the {max_duration // 3600}-hour limit.")

    title = (info.get("title") or "").strip() or "Untitled Analysis"
    row = Analysis(
        id=analysis_id,
        user_id=user.id if user else None,
        title=title,
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
            filename=title,
            content_type="",
            size_bytes=0,
            duration_seconds=info["duration_seconds"],
            storage_path=None,
            source=source,
            external_video_id=info.get("external_video_id") or None,
            source_url=url,
        )
    )
    db.commit()
    db.refresh(row)
    return row


def run_video_pipeline_task(analysis_id: UUID) -> None:
    """Background task: extracts audio, transcribes it incrementally, runs
    claim detection on partial transcripts, and persists claims with mapped
    timestamps. Uses its own DB session and ensures temp audio cleanup.
    """
    db = SessionLocal()
    try:
        row = db.get(Analysis, analysis_id)
        if row is None:
            return
        video = db.get(Video, analysis_id)

        row.status = "extracting_audio"
        db.commit()

        audio_path = os.path.join(tempfile.gettempdir(), f"{analysis_id}.audio.mp3")

        try:
            # Attempt fast path: if remote (YouTube) captions available, use them
            if video.source != "upload" and (video.source or "").lower() == "youtube":
                try:
                    captions = media.fetch_youtube_captions(video.source_url)
                    if captions and captions.get("segments"):
                        # Persist captions as the transcript and run full claim detection immediately
                        existing_transcript = db.get(Transcript, analysis_id)
                        if existing_transcript is None:
                            db.add(Transcript(id=analysis_id, segments=captions["segments"]))
                        else:
                            existing_transcript.segments = captions["segments"]
                        row.original_text = captions.get("text", "")
                        row.status = "detecting_claims"
                        db.commit()

                        # Process segments sequentially so claims appear as the video would play
                        try:
                            segs = captions.get("segments", [])
                            # Ensure original_text is the merged caption text so position_in_text can be found
                            row.original_text = captions.get("text", "")
                            db.commit()
                            existing_texts = {c.extracted_claim.strip().lower() for c in row.claims}
                            import time

                            for i, seg in enumerate(segs):
                                try:
                                    # Run an ultra-fast live detector on this segment - regex-based
                                    def live_detect_segment_claims(text: str, start_ms: int, end_ms: int) -> list[dict]:
                                        if not text or len(text.strip()) < 10:
                                            return []
                                        results = []
                                        # Split sentences
                                        sents = re.split(r"(?<=[.!?])\\s+", text.strip())
                                        for s in sents:
                                            st = s.strip()
                                            if len(st) < 20:
                                                continue
                                            low = st.lower()
                                            # Skip obvious opinion/question
                                            if st.endswith("?") or re.search(r"\b(opinion|believe|feel|think|should|must)\b", st, re.I):
                                                continue
                                            score = 0
                                            if re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", st):
                                                score += 2
                                            if re.search(r"\b\d{4}\b", st):
                                                score += 2
                                            if "%" in st or re.search(r"\bpercent\b", st, re.I):
                                                score += 2
                                            if re.search(r"\b(is|are|was|were|reported|received|won|lost|voted|passed|bought|paid|made)\b", st, re.I):
                                                score += 1
                                            if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", st):
                                                score += 1
                                            if score >= 2:
                                                results.append({
                                                    "text": st,
                                                    "quote": st,
                                                    "explanation": "Detected as a likely factual claim (live heuristic).",
                                                    "context": "",
                                                    "related_entities": [],
                                                    "time_reference": "unspecified",
                                                    "confidence": 0.25,
                                                    "confidence_explanation": "live heuristic",
                                                    "materiality": 0.5,
                                                    "sources": [],
                                                    # set rough timestamps to the segment boundaries
                                                    "start_ms": start_ms,
                                                    "end_ms": end_ms,
                                                })
                                        return results

                                    start_ms = int(seg.get("start_ms") or 0)
                                    end_ms = int(seg.get("end_ms") or (start_ms + 500))
                                    seg_text = seg.get("text", "")
                                    live_claims = live_detect_segment_claims(seg_text, start_ms, end_ms)
                                    new_live = [c for c in live_claims if c.get("text", "").strip().lower() not in existing_texts]
                                    if new_live:
                                        # Persist live claims in a single batch (fast)
                                        analysis_service.persist_claims(db, row, new_live, source="pipeline_live")
                                        # After adding, ensure start_ms/end_ms already stored via _add_claim_row
                                        db.flush()
                                        db.commit()
                                        existing_texts = {c.extracted_claim.strip().lower() for c in row.claims}
                                except Exception:
                                    db.rollback()

                                # Pace processing lightly to let UI receive claims; short sleep only
                                try:
                                    dur_s = max(0.0, min(0.5, (end_ms - start_ms) / 1000.0))
                                except Exception:
                                    dur_s = 0.1
                                time.sleep(dur_s)

                            # After streaming the quick heuristic pass, run final full detection
                            try:
                                result = pipeline.run(row.original_text or "", row.speaker, row.speech_date)
                                row.title = (result.get("title") or "").strip() or row.title
                                row.summary = result.get("summary", row.summary)
                                row.topics = result.get("topics", row.topics)
                                row.entities = result.get("entities", row.entities)
                                row.entity_details = result.get("entity_details", row.entity_details)

                                # Persist claims from full pass
                                analysis_service.persist_claims(db, row, result.get("claims", []))
                                db.flush()

                                # Map timestamps for claims
                                for claim in row.claims:
                                    if claim.position_in_text is None:
                                        continue
                                    claim.start_ms = media.char_offset_to_ms(segs, claim.position_in_text, edge="start")
                                    claim.end_ms = media.char_offset_to_ms(segs, claim.position_in_text + len(claim.quote or ""), edge="end")
                                row.status = "complete"
                                db.commit()
                                return
                            except Exception:
                                db.rollback()
                        except Exception:
                            db.rollback()

                        # fall back to full audio transcription below
                except Exception:
                    # If caption fetch fails for any reason, fall back to audio path
                    pass

            # Download or extract audio to a temp file
            if video.source == "upload":
                media.extract_audio(video.storage_path, audio_path)
            else:
                media.download_remote_audio(video.source_url, audio_path)

            row.status = "transcribing"
            db.commit()

            # Callback for incremental transcription updates
            def on_partial(result):
                curr_text = result.get("text", "")
                segments = result.get("segments", [])

                # Persist/update transcript segments and merged text
                existing_transcript = db.get(Transcript, analysis_id)
                if existing_transcript is None:
                    db.add(Transcript(id=analysis_id, segments=segments))
                else:
                    existing_transcript.segments = segments
                row.original_text = curr_text
                db.commit()

                # Quick heuristic detection to surface candidate claims fast
                try:
                    existing_texts = {c.extracted_claim.strip().lower() for c in row.claims}
                    quick = pipeline.quick_find_claims(curr_text, max_claims=6)
                    new_quick = [c for c in quick if c.get("text", "").strip().lower() not in existing_texts]
                    if new_quick:
                        analysis_service.persist_claims(db, row, new_quick, source="pipeline_quick")
                        db.flush()
                        # Map timestamps for newly added claims
                        segments_for_map = segments
                        for claim in row.claims:
                            if claim.position_in_text is None:
                                continue
                            if claim.start_ms is None:
                                claim.start_ms = media.char_offset_to_ms(segments_for_map, claim.position_in_text, edge="start")
                            if claim.end_ms is None:
                                char_end = claim.position_in_text + (len(claim.quote) if claim.quote else 0)
                                claim.end_ms = media.char_offset_to_ms(segments_for_map, char_end, edge="end")
                        db.commit()
                except Exception:
                    db.rollback()

                # Run full pipeline detection asynchronously (best-effort)
                try:
                    partial_result = pipeline.run(curr_text, row.speaker, row.speech_date)

                    # Update analysis metadata progressively
                    row.title = (partial_result.get("title") or "").strip() or row.title
                    row.summary = partial_result.get("summary", row.summary)
                    row.topics = partial_result.get("topics", row.topics)
                    row.entities = partial_result.get("entities", row.entities)
                    row.entity_details = partial_result.get("entity_details", row.entity_details)

                    # Persist only newly discovered claims to avoid duplicates
                    existing_texts = {c.extracted_claim.strip().lower() for c in row.claims}
                    new_claims = [c for c in partial_result.get("claims", []) if (c.get("text", "").strip().lower() not in existing_texts)]
                    if new_claims:
                        analysis_service.persist_claims(db, row, new_claims)
                        db.flush()

                        # Map timestamps for claims that now have position_in_text
                        for claim in row.claims:
                            if claim.position_in_text is None:
                                continue
                            if claim.start_ms is None:
                                claim.start_ms = media.char_offset_to_ms(segments, claim.position_in_text, edge="start")
                            if claim.end_ms is None:
                                char_end = claim.position_in_text + (len(claim.quote) if claim.quote else 0)
                                claim.end_ms = media.char_offset_to_ms(segments, char_end, edge="end")
                        db.commit()
                except Exception:
                    # Don't abort transcription loop on detection errors; rollback to clear partial DB state
                    db.rollback()

            # Run the streaming transcription; remove audio file afterward
            try:
                # For live analysis prefer very short segments for near-real-time updates
                media.transcribe_stream(audio_path, on_partial, segment_seconds=1)
            finally:
                if os.path.exists(audio_path):
                    os.remove(audio_path)

            # After streaming finishes, ensure we have transcript text
            final_transcript = db.get(Transcript, analysis_id)
            transcript_text = (row.original_text or "").strip()
            if not transcript_text:
                row.status = "failed: no_speech_detected"
                db.commit()
                return

            # Final full detection pass to catch any missed claims
            segments = final_transcript.segments if final_transcript else []
            row.status = "detecting_claims"
            db.commit()

            result = pipeline.run(transcript_text, row.speaker, row.speech_date)

            row.title = (result.get("title") or "").strip() or row.title
            row.summary = result.get("summary", "")
            row.topics = result.get("topics", [])
            row.entities = result.get("entities", [])
            row.entity_details = result.get("entity_details", [])

            # Persist any remaining claims that weren't added during streaming
            existing_texts = {c.extracted_claim.strip().lower() for c in row.claims}
            remaining = [c for c in result.get("claims", []) if (c.get("text", "").strip().lower() not in existing_texts)]
            if remaining:
                analysis_service.persist_claims(db, row, remaining)
                db.flush()

            # Map timestamps for all claims
            for claim in row.claims:
                if claim.position_in_text is None:
                    continue
                claim.start_ms = media.char_offset_to_ms(segments, claim.position_in_text, edge="start")
                claim.end_ms = media.char_offset_to_ms(segments, claim.position_in_text + len(claim.quote or ""), edge="end")

            row.status = "complete"
            db.commit()

        except Exception as e:
            # Record the exception class and message to help diagnose failures
            try:
                row.status = f"failed: {e.__class__.__name__}: {str(e)}"
                db.commit()
            except Exception:
                pass
            import traceback

            traceback.print_exc()

    finally:
        db.close()
