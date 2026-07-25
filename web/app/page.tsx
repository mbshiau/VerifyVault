"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAnalysis, submitYoutubeUrl, uploadVideo } from "@/lib/api";

const VIDEO_EXTENSIONS = [".mp4", ".mov", ".m4v", ".webm"];
const VIDEO_ACCEPT = VIDEO_EXTENSIONS.join(",");
const MAX_VIDEO_MB = 500;
const YOUTUBE_URL_RE = /^https?:\/\/(www\.|m\.)?(youtube\.com|youtu\.be)\//i;

type Mode = "text" | "video" | "youtube";

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

  const [youtubeUrl, setYoutubeUrl] = useState("");

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
    }

    if (mode === "youtube") {
      if (!youtubeUrl.trim()) return;
      setLoading(true);
      try {
        const { id } = await submitYoutubeUrl(youtubeUrl.trim(), {
          speaker: speaker.trim() || undefined,
          speechDate: speechDate || undefined,
        });
        router.push(`/analysis/${id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed");
        setLoading(false);
      }
      return;
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
      : mode === "video"
        ? videoFile !== null
        : YOUTUBE_URL_RE.test(youtubeUrl.trim());

  return (
    <main className="mx-auto max-w-7xl px-6 py-12 lg:py-16">
      <div className="max-w-3xl">
        <p className="text-sm uppercase tracking-[0.25em] text-slate-500">VerifyVault</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
          Analyze political text and video with more clarity.
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-600">
          Paste a speech, press release, or statement — or upload a video of one — and get a structured breakdown of
          claims, context, and evidence.
        </p>
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <form
          onSubmit={onSubmit}
          className="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm shadow-slate-200/60 backdrop-blur"
        >
          <div className="mb-6 inline-flex rounded-lg border border-slate-300 bg-slate-50 p-1 text-sm font-medium">
            <button
              type="button"
              onClick={() => setMode("text")}
              className={`rounded-md px-4 py-1.5 transition ${
                mode === "text" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Text
            </button>
            <button
              type="button"
              onClick={() => setMode("video")}
              className={`rounded-md px-4 py-1.5 transition ${
                mode === "video" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Video
            </button>
            <button
              type="button"
              onClick={() => setMode("youtube")}
              className={`rounded-md px-4 py-1.5 transition ${
                mode === "youtube" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              YouTube link
            </button>
          </div>

          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Speaker</span>
                <input
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  placeholder="Jane Smith, Senator"
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                />
              </label>
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Date</span>
                <input
                  type="date"
                  value={speechDate}
                  onChange={(e) => setSpeechDate(e.target.value)}
                  title="Date this was said or written (optional) — leave blank to assume today, set it for older text"
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                />
              </label>
            </div>

            {mode === "text" ? (
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Text to analyze</span>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste a speech, press release, or statement..."
                  className="min-h-[22rem] w-full rounded-xl border border-slate-300 bg-slate-50 p-5 text-base leading-8 text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                  required
                  minLength={20}
                />
              </label>
            ) : (
              <div className="space-y-2">
                <span className="block text-sm font-medium text-slate-700">Video to analyze</span>
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
                  className={`flex min-h-[22rem] flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition ${
                    dragActive ? "border-slate-500 bg-slate-100" : "border-slate-300 bg-slate-50"
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
                      <p className="text-sm font-medium text-slate-900">{videoFile.name}</p>
                      <p className="text-xs text-slate-500">{(videoFile.size / (1024 * 1024)).toFixed(1)} MB</p>
                      {!loading && (
                        <button
                          type="button"
                          onClick={() => pickVideoFile(null)}
                          className="text-xs font-medium text-slate-500 underline hover:text-slate-800"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-slate-700">Drag and drop a video, or</p>
                      <label
                        htmlFor="video-file-input"
                        className="mt-3 cursor-pointer rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-slate-700"
                      >
                        Choose file
                      </label>
                      <p className="mt-3 text-xs text-slate-500">mp4, mov, m4v, webm · up to 500MB · up to 2 hours</p>
                    </>
                  )}

                  {loading && (
                    <div className="mt-5 w-full max-w-xs">
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full bg-slate-900 transition-all"
                          style={{ width: `${Math.round(uploadProgress * 100)}%` }}
                        />
                      </div>
                      <p className="mt-1.5 text-xs text-slate-500">Uploading… {Math.round(uploadProgress * 100)}%</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {mode === "youtube" && (
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">YouTube video URL</span>
                <input
                  type="url"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                />
                <p className="text-xs text-slate-500">
                  Only the audio is used for transcription - the video itself is played back directly from YouTube,
                  never downloaded or re-hosted.
                </p>
              </label>
            )}
          </div>

          <div className="sticky bottom-4 z-20 mt-6 border-t border-slate-200 bg-white/90 pt-4">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-slate-500">The submit button stays visible as you scroll.</p>
              <button
                type="submit"
                disabled={loading || !canSubmit}
                className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-sm shadow-slate-300 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading
                  ? mode === "video"
                    ? "Uploading..."
                    : mode === "youtube"
                      ? "Fetching..."
                      : "Analyzing..."
                  : mode === "video"
                    ? "Upload & analyze"
                    : mode === "youtube"
                      ? "Fetch & analyze"
                      : "Analyze"}
              </button>
            </div>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </div>
        </form>

        <aside className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-slate-50 p-6">
            <h2 className="text-lg font-semibold text-slate-900">What you can analyze</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>• Campaign speeches and debate transcripts</p>
              <p>• Press releases, newsletters, and policy statements</p>
              <p>• Social posts or short public remarks</p>
              <p>• Video of speeches, interviews, debates, or press conferences</p>
              <p>• YouTube links to any of the above</p>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60">
            <h2 className="text-lg font-semibold text-slate-900">Tips</h2>
            <div className="mt-4 space-y-4 text-sm leading-7 text-slate-600">
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
