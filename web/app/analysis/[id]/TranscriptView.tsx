"use client";

import type { MutableRefObject } from "react";
import { TranscriptSegment } from "@/lib/api";
import { ClaimHighlightedText } from "@/app/analysis/[id]/ClaimHighlighter";
import type { ClaimSpan } from "@/lib/highlight";

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
  // Optional highlighted-text mode
  text,
  spans,
  activeIndex,
  onSelect,
  markRefs,
}: {
  segments: TranscriptSegment[];
  activeSegmentIndex: number | null;
  onSeek: (ms: number) => void;
  segmentRefs: MutableRefObject<Map<number, HTMLElement>>;
  text?: string;
  spans?: ClaimSpan[];
  activeIndex?: number | null;
  onSelect?: (index: number) => void;
  markRefs?: MutableRefObject<Map<number, HTMLElement>>;
}) {
  if ((!text || text.length === 0) && segments.length === 0) {
    return <p className="text-sm text-slate-500">No transcript available.</p>;
  }

  // If spans/text provided, render paragraph-style highlighted text similar to
  // the plain-text UI but with a left timestamp column for quick seeking.
  if (text && spans) {
    // Build a normalized map of the full text so segments can be located
    function buildNormMap(s: string) {
      let norm = "";
      const map: number[] = [];
      let lastWasSpace = false;
      for (let i = 0; i < s.length; i++) {
        const ch = s[i];
        if (/\s/.test(ch)) {
          if (!lastWasSpace) {
            norm += " ";
            map.push(i);
            lastWasSpace = true;
          }
        } else {
          norm += ch.toLowerCase();
          map.push(i);
          lastWasSpace = false;
        }
      }
      return { norm, map };
    }

    const { norm: fullNorm, map: fullMap } = buildNormMap(text);
    const normalizedSegments = segments.map((s) => s.text.replace(/\s+/g, " ").trim().toLowerCase());

    // Locate each segment in the full normalized text sequentially
    const segmentOffsets: { start: number; end: number }[] = [];
    let searchPos = 0;
    for (const ns of normalizedSegments) {
      if (ns.length === 0) {
        segmentOffsets.push({ start: 0, end: 0 });
        continue;
      }
      const idx = fullNorm.indexOf(ns, searchPos);
      if (idx === -1) {
        // fallback: push zeros to avoid crashes
        segmentOffsets.push({ start: 0, end: 0 });
      } else {
        const start = fullMap[idx];
        const end = fullMap[idx + ns.length - 1] + 1;
        segmentOffsets.push({ start, end });
        searchPos = idx + ns.length;
      }
    }

    function getMsForIndex(globalIndex: number): number | null {
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        const off = segmentOffsets[i];
        if (!off || off.end <= off.start) continue;
        if (globalIndex >= off.start && globalIndex < off.end) {
          if (seg.start_ms == null) return seg.start_ms ?? null;
          const spanLen = off.end - off.start;
          const relative = (globalIndex - off.start) / Math.max(1, spanLen);
          const dur = (seg.end_ms ?? seg.start_ms) - (seg.start_ms ?? 0);
          return Math.round((seg.start_ms ?? 0) + relative * dur);
        }
      }
      return null;
    }

    function onWordClick(globalIndex: number) {
      const ms = getMsForIndex(globalIndex);
      if (ms != null) onSeek(ms);
    }

    const segmentBoundaries = segments
      .map((seg, i) => ({ charOffset: segmentOffsets[i]?.start, ms: seg.start_ms }))
      .filter(
        (b, i): b is { charOffset: number; ms: number } =>
          b.charOffset !== undefined && b.ms != null && (segmentOffsets[i]?.end ?? 0) > (segmentOffsets[i]?.start ?? 0)
      );

    return (
      <div>
        <div className="prose max-w-none">
          <ClaimHighlightedText
            text={text}
            spans={spans}
            activeIndex={activeIndex ?? null}
            onSelect={onSelect ?? (() => {})}
            markRefs={markRefs ?? ({ current: new Map() } as MutableRefObject<Map<number, HTMLElement>>)}
            onWordClick={onWordClick}
            segmentBoundaries={segmentBoundaries}
            onSeek={onSeek}
          />
        </div>
      </div>
    );
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
            <p className="mt-1 whitespace-pre-wrap leading-relaxed text-slate-900">{segment.text}</p>
          </div>
        );
      })}
    </div>
  );
}
