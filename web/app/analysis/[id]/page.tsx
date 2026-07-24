"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Analysis, Claim, analyzeSelectedClaim, getAnalysis } from "@/lib/api";
import { matchClaimsToText } from "@/lib/highlight";
import { ClaimHighlightedText } from "./ClaimHighlighter";
import { ClaimsSidebar } from "./ClaimsSidebar";
import { AnnotationLayer } from "./AnnotationLayer";
import { EntityDetails } from "./EntityDetails";

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [annotationMode, setAnnotationMode] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [selectedClaims, setSelectedClaims] = useState<Claim[]>([]);
  const [selectedClaimError, setSelectedClaimError] = useState<string | null>(null);
  const [analyzingSelection, setAnalyzingSelection] = useState(false);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());
  const sidebarRefs = useRef<Map<number, HTMLElement>>(new Map());
  const textPanelRef = useRef<HTMLDivElement>(null);

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

  const allClaims = useMemo(() => (data ? [...selectedClaims, ...data.claims] : selectedClaims), [data, selectedClaims]);
  const { spans, unmatched } = useMemo(
    () => (data ? matchClaimsToText(data.text, allClaims) : { spans: [], unmatched: [] }),
    [data, allClaims]
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

  function handleSelectionMouseUp() {
    if (annotationMode || !textPanelRef.current) return;
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;
    const range = selection.getRangeAt(0);
    const container = range.commonAncestorContainer;
    if (!textPanelRef.current.contains(container)) return;
    const next = selection.toString().replace(/\s+/g, " ").trim();
    if (!next) return;
    if (next === selectedText) return;
    setSelectedText(next);
    setSelectedClaimError(null);
  }

  async function handleAnalyzeSelection() {
    if (!data || !selectedText || analyzingSelection) return;
    setAnalyzingSelection(true);
    setSelectedClaimError(null);
    try {
      const result = await analyzeSelectedClaim(data.id, selectedText);
      if (result.is_claim && result.claim) {
        const normalizedQuote = (result.claim.quote || result.claim.text || "").trim().toLowerCase();
        const existingIndexInSelected = selectedClaims.findIndex(
          (c) => ((c.quote || c.text || "").trim().toLowerCase() === normalizedQuote)
        );
        const existingIndexInDetected = data.claims.findIndex(
          (c) => ((c.quote || c.text || "").trim().toLowerCase() === normalizedQuote)
        );
        if (existingIndexInSelected >= 0) {
          setActiveIndex(existingIndexInSelected);
        } else if (existingIndexInDetected >= 0) {
          setActiveIndex(selectedClaims.length + existingIndexInDetected);
        } else {
          const nextSelected = [...selectedClaims, result.claim];
          setSelectedClaims(nextSelected);
          setActiveIndex(nextSelected.length - 1);
        }
      } else {
        setSelectedClaimError(result.reason || "Selected text is not a verifiable, relevant claim.");
      }
    } catch (e) {
      setSelectedClaimError(e instanceof Error ? e.message : "Failed to analyze selected text.");
    } finally {
      setAnalyzingSelection(false);
    }
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
                    sentence, or a claim on the right, to see its sources. You can also select your own sentence and
                    analyze it.
                  </p>
                  <div className="md:max-h-[75vh] md:overflow-y-auto md:pr-4" ref={textPanelRef} onMouseUp={handleSelectionMouseUp}>
                    <AnnotationLayer active={annotationMode}>
                      <ClaimHighlightedText
                        text={data.text}
                        spans={spans}
                        activeIndex={activeIndex}
                        onSelect={(i) => selectClaim(i, "text")}
                        markRefs={markRefs}
                        userAddedCount={selectedClaims.length}
                      />
                    </AnnotationLayer>
                  </div>
                </div>

                <div className="md:sticky md:top-8 md:max-h-[75vh] md:overflow-y-auto md:pr-1">
                  <AnnotationLayer active={annotationMode}>
                    {selectedText && (
                      <section className="mb-3 overflow-hidden rounded-lg border border-neutral-200 bg-white">
                        <div className="space-y-2 p-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                            Selected Sentence
                          </p>
                          <p className="text-sm leading-snug text-neutral-800">{selectedText}</p>
                          <button
                            type="button"
                            onClick={handleAnalyzeSelection}
                            disabled={analyzingSelection}
                            className="rounded-md bg-neutral-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {analyzingSelection ? "Analyzing..." : "Analyze Selected Sentence"}
                          </button>
                          {selectedClaimError && <p className="text-xs text-red-600">{selectedClaimError}</p>}
                        </div>
                      </section>
                    )}
                    <ClaimsSidebar
                      claims={allClaims}
                      activeIndex={activeIndex}
                      onSelect={(i) => selectClaim(i, "sidebar")}
                      matchedIndexes={matchedIndexes}
                      itemRefs={sidebarRefs}
                      userAddedCount={selectedClaims.length}
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
                <EntityDetails entities={data.entity_details || []} />
              )}
            </>
          )}
        </div>
      </AnnotationLayer>
    </main>
  );
}
