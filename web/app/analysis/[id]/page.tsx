"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Analysis, Claim, Source, analyzeSelectedClaim, getAnalysis } from "@/lib/api";
import { matchClaimsToText } from "@/lib/highlight";
import { useAuth } from "@/lib/auth";
import { SaveGuestAnalysisBanner } from "@/components/SaveGuestAnalysisBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ClaimHighlightedText } from "./ClaimHighlighter";
import { AnnotationLayer } from "./AnnotationLayer";
import { EntityDetails } from "./EntityDetails";

type SnippetTarget = {
  source: Source;
  claimText: string;
  claimIndex: number;
  sourceIndex: number;
};

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [selectedClaimIndex, setSelectedClaimIndex] = useState(0);
  const [expandedClaimIndex, setExpandedClaimIndex] = useState<number | null>(0);
  const [annotationMode, setAnnotationMode] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [selectionRect, setSelectionRect] = useState<{ top: number; left: number } | null>(null);
  const [selectedClaims, setSelectedClaims] = useState<Claim[]>([]);
  const [selectedClaimError, setSelectedClaimError] = useState<string | null>(null);
  const [analyzingSelection, setAnalyzingSelection] = useState(false);
  const [duplicateClaimIndex, setDuplicateClaimIndex] = useState<number | null>(null);
  const [copiedClaimIndex, setCopiedClaimIndex] = useState<number | null>(null);
  const [snippetTarget, setSnippetTarget] = useState<SnippetTarget | null>(null);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());
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
  const displayOrder = useMemo(
    () => [...spans.map((s) => s.index), ...unmatched.map((u) => u.index)],
    [spans, unmatched]
  );
  const selectedClaim = allClaims[selectedClaimIndex] ?? null;

  useEffect(() => {
    if (allClaims.length === 0) {
      setSelectedClaimIndex(0);
      setExpandedClaimIndex(null);
      return;
    }
    if (selectedClaimIndex >= allClaims.length) {
      setSelectedClaimIndex(0);
      setExpandedClaimIndex(0);
    }
  }, [allClaims.length, selectedClaimIndex]);

  function selectClaim(index: number, source: "text" | "sidebar") {
    setSelectedClaimIndex(index);
    setExpandedClaimIndex(index);
    setActiveIndex((prev) => {
      const next = prev === index ? null : index;
      if (next !== null) {
        const target = source === "sidebar" ? markRefs.current.get(index) : markRefs.current.get(index);
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

    for (const [index, el] of markRefs.current.entries()) {
      if (range.intersectsNode(el)) {
        selection.removeAllRanges();
        setDuplicateClaimIndex(index);
        return;
      }
    }

    const rect = range.getBoundingClientRect();
    const panelRect = textPanelRef.current.getBoundingClientRect();
    setSelectionRect({
      top: rect.top - panelRect.top + textPanelRef.current.scrollTop,
      left: rect.left - panelRect.left + rect.width / 2,
    });
    setSelectedText(next);
    setSelectedClaimError(null);
  }

  function dismissSelection() {
    setSelectedText("");
    setSelectionRect(null);
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
          setSelectedClaimIndex(existingIndexInSelected);
        } else if (existingIndexInDetected >= 0) {
          setSelectedClaimIndex(selectedClaims.length + existingIndexInDetected);
        } else {
          const nextSelected = [...selectedClaims, result.claim];
          setSelectedClaims(nextSelected);
          setSelectedClaimIndex(nextSelected.length - 1);
          setExpandedClaimIndex(nextSelected.length - 1);
        }
        setSelectedText("");
        setSelectionRect(null);
      } else {
        setSelectedClaimError(result.reason || "Selected text is not a verifiable, relevant claim.");
      }
    } catch (e) {
      setSelectedClaimError(e instanceof Error ? e.message : "Failed to analyze selected text.");
    } finally {
      setAnalyzingSelection(false);
    }
  }

  async function copyClaim(claim: Claim, index: number) {
    await navigator.clipboard.writeText(claim.text);
    setCopiedClaimIndex(index);
    window.setTimeout(() => setCopiedClaimIndex((current) => (current === index ? null : current)), 1200);
  }

  if (error)
    return (
      <main className="space-y-4 p-8">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
          ← Back
        </Link>
        <p className="text-red-600">{error}</p>
      </main>
    );
  if (!data)
    return (
      <main className="space-y-4 p-8">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
          ← Back
        </Link>
        <p className="text-slate-500">Loading…</p>
      </main>
    );

  const processing = data.status === "processing";

  return (
    <main className="mx-auto max-w-7xl px-6 py-10 lg:py-12">
      <div className="flex flex-col gap-5 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
            ← Back
          </Link>
          <div>
            <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Analysis</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{data.title}</h1>
            <p className="mt-2 text-sm text-slate-500">
              Status: {data.status}
              {data.speaker && <> · Speaker: {data.speaker}</>}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setAnnotationMode((v) => !v)}
          title={annotationMode ? "Exit annotation mode" : "Add annotations"}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            annotationMode
              ? "bg-amber-300 text-slate-900 hover:bg-amber-200"
              : "bg-slate-900 text-white hover:bg-slate-700"
          }`}
        >
          {annotationMode ? "Annotation on" : "Annotate"}
        </button>
      </div>

      {annotationMode && (
        <p className="mt-4 max-w-sm text-xs text-slate-500">Click anywhere to add a note. Scrolling still works normally.</p>
      )}

      {!authLoading && !user && data.user_id === null && <SaveGuestAnalysisBanner analysisId={data.id} />}

      {processing ? (
        <p className="mt-8 text-slate-500">Running pipeline…</p>
      ) : (
        <AnnotationLayer active={annotationMode}>
          <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.9fr)]">
            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-slate-900">Original text</h2>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  Click a highlighted claim to inspect it, or select new text to analyze it.
                </p>
              </div>
              <div
                className="relative max-h-[78vh] overflow-y-auto rounded-xl bg-slate-50 p-5"
                ref={textPanelRef}
                onMouseUp={handleSelectionMouseUp}
              >
                <ClaimHighlightedText
                  text={data.text}
                  spans={spans}
                  activeIndex={activeIndex}
                  onSelect={(i) => selectClaim(i, "text")}
                  markRefs={markRefs}
                />

                {selectedText && selectionRect && (
                  <div
                    className="absolute z-20 w-80 -translate-x-1/2 -translate-y-[calc(100%+10px)] rounded-lg border border-slate-200 bg-white p-4 shadow-xl shadow-slate-200/80"
                    style={{ top: selectionRect.top, left: selectionRect.left }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Selected text</p>
                      <button
                        type="button"
                        onClick={dismissSelection}
                        aria-label="Dismiss"
                        className="-mr-1 -mt-1 rounded-md px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                      >
                        ×
                      </button>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-800">{selectedText}</p>
                    <button
                      type="button"
                      onClick={handleAnalyzeSelection}
                      disabled={analyzingSelection}
                      className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {analyzingSelection ? "Analyzing..." : "Analyze selected text"}
                    </button>
                    {selectedClaimError && <p className="mt-2 text-xs text-red-600">{selectedClaimError}</p>}
                    <div className="absolute left-1/2 top-full h-3 w-3 -translate-x-1/2 -translate-y-1/2 rotate-45 border-b border-r border-slate-200 bg-white" />
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-slate-900">Detected claims</h2>
                <p className="mt-1 text-sm leading-6 text-slate-500">Expandable cards with claim text, metadata, and evidence.</p>
              </div>

              <div className="space-y-3">
                {allClaims.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
                    No claims detected.
                  </p>
                ) : (
                  allClaims.map((claim, index) => {
                    const isSelected = selectedClaimIndex === index;
                    const isExpanded = expandedClaimIndex === index;
                    const isUserAdded = claim.source === "user_selected";
                    return (
                      <article
                        key={index}
                        className={`rounded-xl border bg-slate-50/80 p-4 transition hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white hover:shadow-md hover:shadow-slate-200/60 ${
                          isSelected ? "border-slate-400 ring-1 ring-slate-300" : "border-slate-200"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <button
                            type="button"
                            onClick={() => selectClaim(index, "sidebar")}
                            className="flex-1 text-left"
                          >
                            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                              <span className={`h-2 w-2 rounded-sm ${isUserAdded ? "bg-sky-500" : "bg-amber-500"}`} />
                              Claim {index + 1}
                            </div>
                            <p className="mt-2 text-sm leading-7 text-slate-900">{claim.text}</p>
                            <p className="mt-3 text-xs text-slate-500">
                              Confidence {(claim.confidence * 100).toFixed(0)}%
                            </p>
                          </button>

                          <div className="flex flex-col gap-2">
                            <button
                              type="button"
                              onClick={() => copyClaim(claim, index)}
                              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
                            >
                              {copiedClaimIndex === index ? "Copied" : "Copy claim"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedClaimIndex(index);
                                setExpandedClaimIndex(isExpanded ? null : index);
                              }}
                              className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700"
                            >
                              {isExpanded ? "Collapse" : "Expand"}
                            </button>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-4 space-y-4 border-t border-slate-200 pt-4">
                            {claim.explanation && (
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Explanation</p>
                                <p className="mt-2 text-sm leading-7 text-slate-700">{claim.explanation}</p>
                              </div>
                            )}

                            {claim.context && (
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Context</p>
                                <p className="mt-2 text-sm leading-7 text-slate-700">{claim.context}</p>
                              </div>
                            )}

                            {claim.related_entities && claim.related_entities.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Related entities</p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {claim.related_entities.map((entity) => (
                                    <span key={entity} className="rounded-lg bg-slate-200 px-3 py-1 text-xs text-slate-700">
                                      {entity}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {claim.sources?.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Evidence sources</p>
                                <div className="mt-2 space-y-2">
                                  {claim.sources.map((source, sourceIndex) => {
                                    let domain = source.url;
                                    try {
                                      domain = new URL(source.url).hostname.replace(/^www\./, "");
                                    } catch {
                                      // keep the raw URL if parsing fails
                                    }
                                    return (
                                      <article
                                        key={`${source.url}-${sourceIndex}`}
                                        className="rounded-lg border border-slate-200 bg-slate-50 p-3 transition hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white"
                                      >
                                        <div className="flex items-start justify-between gap-3">
                                          <div>
                                            <a
                                              href={source.url}
                                              target="_blank"
                                              rel="noreferrer"
                                              className="text-sm font-semibold text-slate-900 underline decoration-slate-300 decoration-2 underline-offset-4 hover:text-slate-700"
                                            >
                                              {source.title || source.url}
                                            </a>
                                            <p className="mt-1 text-xs text-slate-500">{domain}</p>
                                          </div>
                                          {source.retrieval_score != null && (
                                            <span className="rounded-lg bg-slate-200 px-2.5 py-1 text-xs text-slate-700">
                                              {(source.retrieval_score * 100).toFixed(0)}%
                                            </span>
                                          )}
                                        </div>
                                        {source.relation && (
                                          <p className="mt-2 text-sm leading-6 text-slate-700">{source.relation}</p>
                                        )}
                                        <div className="mt-3 flex flex-wrap items-center gap-2">
                                          <button
                                            type="button"
                                            onClick={() =>
                                              setSnippetTarget({
                                                source,
                                                claimText: claim.text,
                                                claimIndex: index,
                                                sourceIndex,
                                              })
                                            }
                                            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
                                          >
                                            View source snippet
                                          </button>
                                        </div>
                                      </article>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </article>
                    );
                  })
                )}
              </div>
            </section>
          </div>

          {data.entities.length > 0 && (
            <div className="mt-6">
              <EntityDetails entities={data.entity_details || []} />
            </div>
          )}
        </AnnotationLayer>
      )}

      <ConfirmDialog
        open={duplicateClaimIndex !== null}
        title="Already a detected claim"
        description={
          duplicateClaimIndex !== null
            ? `"${allClaims[duplicateClaimIndex]?.text}" has already been identified and analyzed - select a different sentence to analyze something new.`
            : undefined
        }
        confirmLabel="View claim"
        cancelLabel="Dismiss"
        onCancel={() => setDuplicateClaimIndex(null)}
        onConfirm={() => {
          if (duplicateClaimIndex !== null) selectClaim(duplicateClaimIndex, "text");
          setDuplicateClaimIndex(null);
        }}
      />

      {snippetTarget && (
        <SourceSnippetModal
          target={snippetTarget}
          onClose={() => setSnippetTarget(null)}
        />
      )}
    </main>
  );
}

function SourceSnippetModal({
  target,
  onClose,
}: {
  target: SnippetTarget;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-950/20"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">View source snippet</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-900">{target.source.title || target.source.url}</h3>
            <a
              href={target.source.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-block text-sm text-slate-500 underline decoration-slate-300 underline-offset-4 hover:text-slate-700"
            >
              {target.source.url}
            </a>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            aria-label="Close modal"
          >
            ×
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-[1fr_1fr]">
          <div className="rounded-lg bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Claim</p>
            <p className="mt-2 text-sm leading-7 text-slate-900">{target.claimText}</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Snippet</p>
            <p className="mt-2 text-sm leading-7 text-slate-700">
              {target.source.snippet || target.source.summary || "No snippet available for this source."}
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
