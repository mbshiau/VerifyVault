"use client";

import type { MutableRefObject, ReactNode } from "react";
import { ClaimSpan } from "@/lib/highlight";

export function ClaimHighlightedText({
  text,
  spans,
  activeIndex,
  onSelect,
  markRefs,
  onWordClick,
}: {
  text: string;
  spans: ClaimSpan[];
  activeIndex: number | null;
  onSelect: (index: number) => void;
  markRefs: MutableRefObject<Map<number, HTMLElement>>;
  onWordClick?: (globalIndex: number) => void;
}) {
  const nodes: ReactNode[] = [];
  let cursor = 0;

  function renderTokens(sliceText: string, baseIndex: number) {
    const out: ReactNode[] = [];
    const re = /(\S+|\s+)/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(sliceText))) {
      const token = m[0];
      const startInSlice = m.index;
      const globalIndex = baseIndex + startInSlice;
      if (/^\s+$/.test(token)) {
        out.push(token);
      } else {
        out.push(
          <span
            key={`${baseIndex}-${startInSlice}`}
            className="inline-block cursor-pointer"
            onMouseDown={(e) => e.preventDefault()}
            onClick={(e) => { e.stopPropagation(); onWordClick && onWordClick(globalIndex); }}
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

  return <p className="whitespace-pre-wrap leading-relaxed">{nodes}</p>;
}
