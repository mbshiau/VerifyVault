"use client";

import { ReactNode, useMemo, useRef, useState } from "react";
import { Claim, Entity, EntityDetail, Transcript, VideoInfo, getVideoFileUrl } from "@/lib/api";
import { matchClaimsToText } from "@/lib/highlight";
import { ClaimHighlightedText } from "@/app/analysis/[id]/ClaimHighlighter";
import { EntityDetails } from "@/app/analysis/[id]/EntityDetails";
import { VideoPlayer, VideoPlayerHandle } from "@/app/analysis/[id]/VideoPlayer";
import { YouTubePlayer } from "@/app/analysis/[id]/YouTubePlayer";
import { TweetEmbed } from "@/app/analysis/[id]/TweetEmbed";
import { TranscriptView } from "@/app/analysis/[id]/TranscriptView";

export type ReadOnlyAnalysisData = {
  id: string;
  title: string;
  source_type: string;
  text: string;
  speaker?: string | null;
  speech_date?: string | null;
  summary: string;
  claims: Claim[];
  topics: string[];
  entities: Entity[];
  entity_details?: EntityDetail[];
  created_at: string;
  view_count: number;
  video?: VideoInfo | null;
  transcript?: Transcript | null;
};

// Shared, read-only rendering used by both /share/[token] (a token-gated
// link, any visibility) and /library/[id] (the public library, always
// visibility=="public") - the two only differ in the header eyebrow text
// and whatever extra controls (author link, bookmark button) the caller
// wants next to the title, never in how the analysis itself renders.
export function ReadOnlyAnalysisView({
  data,
  eyebrow,
  headerExtra,
}: {
  data: ReadOnlyAnalysisData;
  eyebrow: string;
  headerExtra?: ReactNode;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null);
  const [expandedClaimIndex, setExpandedClaimIndex] = useState<number | null>(0);
  const markRefs = useRef<Map<number, HTMLElement>>(new Map());
  const segmentRefs = useRef<Map<number, HTMLElement>>(new Map());
  const videoPlayerRef = useRef<VideoPlayerHandle>(null);

  const claims = data.claims;
  const { spans } = useMemo(() => matchClaimsToText(data.text, claims), [data.text, claims]);

  function selectClaim(index: number) {
    setExpandedClaimIndex((prev) => (prev === index ? null : index));
    setActiveIndex((prev) => (prev === index ? null : index));
    const claim = claims[index];
    if (claim?.start_ms != null) {
      videoPlayerRef.current?.seekTo(claim.start_ms);
      const segIndex = (data.transcript?.segments ?? []).findIndex(
        (s) => claim.start_ms! >= s.start_ms && claim.start_ms! < s.end_ms
      );
      setActiveSegmentIndex(segIndex >= 0 ? segIndex : null);
    }
    markRefs.current.get(index)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const isVideo = data.source_type === "video";

  return (
    <main className="mx-auto max-w-7xl px-6 py-10 lg:py-12">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-slate-500">{eyebrow}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{data.title}</h1>
          <p className="mt-2 text-sm text-slate-500">
            {data.speaker && <>Speaker: {data.speaker} · </>}
            {new Date(data.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
            {" · "}
            {data.view_count} view{data.view_count === 1 ? "" : "s"}
          </p>
        </div>
        {headerExtra && <div className="flex shrink-0 items-center gap-2">{headerExtra}</div>}
      </div>

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
          </div>
          <div className="max-h-[78vh] overflow-y-auto rounded-xl bg-slate-50 p-5">
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
          </div>
        </section>

        <section className="rounded-xl p-6 glass-panel">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Detected claims</h2>
          </div>

          <div className="space-y-3">
            {claims.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
                No claims detected.
              </p>
            ) : (
              claims.map((claim, index) => {
                const isExpanded = expandedClaimIndex === index;
                return (
                  <article
                    key={index}
                    className={`rounded-xl p-4 glass-blue-card transition ${
                      activeIndex === index ? "border-slate-400 ring-1 ring-slate-300" : "border-blueberry-200/30"
                    }`}
                  >
                    <button type="button" onClick={() => selectClaim(index)} className="w-full text-left">
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                        <span className="h-2 w-2 rounded-sm bg-amber-500" />
                        Claim {index + 1}
                      </div>
                      <p className="mt-2 text-sm leading-7 text-slate-900">{claim.text}</p>
                      <p className="mt-3 text-xs text-slate-500">
                        Confidence {(claim.confidence * 100).toFixed(0)}%
                        {claim.materiality != null && <> · Materiality {(claim.materiality * 100).toFixed(0)}%</>}
                      </p>
                    </button>

                    {isExpanded && (
                      <div className="mt-4 space-y-4 border-t border-slate-200 pt-4">
                        {claim.explanation && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                              Explanation
                            </p>
                            <p className="mt-2 text-sm leading-7 text-slate-700">{claim.explanation}</p>
                          </div>
                        )}

                        {claim.context && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Context</p>
                            <p className="mt-2 text-sm leading-7 text-slate-700">{claim.context}</p>
                          </div>
                        )}

                        {claim.sources?.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                              Evidence sources
                            </p>
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
                                    className="rounded-lg border border-slate-200 bg-slate-50 p-3"
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
    </main>
  );
}
