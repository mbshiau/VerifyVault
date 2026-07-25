"use client";

import type { MutableRefObject } from "react";
import { TranscriptSegment } from "@/lib/api";

export function formatTimestamp(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function TranscriptView({
  segments,
  activeSegmentIndex,
  onSeek,
  segmentRefs,
}: {
  segments: TranscriptSegment[];
  activeSegmentIndex: number | null;
  onSeek: (ms: number) => void;
  segmentRefs: MutableRefObject<Map<number, HTMLElement>>;
}) {
  if (segments.length === 0) {
    return <p className="text-sm text-slate-500">No transcript available.</p>;
  }

  return (
    <div className="space-y-4">
      {segments.map((segment, index) => {
        const isActive = activeSegmentIndex === index;
        return (
          <div
            key={index}
            ref={(el) => {
              if (el) segmentRefs.current.set(index, el);
            }}
            className={`rounded-lg p-2 transition-colors ${isActive ? "bg-yellow-100" : ""}`}
          >
            <button
              type="button"
              onClick={() => onSeek(segment.start_ms)}
              className="rounded px-1.5 py-0.5 text-xs font-semibold text-slate-500 underline decoration-slate-300 decoration-2 underline-offset-2 transition hover:bg-slate-200 hover:text-slate-800"
            >
              {formatTimestamp(segment.start_ms)}
            </button>
            <p className="mt-1 whitespace-pre-wrap leading-relaxed text-slate-900">{segment.text}</p>
          </div>
        );
      })}
    </div>
  );
}
