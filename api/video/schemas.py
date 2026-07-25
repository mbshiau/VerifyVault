from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from models import Transcript, Video


class VideoUploadResponse(BaseModel):
    id: str


class VideoStatusResponse(BaseModel):
    status: str


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    duration_seconds: float | None = None

    @classmethod
    def from_orm_video(cls, video: Video) -> "VideoOut":
        return cls(filename=video.filename, duration_seconds=video.duration_seconds)


class TranscriptSegmentOut(BaseModel):
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


class TranscriptOut(BaseModel):
    segments: list[TranscriptSegmentOut]

    @classmethod
    def from_orm_transcript(cls, transcript: Transcript) -> "TranscriptOut":
        return cls(
            segments=[
                TranscriptSegmentOut(
                    text=s.get("text", ""),
                    start_ms=s.get("start_ms", 0),
                    end_ms=s.get("end_ms", 0),
                    confidence=s.get("confidence"),
                )
                for s in transcript.segments or []
            ]
        )
