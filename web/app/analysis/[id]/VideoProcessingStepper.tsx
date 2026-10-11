"use client";

import { ProcessingIndicator, ProcessingStep } from "./ProcessingIndicator";

const STEPS: ProcessingStep[] = [
  { key: "uploading", label: "Uploading" },
  { key: "extracting_audio", label: "Extracting audio" },
  // YouTube videos try the official transcript before falling back to Whisper
  // (see video/service.py's run_video_pipeline_task) - this status only ever
  // occurs for youtube-sourced videos, never uploads.
  { key: "fetching_youtube_transcript", label: "Fetching transcript" },
  { key: "transcribing", label: "Generating transcript" },
  // Claim detection and source retrieval happen as one call in the existing
  // text pipeline (pipeline.run), so they share a single step here rather
  // than two - there's no natural point to report progress between them.
  { key: "detecting_claims", label: "Detecting claims & finding sources" },
];

export function VideoProcessingStepper({ status, startedAt }: { status: string; startedAt: string }) {
  if (status.startsWith("failed")) {
    const reason = status.slice("failed:".length).trim();
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <p className="text-sm font-semibold text-red-700">Processing failed</p>
        <p className="mt-1 text-sm text-red-600">
          {reason === "no_speech_detected"
            ? "No speech was detected in this video."
            : "Something went wrong while processing this video. Please try uploading again."}
        </p>
      </div>
    );
  }

  return <ProcessingIndicator steps={STEPS} activeKey={status} startedAt={startedAt} />;
}
