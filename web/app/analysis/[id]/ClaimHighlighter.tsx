"use client";

import type { MutableRefObject, ReactNode } from "react";
import { ClaimSpan } from "@/lib/highlight";

export function ClaimHighlightedText({
  text,
  spans,
  activeIndex,
  onSelect,
  markRefs,
  userAddedCount = 0,
}: {
  text: string;
  spans: ClaimSpan[];
  activeIndex: number | null;
  onSelect: (index: number) => void;
  markRefs: MutableRefObject<Map<number, HTMLElement>>;
  userAddedCount?: number;
}) {
  const nodes: ReactNode[] = [];
  let cursor = 0;

  spans.forEach((span) => {
    if (span.start > cursor) nodes.push(text.slice(cursor, span.start));
    const isActive = activeIndex === span.index;
    const isUserAdded = span.index < userAddedCount;
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
        className={`cursor-pointer rounded px-0.5 font-semibold underline decoration-2 underline-offset-2 transition-colors ${
          isUserAdded
            ? isActive
              ? "bg-purple-400 decoration-purple-700"
              : "bg-purple-200 decoration-purple-500 hover:bg-purple-300"
            : isActive
              ? "bg-yellow-400 decoration-yellow-700"
              : "bg-yellow-200 decoration-yellow-500 hover:bg-yellow-300"
        }`}
      >
        {text.slice(span.start, span.end)}
      </mark>
    );
    cursor = span.end;
  });

  if (cursor < text.length) nodes.push(text.slice(cursor));

  return <p className="whitespace-pre-wrap leading-relaxed">{nodes}</p>;
}
