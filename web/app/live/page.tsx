"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Analysis,
  getAnalysis,
  getVideoFileUrl,
  submitVideoUrl,
  uploadVideo,
} from "@/lib/api";
import { matchClaimsToText } from "@/lib/highlight";
import { TranscriptView } from "@/app/analysis/[id]/TranscriptView";
import { VideoPlayer } from "@/app/analysis/[id]/VideoPlayer";
import { YouTubePlayer } from "@/app/analysis/[id]/YouTubePlayer";

function formatDate(iso?: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString();
}

export default function LivePage() {
  const [videoUrl, setVideoUrl] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoMode, setVideoMode] = useState<"link" | "upload">("link");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);

  // Reset visible claims when analysis updates (new run)
  useEffect(() => {
    setVisibleClaims([]);
  }, [analysisId]);
  const [status, setStatus] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const videoPlayerRef = useRef<any>(null);
  const segmentRefs = useRef<Map<number, HTMLElement>>(new Map());
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null);
  const [visibleClaims, setVisibleClaims] = useState<any[]>([]);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const pausedBySyncRef = useRef(false);

  // Reveal lead: show claims slightly before or exactly when they start (ms)
  const CLAIM_REVEAL_LEAD_MS = 200;

  // Called by player every ~250ms with current playback ms
  function handleTimeUpdate(ms: number) {
    const segs = analysis?.transcript?.segments ?? [];
    if (segs.length > 0) {
      // Update active segment highlighting
      const idx = segs.findIndex((s) => {
        const start = s.start_ms ?? 0;
        const end = s.end_ms ?? (start + 1000);
        return ms >= start && ms < end;
      });
      setActiveSegmentIndex(idx === -1 ? null : idx);

      // Stall playback if player gets ahead of produced transcript by > buffer
      const latestEnd = segs.reduce((acc, s) => Math.max(acc, s.end_ms ?? s.start_ms ?? 0), 0);
      const bufferMs = 800;
      if ((status?.includes("transcribing") || segs.length > 0) && ms > latestEnd + bufferMs) {
        if (!pausedBySyncRef.current) {
          videoPlayerRef.current?.pause?.();
          pausedBySyncRef.current = true;
        }
      } else if (pausedBySyncRef.current && ms <= latestEnd - 200) {
        // Resume when transcript has caught up slightly
        videoPlayerRef.current?.play?.();
        pausedBySyncRef.current = false;
      }
    }

    // Reveal claims in real time as playback reaches their timestamps
    if (analysis?.claims && analysis.claims.length > 0) {
      const existingIds = new Set(visibleClaims.map((c) => c.id));
      const toReveal = analysis.claims.filter((c) => {
        if (c.start_ms == null) return false;
        if (existingIds.has(c.id)) return false;
        return ms + CLAIM_REVEAL_LEAD_MS >= (c.start_ms ?? 0);
      });
      if (toReveal.length > 0) {
        // Append newly revealed claims in chronological order
        setVisibleClaims((prev) => {
          const merged = [...prev, ...toReveal];
          // keep unique
          const seen = new Set();
          return merged.filter((x) => {
            const key = x.id ?? x.text;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        });
      }
    }
  }

  // Polling effect (faster for near-real-time updates)
  useEffect(() => {
    if (!analysisId) return;
    
    let mounted = true;
    
    const poll = async () => {
      try {
        const a = await getAnalysis(analysisId);
        if (!mounted) return;
        
        setAnalysis(a);
        setStatus(a.status ?? null);
        setError(null);
        
        // Stop polling when complete or failed
        if (a.status?.startsWith("complete") || a.status?.startsWith("failed")) {
          if (pollingRef.current) clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      } catch (err) {
        if (mounted) {
          console.error("Polling error:", err);
          setError(`Error fetching analysis: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };
    
    // Poll immediately and then every 500ms for more responsive updates
    poll();
    pollingRef.current = setInterval(poll, 500);
    
    return () => {
      mounted = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [analysisId]);

  function pickFile(f: File | null) {
    setVideoFile(f);
    setError(null);
  }

  async function startAnalysis() {
    setError(null);
    setIsLoading(true);
    
    try {
      if (videoMode === "link") {
        if (!videoUrl.trim()) {
          setError("Please enter a video URL.");
          setIsLoading(false);
          return;
        }
        console.log("Submitting video URL:", videoUrl.trim());
        const res = await submitVideoUrl(videoUrl.trim(), {});
        console.log("Response:", res);
        setAnalysisId(res.id);
        setStatus("uploading");
        // Try to start playback (user gesture) — allow a short delay for player to mount
        setTimeout(() => {
          try { videoPlayerRef.current?.play?.(); } catch (e) { /* ignore */ }
        }, 300);
      } else {
        if (!videoFile) {
          setError("Please choose a video file to upload.");
          setIsLoading(false);
          return;
        }
        console.log("Uploading video file:", videoFile.name);
        const res = await uploadVideo(videoFile, { 
          onProgress: (p) => setUploadProgress(p) 
        });
        console.log("Upload response:", res);
        setAnalysisId(res.id);
        setStatus("uploading");
        // Try to start playback (user gesture) — allow a short delay for player to mount
        setTimeout(() => {
          try { videoPlayerRef.current?.play?.(); } catch (e) { /* ignore */ }
        }, 300);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("Start analysis error:", {error: err, message: msg, stack: err instanceof Error ? err.stack : "N/A"});
      setError(`Failed to start analysis: ${msg}`);
      setIsLoading(false);
    }
  }

  const playerSrc = useMemo(() => {
    if (analysis?.video?.source === "upload") return getVideoFileUrl(analysis.id);
    if (videoMode === "link" && videoUrl) {
      const m = videoUrl.match(/(?:v=|youtu\.be\/)([A-Za-z0-9_-]{6,})/);
      if (m) return `https://www.youtube.com/embed/${m[1]}?rel=0`;
      return videoUrl;
    }
    if (videoFile) return URL.createObjectURL(videoFile);
    return null;
  }, [analysis, videoMode, videoUrl, videoFile]);

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Live Video Analysis</h1>
        <p className="mt-1 text-sm text-stone-500">Watch a video while claim detection runs in real time. Transcripts update as they're produced and claims appear on the right.</p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <section className="rounded-2xl border border-white/10 bg-white/60 p-6 backdrop-blur-sm shadow-[0_20px_40px_rgba(59,130,246,0.08)]">
          <div className="mb-4 inline-flex rounded-md bg-stone-50 p-1">
            <button
              type="button"
              onClick={() => {
                setVideoMode("link");
                setError(null);
              }}
              className={`rounded-sm px-3 py-1 text-sm font-medium ${videoMode === "link" ? "bg-blueberry-600 text-white" : "text-stone-600 hover:text-stone-900"}`}
            >
              Link
            </button>
            <button
              type="button"
              onClick={() => {
                setVideoMode("upload");
                setError(null);
              }}
              className={`rounded-sm px-3 py-1 text-sm font-medium ${videoMode === "upload" ? "bg-blueberry-600 text-white" : "text-stone-600 hover:text-stone-900"}`}
            >
              Upload
            </button>
          </div>

          <div className="space-y-4">
            {videoMode === "link" ? (
              <div>
                <input
                  type="url"
                  value={videoUrl}
                  onChange={(e) => setVideoUrl(e.target.value)}
                  placeholder="Paste YouTube link (e.g., youtube.com/watch?v=...)"
                  className="w-full rounded-md border border-stone-300 bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-blueberry-600 focus:ring-1 focus:ring-blueberry-600"
                />
              </div>
            ) : (
              <div>
                <input 
                  type="file" 
                  accept="video/*" 
                  onChange={(e) => {
                    pickFile(e.target.files?.[0] ?? null);
                    setUploadProgress(0);
                  }}
                  className="w-full text-sm"
                />
                {uploadProgress > 0 && uploadProgress < 1 && (
                  <div className="mt-3">
                    <div className="h-2 w-full rounded-full bg-stone-200 overflow-hidden">
                      <div 
                        className="h-full bg-blueberry-600 transition-all" 
                        style={{ width: `${Math.round(uploadProgress * 100)}%` }} 
                      />
                    </div>
                    <p className="mt-2 text-xs text-stone-600">Uploading… {Math.round(uploadProgress * 100)}%</p>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="text-sm text-stone-600">
                Status: <span className="font-medium text-stone-900">{status || "idle"}</span>
              </div>
              <button 
                onClick={startAnalysis}
                disabled={isLoading || !analysisId === false}
                className="rounded-md bg-blueberry-600 px-4 py-2 text-sm font-medium text-white hover:bg-blueberry-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {isLoading ? "Starting..." : "Start Analysis"}
              </button>
            </div>

            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                {error}
              </div>
            )}

            {/* Video Player */}
            {analysisId && playerSrc ? (
              <div className="mt-6">
                {analysis?.video?.source === "youtube" || (videoMode === "link" && /(?:v=|youtu\.be\/)/.test(videoUrl)) ? (
                  <YouTubePlayer 
                    ref={videoPlayerRef} 
                    videoId={(analysis?.video?.external_video_id) || (videoUrl.match(/(?:v=|youtu\.be\/)([A-Za-z0-9_-]{6,})/)?.[1] ?? "")} 
                    onTimeUpdate={handleTimeUpdate}
                  />
                ) : (
                  <VideoPlayer 
                    ref={videoPlayerRef} 
                    src={playerSrc} 
                    captions={analysis?.transcript?.segments ?? undefined} 
                    onTimeUpdate={handleTimeUpdate}
                  />
                )}
              </div>
            ) : (
              analysisId ? (
                <div className="min-h-[240px] flex items-center justify-center rounded-md border border-dashed border-stone-300 bg-stone-50 text-stone-500">
                  <p>Loading video...</p>
                </div>
              ) : null
            )}

            {/* Transcript */}
            {analysisId && (
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-stone-900">Transcript (Live)</h3>
                <div className="mt-2 max-h-[240px] overflow-auto rounded-md border border-stone-300 bg-white p-3 text-sm text-stone-800">
                  {analysis?.text && analysis?.claims ? (
                    <TranscriptView
                      segments={analysis.transcript?.segments ?? []}
                      activeSegmentIndex={activeSegmentIndex}
                      onSeek={(ms) => videoPlayerRef.current?.seekTo?.(ms)}
                      segmentRefs={segmentRefs}
                      text={analysis.text}
                      spans={matchClaimsToText(analysis.text, analysis.claims).spans}
                      activeIndex={null}
                      onSelect={() => {}}
                      markRefs={{ current: new Map() }}
                    />
                  ) : analysis?.transcript?.segments && analysis.transcript.segments.length > 0 ? (
                    <div className="space-y-2">
                      {analysis.transcript.segments.map((s, idx) => (
                        <p key={idx} className="text-sm text-stone-700">{s.text}</p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-stone-500">Waiting for transcript...</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Claims Sidebar */}
        <aside className="rounded-2xl border border-white/10 bg-white/60 p-4 backdrop-blur-sm shadow-[0_20px_40px_rgba(59,130,246,0.08)]">
          <h2 className="text-lg font-semibold text-stone-900">Live Claims</h2>
          <p className="mt-1 text-xs text-stone-500">Claims appear here as they're detected.</p>

          {analysisId ? (
            <div className="mt-4 space-y-3 max-h-[70vh] overflow-auto">
              {visibleClaims && visibleClaims.length > 0 ? (
                visibleClaims.map((c, idx) => {
                  return (
                    <article key={c.id || `${idx}-${c.text}`} className="rounded-lg border border-stone-200 bg-white p-3">
                      <h4 className="font-semibold text-sm text-stone-900 line-clamp-2">{c.text}</h4>
                      <div className="mt-2 flex items-center gap-2 text-xs">
                        <span className="text-stone-600">Confidence:</span>
                        <span className="font-medium text-stone-900">{(c.confidence * 100).toFixed(0)}%</span>
                      </div>
                      {c.explanation && (
                        <p className="mt-2 text-xs text-stone-600 line-clamp-3">{c.explanation}</p>
                      )}
                      {c.sources && c.sources.length > 0 && (
                        <div className="mt-2">
                          <div className="text-xs font-medium text-stone-700">Sources</div>
                          <ul className="mt-1 space-y-1">
                            {c.sources.slice(0, 2).map((s, i) => (
                              <li key={i}>
                                <a 
                                  href={s.url} 
                                  target="_blank" 
                                  rel="noreferrer"
                                  className="text-xs text-blueberry-600 hover:underline truncate block"
                                >
                                  {s.title || s.url}
                                </a>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {c.start_ms != null && (
                        <button
                          onClick={() => {
                            if (c.start_ms != null) {
                              videoPlayerRef.current?.seekTo?.(c.start_ms);
                            }
                          }}
                          className="mt-3 text-xs text-blueberry-600 hover:underline"
                        >
                          Jump to claim
                        </button>
                      )}
                    </article>
                  );
                })
              ) : analysis?.claims && analysis.claims.length > 0 ? (
                <p className="text-sm text-stone-500 mt-4">Claims detected; they will appear here as the video plays.</p>
              ) : (
                <p className="text-sm text-stone-500 mt-4">
                  {status?.includes("detecting_claims") || status?.includes("transcribing")
                    ? "Analyzing claims..."
                    : "No claims detected yet"}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-stone-500 mt-4">Start an analysis to see claims appear here.</p>
          )}
        </aside>
      </div>
    </main>
  );
}

