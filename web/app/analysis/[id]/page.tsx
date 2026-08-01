"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Analysis,
  Claim,
  VIDEO_PROCESSING_STATUSES,
  analyzeSelectedClaim,
  deleteClaim,
  findMoreSources,
  getAnalysis,
  getVideoFileUrl,
} from "@/lib/api";
import { matchClaimsToText } from "@/lib/highlight";
import { useAuth } from "@/lib/auth";
import { SaveGuestAnalysisBanner } from "@/components/SaveGuestAnalysisBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ClaimHighlightedText } from "./ClaimHighlighter";
import { AnnotationLayer } from "./AnnotationLayer";
import { EntityDetails } from "./EntityDetails";
import { VideoPlayer, VideoPlayerHandle } from "./VideoPlayer";
import { YouTubePlayer } from "./YouTubePlayer";
import { TweetEmbed } from "./TweetEmbed";
import { TranscriptView } from "./TranscriptView";
import { VideoProcessingStepper } from "./VideoProcessingStepper";
import { ShareDialog } from "@/components/ShareDialog";
import { renameAnalysis } from "@/lib/api";

const VIDEO_IN_PROGRESS_STATUSES: readonly string[] = VIDEO_PROCESSING_STATUSES;

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [selectedClaimIndex, setSelectedClaimIndex] = useState(0);
  const [sharingOpen, setSharingOpen] = useState(false);
  const [expandedClaimIndex, setExpandedClaimIndex] = useState<number | null>(0);
  const [annotationMode, setAnnotationMode] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [selectionRect, setSelectionRect] = useState<{ top: number; left: number; isBelow: boolean } | null>(null);
  const [selectedClaims, setSelectedClaims] = useState<Claim[]>([]);
  const [selectedClaimError, setSelectedClaimError] = useState<string | null>(null);
  const [analyzingSelection, setAnalyzingSelection] = useState(false);
  const [duplicateClaimIndex, setDuplicateClaimIndex] = useState<number | null>(null);
  const [copiedClaimIndex, setCopiedClaimIndex] = useState<number | null>(null);
  const [claimPendingDelete, setClaimPendingDelete] = useState<Claim | null>(null);
  const [deletingClaim, setDeletingClaim] = useState(false);
  const [deleteClaimError, setDeleteClaimError] = useState<string | null>(null);
  const [findingMoreSourcesFor, setFindingMoreSourcesFor] = useState<string | null>(null);
  const [moreSourcesErrorFor, setMoreSourcesErrorFor] = useState<string | null>(null);
  const [moreSourcesError, setMoreSourcesError] = useState<string | null>(null);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());
  const textPanelRef = useRef<HTMLDivElement>(null);
  const selectionPopupRef = useRef<HTMLDivElement | null>(null);
  const videoPlayerRef = useRef<VideoPlayerHandle>(null);
  const segmentRefs = useRef<Map<number, HTMLElement>>(new Map());
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const a = await getAnalysis(id);
        if (stop) return;
        setData(a);
        if (a.status === "processing" || VIDEO_IN_PROGRESS_STATUSES.includes(a.status)) setTimeout(tick, 1500);
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
  const { spans } = useMemo(
    () => (data ? matchClaimsToText(data.text, allClaims) : { spans: [], unmatched: [] }),
    [data, allClaims]
  );

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

  function selectClaim(index: number) {
    setSelectedClaimIndex(index);
    setExpandedClaimIndex(index);
    setActiveIndex((prev) => {
      const next = prev === index ? null : index;
      if (next !== null) {
        markRefs.current.get(index)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return next;
    });

    if (data?.source_type === "video") {
      const claim = allClaims[index];
      const startMs = claim?.start_ms;
      if (startMs != null) {
        videoPlayerRef.current?.seekTo(startMs);
        const segments = data.transcript?.segments || [];
        const segIndex = segments.findIndex((s) => startMs >= s.start_ms && startMs < s.end_ms);
        if (segIndex >= 0) {
          setActiveSegmentIndex(segIndex);
          segmentRefs.current.get(segIndex)?.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
    }
  }

  function handleSelectionMouseUp() {
    if (annotationMode || !textPanelRef.current) return;
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;
    const range = selection.getRangeAt(0);
    if (!textPanelRef.current.contains(range.commonAncestorContainer)) return;

    const next = selection.toString().replace(/\s+/g, " ").trim();
    if (!next || next === selectedText) return;

    for (const [index, el] of markRefs.current.entries()) {
      if (range.intersectsNode(el)) {
        selection.removeAllRanges();
        setDuplicateClaimIndex(index);
        return;
      }
    }

    const rect = range.getBoundingClientRect();
    const panelRect = textPanelRef.current.getBoundingClientRect();
    const panel = textPanelRef.current;
    const relativeTop = rect.top - panelRect.top + panel.scrollTop;

    // Check if popup would go off-screen above (less than 200px from top of panel)
    // If so, position it below the selection instead
    const isBelow = relativeTop < 200;

    // initial top/left (will be adjusted when popup size is known)
    const initialTop = rect.bottom - panelRect.top + panel.scrollTop; // default assume below
    const initialLeft = rect.left - panelRect.left + panel.scrollLeft + rect.width / 2;

    setSelectionRect({ top: initialTop, left: initialLeft, isBelow });
    setSelectedText(next);
    setSelectedClaimError(null);

    // Adjust to final top/left that positions the popup fully inside the panel
    requestAnimationFrame(() => {
      const popup = selectionPopupRef.current;
      if (!panel || !popup) return;

      const popupHeight = popup.offsetHeight;
      const popupWidth = popup.offsetWidth;
      const panelHeight = panel.clientHeight;
      const scrollTop = panel.scrollTop;
      const scrollLeft = panel.scrollLeft;

      // Compute desired top so popup sits either below the selection (preferred)
      // or above it if there's not enough space below.
      const belowTop = rect.bottom - panelRect.top + panel.scrollTop + 8; // a little gap below selection
      const aboveTop = rect.top - panelRect.top + panel.scrollTop - popupHeight - 8; // place above selection

      // Choose below if it fits, otherwise above
      let finalTop = belowTop;
      if (belowTop + popupHeight > scrollTop + panelHeight - 8) {
        finalTop = aboveTop;
      }

      // Clamp finalTop within panel content bounds
      const minFinalTop = scrollTop + 8;
      const maxFinalTop = scrollTop + panelHeight - popupHeight - 8;
      if (maxFinalTop < minFinalTop) {
        finalTop = minFinalTop; // popup taller than panel
      } else {
        finalTop = Math.min(Math.max(finalTop, minFinalTop), maxFinalTop);
      }

      // Clamp left so popup stays within horizontal bounds of panel
      let finalLeft = rect.left - panelRect.left + panel.scrollLeft + rect.width / 2;
      const minLeft = scrollLeft + popupWidth / 2 + 8;
      const maxLeft = scrollLeft + panel.clientWidth - popupWidth / 2 - 8;
      finalLeft = Math.min(Math.max(finalLeft, minLeft), maxLeft);

      setSelectionRect((prev) => (prev ? { ...prev, top: finalTop, left: finalLeft, isBelow: finalTop === belowTop } : prev));
    });
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

  function requestDeleteClaim(claim: Claim) {
    setDeleteClaimError(null);
    setClaimPendingDelete(claim);
  }

  async function confirmDeleteClaim() {
    if (!data || !claimPendingDelete?.id || deletingClaim) return;
    setDeletingClaim(true);
    setDeleteClaimError(null);
    try {
      await deleteClaim(data.id, claimPendingDelete.id);
      const deletedId = claimPendingDelete.id;
      setSelectedClaims((prev) => prev.filter((c) => c.id !== deletedId));
      setData((prev) => (prev ? { ...prev, claims: prev.claims.filter((c) => c.id !== deletedId) } : prev));
      setActiveIndex(null);
      setExpandedClaimIndex(null);
      setClaimPendingDelete(null);
    } catch (e) {
      setDeleteClaimError(e instanceof Error ? e.message : "Failed to delete claim.");
    } finally {
      setDeletingClaim(false);
    }
  }

  async function handleFindMoreSources(claim: Claim) {
    if (!data || !claim.id || findingMoreSourcesFor) return;
    setFindingMoreSourcesFor(claim.id);
    setMoreSourcesErrorFor(null);
    setMoreSourcesError(null);
    try {
      const updated = await findMoreSources(data.id, claim.id);
      setSelectedClaims((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setData((prev) =>
        prev ? { ...prev, claims: prev.claims.map((c) => (c.id === updated.id ? updated : c)) } : prev
      );
    } catch (e) {
      setMoreSourcesErrorFor(claim.id);
      setMoreSourcesError(e instanceof Error ? e.message : "Failed to find more sources.");
    } finally {
      setFindingMoreSourcesFor(null);
    }
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
  const isVideo = data.source_type === "video";
  const videoInProgress = isVideo && VIDEO_IN_PROGRESS_STATUSES.includes(data.status);
  const videoFailed = isVideo && data.status.startsWith("failed");

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
            {data.summary && (
              <p className="mt-2 text-sm text-slate-700">{data.summary}</p>
            )}
            <p className="mt-2 text-sm text-slate-500">
              Status: {data.status}
              {data.speaker && <> · Speaker: {data.speaker}</>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSharingOpen(true)}
            className="rounded-md border border-blueberry-300 px-3 py-1 text-sm font-medium text-blueberry-700 hover:bg-blueberry-50"
          >
            Share
          </button>

          <button
            type="button"
            onClick={async () => {
              const newTitle = window.prompt("Rename analysis", data.title);
              if (newTitle && newTitle.trim() && newTitle.trim() !== data.title) {
                try {
                  const updated = await renameAnalysis(data.id, newTitle.trim());
                  setData((prev) => (prev ? { ...prev, title: updated.title } : prev));
                } catch (e) {
                  alert(e instanceof Error ? e.message : "Failed to rename");
                }
              }
            }}
            className="rounded-md border border-blueberry-300 px-3 py-1 text-sm font-medium text-blueberry-700 hover:bg-blueberry-50"
          >
            Rename
          </button>

          <button
            type="button"
            onClick={() => setAnnotationMode((v) => !v)}
            title={annotationMode ? "Exit annotation mode" : "Add annotations"}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              annotationMode
                ? "bg-amber-300 text-slate-900 hover:bg-amber-200"
                : "bg-blueberry-600 text-white hover:bg-blueberry-700"
            }`}
          >
            {annotationMode ? "Annotation on" : "Annotate"}
          </button>
        </div>
      </div>

      {annotationMode && (
        <p className="mt-4 max-w-sm text-xs text-slate-500">Click anywhere to add a note. Scrolling still works normally.</p>
      )}

      {!authLoading && !user && data.user_id === null && <SaveGuestAnalysisBanner analysisId={data.id} />}

      {isVideo && (videoInProgress || videoFailed) ? (
        <div className="mt-8">
          <VideoProcessingStepper status={data.status} />
        </div>
      ) : processing ? (
        <p className="mt-8 text-slate-500">Running pipeline…</p>
      ) : (
        <AnnotationLayer active={annotationMode}>
          {isVideo && (
            <div className="mt-8">
              {data.video?.source === "youtube" && data.video.external_video_id ? (
                <YouTubePlayer ref={videoPlayerRef} videoId={data.video.external_video_id} />
              ) : data.video?.source === "twitter" && data.video.external_video_id ? (
                <TweetEmbed ref={videoPlayerRef} tweetId={data.video.external_video_id} />
              ) : (
                <VideoPlayer ref={videoPlayerRef} src={getVideoFileUrl(data.id)} />
              )}
            </div>
          )}
          <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.9fr)]">
            <section className="rounded-xl p-6 glass-panel">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-slate-900">{isVideo ? "Transcript" : "Original text"}</h2>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  {isVideo
                    ? "Click any word in the transcript to jump to that point in the video, or select (highlight) transcript text to analyze a claim. You can also click a highlighted claim to inspect it."
                    : "Click a highlighted claim to inspect it, or select (highlight) text to analyze a claim."}
                </p>
              </div>
              <div
                className="relative max-h-[78vh] overflow-y-auto rounded-xl bg-slate-50 p-5"
                ref={textPanelRef}
                onMouseUp={handleSelectionMouseUp}
              >
                {isVideo ? (
                  <TranscriptView
                    segments={data.transcript?.segments || []}
                    activeSegmentIndex={activeSegmentIndex}
                    onSeek={(ms) => videoPlayerRef.current?.seekTo(ms)}
                    segmentRefs={segmentRefs}
                    text={data.text}
                    spans={spans}
                    activeIndex={activeIndex}
                    onSelect={selectClaim}
                    markRefs={markRefs}
                  />
                ) : (
                  <ClaimHighlightedText
                    text={data.text}
                    spans={spans}
                    activeIndex={activeIndex}
                    onSelect={selectClaim}
                    markRefs={markRefs}
                  />
                )}

                {selectedText && selectionRect && (
                  <div
                    ref={selectionPopupRef}
                    className={`absolute z-20 w-80 -translate-x-1/2 rounded-lg p-4 bg-white border border-slate-200 shadow-xl`}
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
                      className="mt-3 rounded-lg bg-blueberry-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blueberry-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {analyzingSelection ? "Analyzing..." : "Analyze selected text"}
                    </button>
                    {selectedClaimError && <p className="mt-2 text-xs text-red-600">{selectedClaimError}</p>}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-xl p-6 glass-panel">
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
                      className={`rounded-xl p-4 glass-blue-card transition hover:-translate-y-0.5 hover:shadow-xl ${
                        isSelected ? "border-blueberry-300 ring-1 ring-blueberry-300" : "border-blueberry-200/30"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <button type="button" onClick={() => selectClaim(index)} className="flex-1 text-left">
                            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                              <span className={`h-2 w-2 rounded-sm ${isUserAdded ? "bg-sky-500" : "bg-amber-500"}`} />
                              Claim {index + 1}
                            </div>
                            <p className="mt-2 text-sm leading-7 text-slate-900">{claim.text}</p>
                            <p className="mt-3 text-xs text-slate-500">Confidence {(claim.confidence * 100).toFixed(0)}%</p>
                          </button>

                          <div className="flex flex-col gap-2">
                            <button
                              type="button"
                              onClick={() => copyClaim(claim, index)}
                              className="rounded-lg border border-blueberry-200 px-3 py-1.5 text-xs font-medium text-blueberry-700 transition hover:bg-blueberry-100"
                            >
                              {copiedClaimIndex === index ? "Copied" : "Copy claim"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedClaimIndex(index);
                                setExpandedClaimIndex(isExpanded ? null : index);
                              }}
                              className="rounded-lg bg-blueberry-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blueberry-700"
                            >
                              {isExpanded ? "Collapse" : "Expand"}
                            </button>
                            {claim.id && (
                              <button
                                type="button"
                                onClick={() => requestDeleteClaim(claim)}
                                className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50"
                              >
                                Delete
                              </button>
                            )}
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
                                      </article>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {claim.id && (
                              <div>
                                <button
                                  type="button"
                                  onClick={() => handleFindMoreSources(claim)}
                                  disabled={findingMoreSourcesFor === claim.id}
                                  className="rounded-lg border border-blueberry-200 px-3 py-1.5 text-xs font-medium text-blueberry-700 transition hover:bg-blueberry-100 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {findingMoreSourcesFor === claim.id ? "Searching..." : "+ Find more sources"}
                                </button>
                                {moreSourcesErrorFor === claim.id && moreSourcesError && (
                                  <p className="mt-1.5 text-xs text-red-600">{moreSourcesError}</p>
                                )}
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

      <ShareDialog
        open={sharingOpen}
        analysis={{ id: data.id, visibility: data.visibility, share_token: data.share_token }}
        onClose={() => setSharingOpen(false)}
      />

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
          if (duplicateClaimIndex !== null) selectClaim(duplicateClaimIndex);
          setDuplicateClaimIndex(null);
        }}
      />

      <ConfirmDialog
        open={claimPendingDelete !== null}
        title="Delete this claim?"
        description={
          claimPendingDelete
            ? `"${claimPendingDelete.text}" and its sources will be permanently removed from this analysis.${
                deleteClaimError ? ` ${deleteClaimError}` : ""
              }`
            : undefined
        }
        confirmLabel={deletingClaim ? "Deleting..." : "Delete"}
        cancelLabel="Cancel"
        danger
        onCancel={() => {
          if (deletingClaim) return;
          setClaimPendingDelete(null);
          setDeleteClaimError(null);
        }}
        onConfirm={confirmDeleteClaim}
      />
    </main>
  );
}
