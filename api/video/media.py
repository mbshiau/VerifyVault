import concurrent.futures
import json
import subprocess
import tempfile
from pathlib import Path

import yt_dlp
from groq import Groq

from config import settings

# Chunk length for splitting audio before transcription. Keeps every chunk's
# upload well under Groq's per-file size limit regardless of the source
# video's bitrate (a 2-hour video at any reasonable bitrate splits into ~12
# chunks this way), and lets chunks transcribe in parallel rather than
# serially - the same ThreadPoolExecutor-for-independent-work pattern
# pipeline.py already uses for concurrent claim fact-checking.
_CHUNK_SECONDS = 600
_MAX_PARALLEL_CHUNKS = 4


class MediaError(RuntimeError):
    """Raised for ffmpeg/ffprobe/transcription failures - callers translate
    this into a `failed: ...` analysis status rather than letting it bubble
    as a raw subprocess/HTTP error.
    """


def probe_video(path: str) -> dict:
    """Reads container metadata only (fast, no full read of the file) to get
    duration and whether an audio stream exists at all.
    """
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise MediaError("Could not read the video file - it may be corrupted or an unsupported format.") from e
    data = json.loads(proc.stdout or "{}")
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    return {"duration_seconds": duration, "has_audio": has_audio}


def extract_audio(video_path: str, out_path: str) -> None:
    """Extracts a mono 16kHz mp3 audio track - the format/rate whisper-family
    models expect, and small enough to keep chunk uploads well under size limits.
    """
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", "-f", "mp3", out_path],
            check=True,
            capture_output=True,
            timeout=1800,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise MediaError("Failed to extract audio from the video.") from e


def fetch_url_video_info(url: str) -> dict:
    """Probes a video URL's metadata only (no download) so duration/existence
    can be validated before committing to an actual download. Generic over
    every site yt-dlp supports (YouTube, Twitter/X, ...) - nothing here is
    platform-specific.
    """
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise MediaError(
            "Could not read this video - it may be private, deleted, age-restricted, or region-locked."
        ) from e
    if info is None:
        raise MediaError("Could not read this video.")
    if info.get("_type") == "playlist" or info.get("entries") is not None:
        raise MediaError("Please provide a link to a single video, not a playlist.")
    return {
        "duration_seconds": float(info.get("duration") or 0.0),
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or "",
        # display_id is the user-facing id (e.g. a tweet/status id for
        # Twitter) - id is often an internal media-asset id instead (observed
        # concretely on Twitter, where `id` is the underlying video's id, not
        # the tweet's). For YouTube the two are the same, so this fallback
        # order works correctly for both without a platform-specific branch.
        "external_video_id": info.get("display_id") or info.get("id") or "",
    }


def download_remote_audio(url: str, out_path: str) -> None:
    """Downloads only the best available audio stream (no video) to a temp
    file, then normalizes it through the exact same extract_audio() every
    uploaded video's audio goes through - so transcribe() downstream never
    needs to know whether the source was an upload or a remote URL.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_template = str(Path(tmp_dir) / "audio.%(ext)s")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": raw_template,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            raise MediaError("Failed to download audio from this video.") from e
        downloaded = next(Path(tmp_dir).glob("audio.*"), None)
        if downloaded is None:
            raise MediaError("Failed to download audio from this video.")
        extract_audio(str(downloaded), out_path)


def _split_audio(audio_path: str, chunk_dir: str) -> list[str]:
    pattern = str(Path(chunk_dir) / "chunk_%04d.mp3")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", audio_path,
                "-f", "segment", "-segment_time", str(_CHUNK_SECONDS),
                "-c", "copy", pattern,
            ],
            check=True,
            capture_output=True,
            timeout=1800,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise MediaError("Failed to prepare audio for transcription.") from e
    return sorted(str(p) for p in Path(chunk_dir).glob("chunk_*.mp3"))


def _segment_confidence(seg: dict) -> float | None:
    """Whisper's verbose_json segments carry avg_logprob (a log probability,
    so 0 is maximally confident and more negative is less so) rather than a
    0-1 confidence score. This is a rough, deliberately simple mapping - the
    PRD only asks for confidence "if available", not a precise calibration.
    """
    avg_logprob = seg.get("avg_logprob")
    if avg_logprob is None:
        return None
    return max(0.0, min(1.0, 1.0 + float(avg_logprob)))


def _transcribe_chunk(chunk_index: int, chunk_path: str) -> list[dict]:
    client = Groq(api_key=settings.groq_api_key)
    with open(chunk_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=(Path(chunk_path).name, f.read()),
            model=settings.groq_whisper_model,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    offset_s = chunk_index * _CHUNK_SECONDS
    raw_segments = getattr(resp, "segments", None) or []
    return [
        {
            "text": (seg.get("text") or "").strip(),
            "start_ms": int((float(seg.get("start", 0.0)) + offset_s) * 1000),
            "end_ms": int((float(seg.get("end", 0.0)) + offset_s) * 1000),
            "confidence": _segment_confidence(seg),
        }
        for seg in raw_segments
    ]


def transcribe(audio_path: str) -> dict:
    """Splits audio into chunks, transcribes them in parallel, and merges the
    results into a single transcript string plus an ordered segment list.

    Returns {"text": str, "segments": [{text, start_ms, end_ms, confidence,
    start_char, end_char}, ...]} - start_char/end_char are each segment's
    character range within the returned text, which is what lets a claim's
    existing position_in_text be mapped to a timestamp later (see
    char_offset_to_ms below).
    """
    with tempfile.TemporaryDirectory() as chunk_dir:
        chunk_paths = _split_audio(audio_path, chunk_dir)
        if not chunk_paths:
            chunk_paths = [audio_path]

        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_PARALLEL_CHUNKS) as pool:
            futures = [pool.submit(_transcribe_chunk, i, p) for i, p in enumerate(chunk_paths)]
            chunk_segment_lists = [f.result() for f in futures]

    merged_segments: list[dict] = []
    text_parts: list[str] = []
    cursor = 0
    for segments in chunk_segment_lists:
        for seg in segments:
            if not seg["text"]:
                continue
            if text_parts:
                text_parts.append(" ")
                cursor += 1
            start_char = cursor
            text_parts.append(seg["text"])
            cursor += len(seg["text"])
            merged_segments.append({**seg, "start_char": start_char, "end_char": cursor})

    return {"text": "".join(text_parts), "segments": merged_segments}


def char_offset_to_ms(segments: list[dict], char_offset: int | None, edge: str = "start") -> int | None:
    """Maps a character offset in the merged transcript text to a millisecond
    timestamp, via the segment (from transcribe()) whose [start_char, end_char)
    range contains it. edge="start"/"end" picks that segment's start_ms/end_ms -
    used respectively for a claim's start (position_in_text) and end
    (position_in_text + len(quote)) offsets. Returns None when out of range,
    so an unmatched claim just gets no timestamp rather than a wrong one.
    """
    if char_offset is None or char_offset < 0 or not segments:
        return None
    seg = next((s for s in segments if s["start_char"] <= char_offset < s["end_char"]), None)
    if seg is None and char_offset >= segments[-1]["end_char"]:
        seg = segments[-1]
    if seg is None:
        return None
    return seg["end_ms"] if edge == "end" else seg["start_ms"]
