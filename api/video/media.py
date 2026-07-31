import concurrent.futures
import json
import subprocess
import tempfile
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import html

import requests
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


def fetch_youtube_captions(url: str, prefer_langs: list[str] | None = None) -> dict | None:
    """Attempts to fetch captions/subtitles for a YouTube URL using yt-dlp's
    metadata. Returns {'text': str, 'segments': [{text,start_ms,end_ms,start_char,end_char}, ...]}
    or None when no usable captions are found.

    Uses automatic captions first (if available) then falls back to uploaded
    subtitles. Prefers languages in prefer_langs (list of 'en', 'es', ...).
    """
    prefer_langs = prefer_langs or ["en"]
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    if not info:
        return None

    # Inspect automatic_captions then subtitles
    tracks = info.get("automatic_captions") or {}
    use_auto = True
    if not tracks:
        tracks = info.get("subtitles") or {}
        use_auto = False
    if not tracks:
        return None

    # Choose language
    lang = None
    for pref in prefer_langs:
        if pref in tracks:
            lang = pref
            break
    if lang is None:
        # pick first available
        lang = next(iter(tracks.keys()), None)
    if lang is None:
        return None

    entries = tracks.get(lang) or []
    if not entries:
        return None

    # Prefer vtt or ttml if available
    track = None
    for e in entries:
        if (e.get("ext") or "").lower() in ("vtt", "ttml", "xml"):
            track = e
            break
    if track is None:
        track = entries[0]

    track_url = track.get("url")
    if not track_url:
        return None

    try:
        r = requests.get(track_url, timeout=15)
        if not r.ok:
            return None
        body = r.text
    except Exception:
        return None

    segments = []
    # Try VTT first
    segments = _parse_vtt_to_segments(body)
    if not segments:
        # Try TTML/XML
        segments = _parse_ttml_to_segments(body)
    if not segments:
        return None

    # Build merged text with start_char/end_char offsets
    text_parts: list[str] = []
    cursor = 0
    merged_segments: list[dict] = []
    for seg in segments:
        t = seg.get("text", "").strip()
        if not t:
            continue
        if text_parts:
            text_parts.append(" ")
            cursor += 1
        start_char = cursor
        text_parts.append(t)
        cursor += len(t)
        merged_segments.append({
            "text": t,
            "start_ms": seg.get("start_ms"),
            "end_ms": seg.get("end_ms"),
            "start_char": start_char,
            "end_char": cursor,
        })

    return {"text": "".join(text_parts), "segments": merged_segments}


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


def _parse_vtt_to_segments(vtt_text: str) -> list[dict]:
    cues = []
    lines = [l.strip() for l in vtt_text.splitlines()]
    i = 0
    time_re = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d{3}|\d{1}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}|\d{1}:\d{2}\.\d{3})")
    while i < len(lines):
        m = time_re.match(lines[i])
        if m:
            start_s = m.group(1)
            end_s = m.group(2)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i]:
                text_lines.append(lines[i])
                i += 1
            text = " ".join(text_lines).strip()
            def ts_to_ms(ts: str) -> int:
                parts = ts.split(":")
                if len(parts) == 3:
                    h, m, s = parts
                    sec, ms = s.split(".")
                    total = int(h) * 3600 + int(m) * 60 + int(sec)
                    return total * 1000 + int(ms)
                else:
                    m, s = parts
                    sec, ms = s.split(".")
                    total = int(m) * 60 + int(sec)
                    return total * 1000 + int(ms)
            cues.append({"text": html.unescape(text), "start_ms": ts_to_ms(start_s), "end_ms": ts_to_ms(end_s)})
        else:
            i += 1
    return cues


def _parse_ttml_to_segments(ttml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(ttml_text)
    except ET.ParseError:
        return []
    # namespace-insensitive search for <p> elements with begin/dur or begin/end
    cues = []
    for p in root.iter():
        tag = p.tag.lower()
        if tag.endswith('p'):
            text = ''.join(p.itertext()).strip()
            begin = p.attrib.get('begin') or p.attrib.get('start')
            end = p.attrib.get('end')
            dur = p.attrib.get('dur')
            if begin is None:
                continue
            def time_to_ms(t: str) -> int:
                # supports seconds (e.g., 12.34s) or hh:mm:ss.ms
                if t.endswith('s'):
                    return int(float(t[:-1]) * 1000)
                parts = t.split(':')
                if len(parts) == 3:
                    h, m, s = parts
                    sec = float(s)
                    total = int(h) * 3600 + int(m) * 60 + int(sec)
                    return int(total * 1000)
                return int(float(t) * 1000)
            start_ms = time_to_ms(begin)
            if end:
                end_ms = time_to_ms(end)
            elif dur:
                end_ms = start_ms + time_to_ms(dur)
            else:
                end_ms = start_ms + 1000
            cues.append({"text": html.unescape(text), "start_ms": start_ms, "end_ms": end_ms})
    return cues


def transcribe_stream(audio_path: str, on_chunk_callback, segment_seconds: int = 15):
    """Transcribes audio chunk-by-chunk and calls on_chunk_callback with
    the current merged transcript after each chunk. The callback receives a
    dict like {"text": str, "segments": [...] } so callers can persist
    partial transcripts and run incremental claim detection.

    This runs sequentially (one chunk after another) to produce ordered
    incremental updates suitable for near-real-time UIs.

    segment_seconds: chunk length in seconds for ffmpeg segmentation. Use
    small values (e.g., 1-3) for near-real-time updates, but note this
    increases transcription calls and cost.
    """
    with tempfile.TemporaryDirectory() as chunk_dir:
        pattern = str(Path(chunk_dir) / "chunk_%04d.mp3")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    audio_path,
                    "-f",
                    "segment",
                    "-segment_time",
                    str(segment_seconds),
                    "-c",
                    "copy",
                    pattern,
                ],
                check=True,
                capture_output=True,
                timeout=1800,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise MediaError("Failed to prepare audio for transcription.") from e

        chunk_paths = sorted(str(p) for p in Path(chunk_dir).glob("chunk_*.mp3"))
        if not chunk_paths:
            chunk_paths = [audio_path]

        merged_segments: list[dict] = []
        text_parts: list[str] = []
        cursor = 0

        for i, chunk_path in enumerate(chunk_paths):
            segments = _transcribe_chunk(i, chunk_path)
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

            # Call the callback with a shallow copy of segments to avoid
            # accidental mutation by callers.
            on_chunk_callback({"text": "".join(text_parts), "segments": merged_segments.copy()})


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
