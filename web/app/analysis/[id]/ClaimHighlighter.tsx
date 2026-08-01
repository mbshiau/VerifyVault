"use client";

import type { MutableRefObject, ReactNode } from "react";
import { ClaimSpan } from "@/lib/highlight";
import { formatTimestamp } from "./TranscriptView";

export type SegmentBoundary = { charOffset: number; ms: number };

export function ClaimHighlightedText({
  text,
  spans,
  activeIndex,
  onSelect,
  markRefs,
  onWordClick,
  segmentBoundaries,
  onSeek,
}: {
  text: string;
  spans: ClaimSpan[];
  activeIndex: number | null;
  onSelect: (index: number) => void;
  markRefs: MutableRefObject<Map<number, HTMLElement>>;
  onWordClick?: (globalIndex: number) => void;
  // Video-transcript mode only: renders a clickable "⏱ 0:13"-style marker
  // at each transcript segment's start, in document order alongside the
  // claim highlighting - onSeek jumps the video straight to that segment,
  // no reverse char-offset lookup required since the ms is already known.
  segmentBoundaries?: SegmentBoundary[];
  onSeek?: (ms: number) => void;
}) {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let boundaryIdx = 0;
  const boundaries = segmentBoundaries ?? [];

  function flushBoundaries(out: ReactNode[], upToGlobalIndex: number) {
    while (boundaryIdx < boundaries.length && boundaries[boundaryIdx].charOffset <= upToGlobalIndex) {
      const b = boundaries[boundaryIdx];
      out.push(
        <span key={`ts-${b.charOffset}`} className="mt-3 block first:mt-0">
          <button
            type="button"
            className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-300"
            onMouseDown={(e) => e.preventDefault()}
            onClick={(e) => {
              e.stopPropagation();
              onSeek && onSeek(b.ms);
            }}
          >
            ⏱ {formatTimestamp(b.ms)}
          </button>
        </span>
      );
      boundaryIdx++;
    }
  }

  function renderTokens(sliceText: string, baseIndex: number) {
    const out: ReactNode[] = [];
    const re = /(\S+|\s+)/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(sliceText))) {
      const token = m[0];
      const startInSlice = m.index;
      const globalIndex = baseIndex + startInSlice;
      flushBoundaries(out, globalIndex);
      if (/^\s+$/.test(token)) {
        out.push(token);
      } else {
        out.push(
          <span
            key={`${baseIndex}-${startInSlice}`}
            className={`inline-block ${onWordClick ? 'cursor-pointer' : ''}`}
            onMouseDown={onWordClick ? (e) => e.preventDefault() : undefined}
            onClick={(e) => { e.stopPropagation(); if (onWordClick) onWordClick(globalIndex); }}
            role={onWordClick ? "button" : undefined}
            tabIndex={onWordClick ? 0 : undefined}
          >
            {token}
          </span>
        );
      }
    }
    return out;
  }

  spans.forEach((span) => {
    if (span.start > cursor) nodes.push(...renderTokens(text.slice(cursor, span.start), cursor));
    // Flush any boundary sitting exactly at the span's start before opening
    // the <mark> below, so it renders as a plain marker rather than getting
    // swept inside the highlight's yellow background.
    flushBoundaries(nodes, span.start);
    const isActive = activeIndex === span.index;
    const isUserAdded = span.claim.source === "user_selected";
    const markedTokens = renderTokens(text.slice(span.start, span.end), span.start);
    nodes.push(
      <mark
        key={span.index}
        ref={(el) => {
          if (el) markRefs.current.set(span.index, el);
        }}
        role="button"
        tabIndex={0}
        onClick={() => onSelect(span.index)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(span.index);
          }
        }}
        className={`cursor-pointer rounded px-0.5 font-semibold transition-colors ${
          isUserAdded
            ? isActive
              ? "bg-purple-400 decoration-purple-700"
              : "bg-purple-200 decoration-purple-500 hover:bg-purple-300"
            : isActive
              ? "bg-yellow-400 decoration-yellow-700"
              : "bg-yellow-200 decoration-yellow-500 hover:bg-yellow-300"
        }`}
      >
        {markedTokens}
      </mark>
    );
    cursor = span.end;
  });

  if (cursor < text.length) nodes.push(...renderTokens(text.slice(cursor), cursor));
  flushBoundaries(nodes, text.length);

  return <p className="whitespace-pre-wrap leading-relaxed">{nodes}</p>;
}
