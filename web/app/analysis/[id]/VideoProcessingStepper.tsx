"use client";

const STEPS: { status: string; label: string }[] = [
  { status: "uploading", label: "Uploading" },
  { status: "extracting_audio", label: "Extracting audio" },
  { status: "transcribing", label: "Generating transcript" },
  // Claim detection and source retrieval happen as one call in the existing
  // text pipeline (pipeline.run), so they share a single step here rather
  // than two - there's no natural point to report progress between them.
  { status: "detecting_claims", label: "Detecting claims & finding sources" },
];

export function VideoProcessingStepper({ status }: { status: string }) {
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

  const currentIndex = STEPS.findIndex((s) => s.status === status);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-3 text-sm">
        {STEPS.map((step, index) => {
          const done = currentIndex >= 0 && index < currentIndex;
          const active = index === currentIndex;
          return (
            <li key={step.status} className="flex items-center gap-2">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  done
                    ? "bg-slate-900 text-white"
                    : active
                      ? "bg-amber-400 text-slate-900"
                      : "bg-slate-200 text-slate-500"
                }`}
              >
                {done ? "✓" : index + 1}
              </span>
              <span className={active ? "font-medium text-slate-900" : "text-slate-500"}>{step.label}</span>
              {index < STEPS.length - 1 && <span className="ml-2 text-slate-300">→</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
