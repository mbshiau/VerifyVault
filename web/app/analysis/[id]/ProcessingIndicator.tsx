"use client";

import { useEffect, useState } from "react";

export type ProcessingStep = { key: string; label: string };

const DEFAULT_TIPS = [
  "Checking sources against 25+ curated outlets, from wire services to fact-checkers.",
  "Government and .gov/.edu sources get a trust nudge over unverified blogs.",
  "Each claim is checked for the specific state or jurisdiction it's actually about.",
  "Dates matter - a 10-year-old article can't verify a claim about this year.",
  "Rhetorical flourishes are stripped out so search engines match the actual substance.",
  "A speaker's own site is never counted as independent verification of their claims.",
];

function Dots() {
  return (
    <span className="ml-1 inline-flex gap-0.5 align-baseline">
      <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
      <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
      <span className="h-1 w-1 animate-bounce rounded-full bg-current" />
    </span>
  );
}

/**
 * Shared, animated "still working" indicator for both video and text
 * analysis. Video has real discrete backend stages, so it passes
 * `activeKey` driven by the actual polled status. Text analysis runs as one
 * pipeline.run() call with no intermediate status to report, so it instead
 * passes `autoAdvanceMs` and self-advances through the given steps on a
 * timer - an honest approximation (it holds on the last step rather than
 * looping, since it has no way to know true completion ahead of the real
 * status flipping to "complete") rather than a precise progress signal.
 */
export function ProcessingIndicator({
  steps,
  activeKey,
  autoAdvanceMs,
  startedAt,
  tips = DEFAULT_TIPS,
}: {
  steps: ProcessingStep[];
  activeKey?: string;
  autoAdvanceMs?: number;
  startedAt: string;
  tips?: string[];
}) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [autoIndex, setAutoIndex] = useState(0);
  const [tipIndex, setTipIndex] = useState(0);

  useEffect(() => {
    const startMs = new Date(startedAt).getTime();
    const update = () => setElapsedSeconds(Math.max(0, Math.round((Date.now() - startMs) / 1000)));
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  useEffect(() => {
    if (!autoAdvanceMs) return;
    const interval = setInterval(() => {
      setAutoIndex((i) => Math.min(i + 1, steps.length - 1));
    }, autoAdvanceMs);
    return () => clearInterval(interval);
  }, [autoAdvanceMs, steps.length]);

  useEffect(() => {
    const interval = setInterval(() => setTipIndex((i) => (i + 1) % tips.length), 4500);
    return () => clearInterval(interval);
  }, [tips.length]);

  const currentIndex = activeKey ? steps.findIndex((s) => s.key === activeKey) : autoIndex;
  // Nudge toward 90% over ~45s of elapsed time rather than a linear fill, so
  // the bar keeps visibly creeping for genuinely long analyses instead of
  // sitting still once it reaches a plateau - it never claims 100% itself
  // since only the real "complete" status (which unmounts this) means done.
  const fillPercent = Math.min(90, 12 + elapsedSeconds * 1.8);

  return (
    <div className="rounded-xl p-6 glass-panel">
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-3 text-sm">
        {steps.map((step, index) => {
          const done = currentIndex >= 0 && index < currentIndex;
          const active = index === currentIndex;
          return (
            <li key={step.key} className="flex items-center gap-2">
              <span className="relative flex h-6 w-6 shrink-0 items-center justify-center">
                {active && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blueberry-400 opacity-60" />
                )}
                <span
                  className={`relative flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-300 ${
                    done
                      ? "bg-slate-900 text-white"
                      : active
                        ? "bg-blueberry-500 text-white"
                        : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {done ? "✓" : index + 1}
                </span>
              </span>
              <span className={`flex items-center ${active ? "font-medium text-slate-900" : "text-slate-500"}`}>
                {step.label}
                {active && <Dots />}
              </span>
              {index < steps.length - 1 && (
                <span className={`ml-1 h-px w-6 transition-colors duration-500 ${done ? "bg-slate-900" : "bg-slate-300"}`} />
              )}
            </li>
          );
        })}
      </ol>

      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-blueberry-100">
        <div
          className="relative h-full rounded-full bg-gradient-to-r from-blueberry-600 to-blueberry-500 transition-[width] duration-700 ease-out"
          style={{ width: `${fillPercent}%` }}
        >
          <span className="absolute inset-0 w-1/3 bg-white/40 animate-shimmer-sweep" />
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-4">
        <p key={tipIndex} className="animate-fade-in text-xs text-stone-500">
          {tips[tipIndex]}
        </p>
        <p className="shrink-0 text-xs text-slate-400">{elapsedSeconds}s elapsed</p>
      </div>
    </div>
  );
}
