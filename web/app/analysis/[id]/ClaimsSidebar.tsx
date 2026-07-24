"use client";

import type { MutableRefObject } from "react";
import { Claim } from "@/lib/api";

export function ClaimDetails({ claim }: { claim: Claim }) {
  return (
    <div className="space-y-3 border-t border-neutral-100 px-3 pb-3 pt-2">
      {claim.explanation && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Explanation</p>
          <p className="mt-0.5 text-xs leading-relaxed text-neutral-700">{claim.explanation}</p>
        </div>
      )}

      {claim.context && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Context</p>
          <p className="mt-0.5 text-xs leading-relaxed text-neutral-700">{claim.context}</p>
        </div>
      )}

      {claim.related_entities && claim.related_entities.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Related Entities</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {claim.related_entities.map((name, i) => (
              <span key={i} className="rounded-full bg-neutral-200 px-2 py-0.5 text-xs text-neutral-700">
                {name}
              </span>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Sources</p>
        {claim.sources?.length > 0 ? (
          <div className="mt-1 space-y-2">
            {claim.sources.map((s, i) => {
              let domain = s.url;
              try {
                domain = new URL(s.url).hostname.replace(/^www\./, "");
              } catch {
                // keep raw url if it doesn't parse
              }
              return (
                <a
                  key={i}
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-md p-2 text-xs hover:bg-neutral-50"
                >
                  <span className="flex items-baseline gap-1.5">
                    <span className="truncate font-medium text-blue-700 underline">{s.title || s.url}</span>
                    <span className="flex-none text-neutral-400">· {domain}</span>
                  </span>
                  {s.relation && <span className="mt-0.5 block text-neutral-600">{s.relation}</span>}
                </a>
              );
            })}
          </div>
        ) : (
          <p className="mt-0.5 text-xs text-neutral-500">No sources found.</p>
        )}
      </div>
    </div>
  );
}

export function ClaimsSidebar({
  claims,
  activeIndex,
  onSelect,
  matchedIndexes,
  itemRefs,
  userAddedCount = 0,
}: {
  claims: Claim[];
  activeIndex: number | null;
  onSelect: (index: number) => void;
  matchedIndexes: Set<number>;
  itemRefs: MutableRefObject<Map<number, HTMLElement>>;
  userAddedCount?: number;
}) {
  if (claims.length === 0) {
    return <p className="text-sm text-neutral-500">No claims detected.</p>;
  }

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold">Detected Claims</h2>
      <ul className="space-y-2">
        {claims.map((claim, index) => {
          const isActive = activeIndex === index;
          const isUserAdded = index < userAddedCount;
          return (
            <li
              key={index}
              ref={(el) => {
                if (el) itemRefs.current.set(index, el);
              }}
              className="overflow-hidden rounded-lg border border-neutral-200 bg-white"
            >
              <button
                type="button"
                onClick={() => onSelect(index)}
                className={`flex w-full items-start gap-2 p-3 text-left text-sm transition-colors ${
                  isActive ? (isUserAdded ? "bg-purple-50" : "bg-yellow-50") : "hover:bg-neutral-50"
                }`}
              >
                <span
                  className={`mt-1 h-2 w-2 flex-none rounded-full ${
                    matchedIndexes.has(index) ? (isUserAdded ? "bg-purple-500" : "bg-yellow-500") : "bg-neutral-300"
                  }`}
                  title={matchedIndexes.has(index) ? "Highlighted in text" : "Not matched to a specific sentence"}
                />
                <span className="flex-1">
                  <span className="block font-medium leading-snug">{claim.text}</span>
                  <span className="mt-1 block text-xs text-neutral-500">
                    Confidence: {(claim.confidence * 100).toFixed(0)}%
                  </span>
                </span>
                <span className="mt-0.5 flex-none text-neutral-400">{isActive ? "▾" : "▸"}</span>
              </button>

              {isActive && <ClaimDetails claim={claim} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
