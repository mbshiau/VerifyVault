"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAnalysis, submitVideoUrl, uploadVideo } from "@/lib/api";

const VIDEO_EXTENSIONS = [".mp4", ".mov", ".m4v", ".webm"];
const VIDEO_ACCEPT = VIDEO_EXTENSIONS.join(",");
const MAX_VIDEO_MB = 500;
const SUPPORTED_VIDEO_URL_RE =
  /^https?:\/\/(www\.|m\.|mobile\.)?(youtube\.com|youtu\.be|twitter\.com|x\.com)\//i;

type Mode = "text" | "video";

export default function Home() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [speaker, setSpeaker] = useState("");
  const [speechDate, setSpeechDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [videoUrl, setVideoUrl] = useState("");
  const [videoMode, setVideoMode] = useState<"upload" | "link">("upload");

  function pickVideoFile(file: File | null) {
    setError(null);
    if (!file) {
      setVideoFile(null);
      return;
    }
    const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!VIDEO_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file format '${ext}'. Please upload one of: ${VIDEO_EXTENSIONS.join(", ")}.`);
      setVideoFile(null);
      return;
    }
    if (file.size > MAX_VIDEO_MB * 1024 * 1024) {
      setError(`Video exceeds the ${MAX_VIDEO_MB}MB upload limit.`);
      setVideoFile(null);
      return;
    }
    setVideoFile(file);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (mode === "video") {
      // Handle upload vs link mode using videoMode
      if (videoMode === "upload") {
        if (!videoFile) return;
        setLoading(true);
        setUploadProgress(0);
        try {
          const { id } = await uploadVideo(videoFile, {
            speaker: speaker.trim() || undefined,
            speechDate: speechDate || undefined,
            onProgress: setUploadProgress,
          });
          router.push(`/analysis/${id}`);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed");
          setLoading(false);
        }
        return;
      } else {
        // link mode
        if (!videoUrl.trim()) return;
        setLoading(true);
        try {
          const { id } = await submitVideoUrl(videoUrl.trim(), {
            speaker: speaker.trim() || undefined,
            speechDate: speechDate || undefined,
          });
          router.push(`/analysis/${id}`);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Failed";
          setError(msg);
          setLoading(false);
        }
        return;
      }
    }

    setLoading(true);
    try {
      const a = await createAnalysis(text, speaker.trim(), speechDate || undefined);
      router.push(`/analysis/${a.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setLoading(false);
    }
  }

  const canSubmit =
    mode === "text"
      ? text.length >= 20
      : videoMode === "upload"
        ? videoFile !== null
        : SUPPORTED_VIDEO_URL_RE.test(videoUrl.trim());

  return (
    <main className="mx-auto max-w-7xl px-6 py-12 lg:py-16">
      <div className="max-w-3xl p-6 rounded-2xl bg-white/30 backdrop-blur-sm shadow-[0_20px_40px_rgba(59,130,246,0.16)] border border-white/10">
        <p className="text-sm uppercase tracking-[0.25em] text-stone-500 font-medium">VerifyVault</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blueberry-700 to-blueberry-400 drop-shadow-[0_6px_16px_rgba(59,130,246,0.22)]">
          Analyze political text and video with more clarity.
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-8 text-stone-600">
          Paste a speech, press release, or statement or upload a video of one and get a structured breakdown of
          claims, context, and evidence.
        </p>
        <p className="mt-3 text-xs uppercase tracking-widest text-stone-400">Real-time analysis • Fact verification • Evidence gathering</p>
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-white/10 bg-white/60 backdrop-blur-sm p-6 shadow-[0_20px_40px_rgba(59,130,246,0.16)]"
        >
          <div className="mb-6 inline-flex rounded-md border divider-light bg-stone-50 p-1 text-sm font-medium">
            <button
              type="button"
              onClick={() => setMode("text")}
              className={`rounded-sm px-4 py-1.5 transition ${
                mode === "text" ? "bg-blueberry-600 text-white" : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Text
            </button>
            <button
              type="button"
              onClick={() => setMode("video")}
              className={`rounded-sm px-4 py-1.5 transition ${
                mode === "video" ? "bg-blueberry-600 text-white" : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Video
            </button>
          </div>

          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-black">Speaker</span>
                <p className="text-xs text-stone-400">Optional</p>
                <input
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  placeholder="Jane Smith, Senator"
                  className="w-full rounded-md border divider-light bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-blueberry-600 focus:bg-white"
                />
              </label>
              <label className="block space-y-2">
                <span className="text-sm font-medium text-black">Date</span>
                <p className="text-xs text-stone-400">Optional</p>
                <input
                  type="date"
                  value={speechDate}
                  onChange={(e) => setSpeechDate(e.target.value)}
                  title="Date this was said or written (optional) — leave blank to assume today, set it for older text"
                  className="w-full rounded-md border divider-light bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-blueberry-600 focus:bg-white"
                />
              </label>
            </div>

            {mode === "text" ? (
              <label className="block space-y-2">
                <span className="text-sm font-medium text-black">Text to analyze</span>
                <p className="text-xs text-stone-400">Minimum 20 characters</p>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste a speech, press release, or statement..."
                  className="min-h-[22rem] w-full rounded-lg border divider-light bg-stone-50 p-5 text-base leading-8 text-stone-900 outline-none transition focus:border-blueberry-600 focus:bg-white"
                  required
                  minLength={20}
                />
              </label>
            ) : (
              <div className="space-y-4">
                <div className="inline-flex rounded-md bg-stone-50 p-1">
                  <button
                    type="button"
                    onClick={() => setVideoMode("upload")}
                    className={`rounded-sm px-3 py-1 text-sm font-medium ${videoMode === "upload" ? "bg-blueberry-600 text-white" : "text-stone-600 hover:text-stone-900"}`}
                  >
                    Upload
                  </button>
                  <button
                    type="button"
                    onClick={() => setVideoMode("link")}
                    className={`rounded-sm px-3 py-1 text-sm font-medium ${videoMode === "link" ? "bg-blueberry-600 text-white" : "text-stone-600 hover:text-stone-900"}`}
                  >
                    Link
                  </button>
                </div>

                {videoMode === "upload" ? (
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragActive(true);
                    }}
                    onDragLeave={() => setDragActive(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragActive(false);
                      pickVideoFile(e.dataTransfer.files?.[0] ?? null);
                    }}
                    className={`flex min-h-[14rem] flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition ${
                      dragActive ? "border-blueberry-600 bg-blueberry-50" : "border-divider-light bg-stone-50"
                    }`}
                  >
                    <input
                      id="video-file-input"
                      type="file"
                      accept={VIDEO_ACCEPT}
                      className="hidden"
                      onChange={(e) => pickVideoFile(e.target.files?.[0] ?? null)}
                    />
                    {videoFile ? (
                      <div className="space-y-3">
                        <p className="text-sm font-medium text-black">{videoFile.name}</p>
                        <p className="text-xs text-stone-600">{(videoFile.size / (1024 * 1024)).toFixed(1)} MB</p>
                        {!loading && (
                          <button
                            type="button"
                            onClick={() => pickVideoFile(null)}
                            className="text-xs font-medium text-stone-500 underline hover:text-stone-800"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ) : (
                      <>
                        <p className="text-sm font-medium text-stone-700">Drag and drop a video, or</p>
                        <label
                          htmlFor="video-file-input"
                          className="mt-3 cursor-pointer rounded-md bg-blueberry-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blueberry-700"
                        >
                          Choose file
                        </label>
                      </>
                    )}

                    {loading && (
                      <div className="mt-5 w-full max-w-xs">
                        <div className="progress-premium">
                          <div
                            className="progress-premium-fill"
                            style={{ width: `${Math.round(uploadProgress * 100)}%` }}
                          />
                        </div>
                        <p className="mt-2 text-xs text-stone-600 micro-text-muted">Uploading… {Math.round(uploadProgress * 100)}%</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-black">YouTube or X/Twitter video URL</span>
                    <p className="text-xs text-stone-400">Audio is transcribed, video played from original source</p>
                    <input
                      type="url"
                      value={videoUrl}
                      onChange={(e) => setVideoUrl(e.target.value)}
                      placeholder="https://www.youtube.com/watch?v=... or https://x.com/.../status..."
                      className="w-full rounded-md border divider-light bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-blueberry-600 focus:bg-white"
                    />
                  </label>
                )}
              </div>
            )}

          </div>

          <div className="sticky bottom-4 z-20 mt-6 border-t divider-light bg-white/70 backdrop-blur-sm pt-4">
            <div className="flex items-center justify-between gap-4">
              <p className="text-xs text-stone-500 micro-text">Visible while scrolling</p>
              <button
                type="submit"
                disabled={loading || !canSubmit}
                  className="rounded-md bg-blueberry-600 px-6 py-3 text-sm font-semibold text-white shadow-md shadow-blueberry-400 transition hover:bg-blueberry-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading
                  ? mode === "video"
                    ? videoMode === "upload"
                      ? "Uploading..."
                      : "Fetching..."
                    : "Analyzing..."
                  : mode === "video"
                    ? videoMode === "upload"
                      ? "Upload & analyze"
                      : "Fetch & analyze"
                    : "Analyze"}
              </button>
            </div>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </div>
        </form>

        <aside className="space-y-6">
          <section className="rounded-lg border border-blueberry-200 bg-blueberry-50 p-6 shadow-md shadow-blueberry-200">
            <h2 className="text-lg font-semibold">What you can analyze</h2>
            <p className="mt-1 text-xs text-stone-400 micro-text">Supported content types</p>
            <div className="mt-4 space-y-3 text-sm leading-7 text-stone-700">
              <p>• Campaign speeches and debate transcripts</p>
              <p>• Press releases, newsletters, and policy statements</p>
              <p>• Social posts or short public remarks</p>
              <p>• Video of speeches, interviews, debates, or press conferences</p>
              <p>• YouTube or X/Twitter links to any of the above</p>
            </div>
          </section>

          <section className="rounded-lg border border-blueberry-200 bg-blueberry-50 p-6 shadow-md shadow-blueberry-200">
            <h2 className="text-lg font-semibold">Tips for best results</h2>
            <p className="mt-1 text-xs text-stone-400 micro-text">Optimization guide</p>
            <div className="mt-4 space-y-4 text-sm leading-7 text-stone-700">
              <p>Keep the source text intact so claims can be matched cleanly.</p>
              <p>Add a speaker and date when you know them to improve context.</p>
              <p>Whitespace and line breaks are fine — they make review easier.</p>
              <p>For video, transcription and claim detection can take a few minutes for longer uploads.</p>
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}
