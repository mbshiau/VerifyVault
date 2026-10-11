"use client";

import { useEffect, useState } from "react";

// Text analysis runs claim extraction, source search, and confidence scoring
// as one pipeline.run() call on the backend with no intermediate status - so
// unlike VideoProcessingStepper (which has real discrete stages to report),
// this can't show genuine step-by-step progress. An elapsed-time counter is
// used instead of a fake staged progress bar, since claim extraction alone
// can legitimately take 20-40s on a longer text and a static "Running
// pipeline…" message otherwise looks indistinguishable from a hung request.
export function TextProcessingIndicator({ startedAt }: { startedAt: string }) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const startMs = new Date(startedAt).getTime();
    const update = () => setElapsedSeconds(Math.max(0, Math.round((Date.now() - startMs) / 1000)));
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  return (
    <div className="rounded-xl p-6 glass-panel">
      <div className="flex items-center gap-3">
        <span className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
        <div>
          <p className="font-medium text-slate-900">Detecting claims & finding sources…</p>
          <p className="mt-0.5 text-sm text-slate-500">
            Longer texts can take up to a minute - {elapsedSeconds}s elapsed
          </p>
        </div>
      </div>
    </div>
  );
}
