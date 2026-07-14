"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Analysis, getAnalysis } from "@/lib/api";
import { matchClaimsToText } from "@/lib/highlight";
import { ClaimHighlightedText } from "./ClaimHighlighter";
import { ClaimsSidebar } from "./ClaimsSidebar";
import { AnnotationLayer } from "./AnnotationLayer";

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [annotationMode, setAnnotationMode] = useState(false);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());
  const sidebarRefs = useRef<Map<number, HTMLElement>>(new Map());

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const a = await getAnalysis(id);
        if (stop) return;
        setData(a);
        if (a.status === "processing") setTimeout(tick, 1500);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed");
      }
    }
    tick();
    return () => {
      stop = true;
    };
  }, [id]);

  const { spans, unmatched } = useMemo(
    () => (data ? matchClaimsToText(data.text, data.claims) : { spans: [], unmatched: [] }),
    [data]
  );
  const matchedIndexes = useMemo(() => new Set(spans.map((s) => s.index)), [spans]);

  function selectClaim(index: number, source: "text" | "sidebar") {
    setActiveIndex((prev) => {
      const next = prev === index ? null : index;
      if (next !== null) {
        const target = source === "sidebar" ? markRefs.current.get(index) : sidebarRefs.current.get(index);
        target?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return next;
    });
  }

  if (error)
    return (
      <main className="space-y-4 p-8">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900">
          ← Back
        </Link>
        <p className="text-red-600">{error}</p>
      </main>
    );
  if (!data)
    return (
      <main className="space-y-4 p-8">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900">
          ← Back
        </Link>
        <p className="text-neutral-500">Loading…</p>
      </main>
    );

  const processing = data.status === "processing";

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <button
        type="button"
        onClick={() => setAnnotationMode((v) => !v)}
        title={annotationMode ? "Exit annotation mode" : "Add annotations"}
        className={`fixed right-6 top-6 z-50 flex h-11 w-11 items-center justify-center rounded-full text-lg
                    shadow-lg transition-colors ${
                      annotationMode
                        ? "bg-yellow-400 text-neutral-900 hover:bg-yellow-300"
                        : "bg-neutral-900 text-white hover:bg-neutral-700"
                    }`}
      >
        ✏️
      </button>
      {annotationMode && (
        <p className="fixed right-6 top-20 z-50 max-w-[10rem] text-right text-xs text-neutral-500">
          Click anywhere to add a note. Scrolling still works normally.
        </p>
      )}

      <AnnotationLayer active={annotationMode}>
        <div className="space-y-8">
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900"
          >
            ← Back
          </Link>
          <header>
            <h1 className="text-2xl font-semibold">Analysis</h1>
            <p className="text-sm text-neutral-500">
              Status: {data.status}
              {data.speaker && <> · Speaker: {data.speaker}</>}
            </p>
          </header>

          {processing ? (
            <p className="text-neutral-500">Running pipeline…</p>
          ) : (
            <>
              <section>
                <h2 className="mb-2 text-lg font-semibold">Summary</h2>
                <p className="whitespace-pre-wrap leading-relaxed">{data.summary}</p>
              </section>

              {data.topics.length > 0 && (
                <section>
                  <h2 className="mb-2 text-lg font-semibold">Topics</h2>
                  <div className="flex flex-wrap gap-2">
                    {data.topics.map((t) => (
                      <span key={t} className="rounded-full bg-neutral-200 px-3 py-1 text-xs">
                        {t}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              <section className="grid gap-8 md:grid-cols-[1fr_360px] md:items-start">
                <div className="min-w-0">
                  <h2 className="mb-2 text-lg font-semibold">Original Text</h2>
                  <p className="mb-3 text-xs text-neutral-500">
                    Click a{" "}
                    <mark className="bg-yellow-200 px-0.5 font-semibold underline decoration-yellow-500 decoration-2">
                      highlighted
                    </mark>{" "}
                    sentence, or a claim on the right, to see its sources.
                  </p>
                  <div className="md:max-h-[75vh] md:overflow-y-auto md:pr-4">
                    <AnnotationLayer active={annotationMode}>
                      <ClaimHighlightedText
                        text={data.text}
                        spans={spans}
                        activeIndex={activeIndex}
                        onSelect={(i) => selectClaim(i, "text")}
                        markRefs={markRefs}
                      />
                    </AnnotationLayer>
                  </div>
                </div>

                <div className="md:sticky md:top-8 md:max-h-[75vh] md:overflow-y-auto md:pr-1">
                  <AnnotationLayer active={annotationMode}>
                    <ClaimsSidebar
                      claims={data.claims}
                      activeIndex={activeIndex}
                      onSelect={(i) => selectClaim(i, "sidebar")}
                      matchedIndexes={matchedIndexes}
                      itemRefs={sidebarRefs}
                    />
                    {unmatched.length > 0 && (
                      <p className="mt-2 text-xs text-neutral-400">
                        Claims with a gray dot couldn&apos;t be matched to one specific sentence.
                      </p>
                    )}
                  </AnnotationLayer>
                </div>
              </section>

              {data.entities.length > 0 && (
                <section>
                  <h2 className="mb-2 text-lg font-semibold">Entities</h2>
                  <ul className="grid grid-cols-2 gap-2 text-sm">
                    {data.entities.map((e, i) => (
                      <li key={i} className="rounded border border-neutral-200 bg-white px-3 py-2">
                        <span className="font-medium">{e.name}</span>{" "}
                        <span className="text-xs text-neutral-500">({e.type})</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </AnnotationLayer>
    </main>
  );
}
