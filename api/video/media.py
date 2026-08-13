import concurrent.futures
import json
import re
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
    # Use a browser-like User-Agent to improve success on platforms like Instagram
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        # Surface the underlying error for diagnostics (still user-friendly)
        raise MediaError(
            f"Could not read this video - it may be private, deleted, age-restricted, or region-locked. (yt-dlp: {e})"
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
        # Use a browser-like User-Agent to improve success on platforms like Instagram
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": raw_template,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
            },
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


def fetch_youtube_transcript(url: str) -> dict | None:
    """Attempts to fetch the official YouTube transcript if available.
    Returns {"text": str, "segments": [{"text": str, "start_ms": int, "end_ms": int}, ...]} or None.
    """
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "writesubtitles": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info or "subtitles" not in info:
                return None
            
            # Try to get English subtitles first, then any available language
            subtitles = info.get("subtitles", {}) or {}
            subs_lang = None
            if "en" in subtitles:
                subs_lang = "en"
            elif "en-US" in subtitles:
                subs_lang = "en-US"
            elif subtitles:
                subs_lang = next(iter(subtitles.keys()))
            
            if not subs_lang:
                return None
            
            sub_list = subtitles.get(subs_lang, [])
            if not sub_list:
                return None
            
            # Parse VTT format (yt-dlp returns VTT by default)
            segments = []
            text_parts = []
            cursor = 0
            
            for sub in sub_list:
                text = (sub.get("text") or "").strip()
                if not text:
                    continue
                
                # Convert timestamps from seconds to milliseconds
                start_ms = int(float(sub.get("start", 0)) * 1000)
                end_ms = int(float(sub.get("end", 0)) * 1000)
                
                if text_parts:
                    text_parts.append(" ")
                    cursor += 1
                
                start_char = cursor
                text_parts.append(text)
                cursor += len(text)
                
                segments.append({
                    "text": text,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_char": start_char,
                    "end_char": cursor,
                })
            
            merged_text = "".join(text_parts)
            return {"text": merged_text, "segments": segments} if segments else None
    except Exception:
        return None


def _add_sentence_punctuation(text: str) -> str:
    """Add periods to sentences that lack ending punctuation."""
    # Split on common sentence boundaries but preserve them
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    result = []
    
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        # Add period if sentence doesn't end with punctuation
        if not re.search(r'[.!?]$', sent):
            sent += '.'
        result.append(sent)
    
    return ' '.join(result)


def _create_sentence_segments(text: str, segments: list[dict]) -> list[dict]:
    """Create segments at sentence boundaries using original segment timestamps.
    
    Maps sentences to the closest available timestamp from Whisper segments.
    """
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    
    new_segments = []
    cursor = 0
    
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        
        # Ensure sentence ends with punctuation
        if not re.search(r'[.!?]$', sent):
            sent += '.'
        
        start_char = cursor
        end_char = cursor + len(sent)
        
        # Find overlapping segments to get timing
        start_ms = None
        end_ms = None
        
        for seg in segments:
            seg_start_char = seg.get("start_char", 0)
            seg_end_char = seg.get("end_char", 0)
            
            # If sentence overlaps with this segment, use its timing
            if seg_start_char < end_char and seg_end_char > start_char:
                if start_ms is None:
                    start_ms = seg.get("start_ms", 0)
                end_ms = seg.get("end_ms", 0)
        
        if start_ms is None:
            start_ms = 0
        if end_ms is None:
            end_ms = start_ms
        
        new_segments.append({
            "text": sent,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "start_char": start_char,
            "end_char": end_char,
        })
        
        cursor = end_char + 1  # +1 for the space between sentences
    
    return new_segments



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

    raw_text = "".join(text_parts)
    
    # Add punctuation and create sentence-level segments
    punctuated_text = _add_sentence_punctuation(raw_text)
    sentence_segments = _create_sentence_segments(punctuated_text, merged_segments)

    return {"text": punctuated_text, "segments": sentence_segments}


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
