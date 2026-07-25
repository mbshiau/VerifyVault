"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnalysisListItem, deleteAnalysis, listAnalyses, renameAnalysis, updateVisibility, listBookmarks } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ShareDialog } from "@/components/ShareDialog";

const VISIBILITY_BADGE: Record<AnalysisListItem["visibility"], string> = {
  private: "🔒 Private",
  unlisted: "🔗 Unlisted",
  public: "🌍 Public",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounced(query, 300);
  const { data, isLoading, error } = useQuery({
    queryKey: ["analyses", debouncedQuery],
    queryFn: () => listAnalyses(debouncedQuery),
  });
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [sharingItem, setSharingItem] = useState<AnalysisListItem | null>(null);
  const { data: bookmarks, isLoading: bookmarksLoading, error: bookmarksError } = useQuery({ queryKey: ["bookmarks"], queryFn: listBookmarks });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameAnalysis(id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["analyses"] }),
  });
  const visibilityMutation = useMutation({
    mutationFn: ({ id, visibility }: { id: string; visibility: "private" | "unlisted" | "public" }) =>
      updateVisibility(id, visibility),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["analyses"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAnalysis(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["analyses"] }),
  });

  const filtered = data || [];

  function startRename(item: AnalysisListItem) {
    setRenamingId(item.id);
    setRenameValue(item.title);
  }

  function commitRename(id: string) {
    const title = renameValue.trim();
    if (title) renameMutation.mutate({ id, title });
    setRenamingId(null);
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <div className="rounded-2xl bg-white/30 backdrop-blur-sm border border-white/10 p-6 shadow-[0_20px_40px_rgba(59,130,246,0.08)]">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-blueberry-700 to-blueberry-400 drop-shadow-[0_6px_16px_rgba(59,130,246,0.12)]">My Analyses</h1>
          <p className="mt-0 text-xs text-stone-400 micro-text">Saved and in-progress analyses, plus your bookmarked library items</p>
        </div>
        <Link href="/" className="rounded-md bg-blueberry-600 px-4 py-2 text-sm font-medium text-white hover:bg-blueberry-700 shadow-sm shadow-blueberry-300">
          New Analysis
        </Link>
      </header>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by title..."
              className="mt-4 w-full rounded-md border border-white/10 bg-white/60 backdrop-blur-sm p-3 text-sm text-stone-900 focus:border-blueberry-600 focus:outline-none"
      />

      {isLoading && <p className="mt-8 text-sm text-stone-600">Loading…</p>}
      {error && <p className="mt-8 text-sm text-red-600">{error instanceof Error ? error.message : "Failed to load"}</p>}

      {!isLoading && !error && filtered.length === 0 && (
        <p className="mt-8 text-sm text-stone-600">
          {debouncedQuery.trim() ? "No analyses match your search." : "No saved analyses yet."}
        </p>
      )}

      <ul className="mt-6 divide-y divider-light overflow-hidden rounded-2xl border border-white/10 bg-white/60 shadow-[0_20px_40px_rgba(59,130,246,0.08)]">
        {filtered.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-3 px-3 py-2">
            <div className="min-w-0 flex-1">
              {renamingId === item.id ? (
                <input
                  autoFocus
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => commitRename(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename(item.id);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  className="w-full rounded border divider-light px-2 py-1 text-sm text-stone-900"
                />
              ) : (
                <Link href={`/analysis/${item.id}`} className="truncate text-sm font-semibold text-blueberry-700 hover:underline">
                  {item.title}
                </Link>
              )}
              <p className="mt-0.5 text-xs text-stone-500">
                <span className="text-black">{item.claim_count} claim{item.claim_count === 1 ? "" : "s"}</span>
                {" · "}
                <span className={item.source_type === "video" || item.source_type === "text" ? "text-blueberry-600 font-medium" : "text-black"}>
                  {item.source_type}
                </span>
                {" · "}
                <span className="text-black">Updated {formatDate(item.updated_at)}</span>
                {item.status !== "complete" && <> {" · "}<span className="text-black">{item.status}</span></>}
                {" · "}
                <span className={item.visibility === "private" ? "text-blueberry-600 font-medium" : "text-black"}>
                  {VISIBILITY_BADGE[item.visibility]}
                </span>
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => setSharingItem(item)}
                className="rounded-md border border-blueberry-300 px-2.5 py-1 text-xs font-medium text-blueberry-700 hover:bg-blueberry-50"
              >
                Share
              </button>
              <button
                type="button"
                onClick={() =>
                  visibilityMutation.mutate({
                    id: item.id,
                    visibility: item.visibility === "public" ? "private" : "public",
                  })
                }
                className="rounded-md border border-blueberry-600 px-2.5 py-1 text-xs font-medium text-blueberry-600 hover:bg-blueberry-100"
              >
                {item.visibility === "public" ? "Unpublish" : "Publish"}
              </button>
              <button
                type="button"
                onClick={() => startRename(item)}
                className="rounded-md border border-blueberry-200 px-2.5 py-1 text-xs font-medium text-blueberry-700 hover:bg-blueberry-50"
              >
                Rename
              </button>
              <button
                type="button"
                onClick={() => setPendingDeleteId(item.id)}
                className="rounded-md border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>

      {/* Bookmarked items section */}
      <section className="mt-8">
        <header className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Bookmarked library items</h2>
          <Link href="/library" className="text-sm text-neutral-600 hover:text-neutral-900">Browse public library</Link>
        </header>
        {bookmarksLoading && <p className="mt-4 text-sm text-neutral-500">Loading…</p>}
        {bookmarksError && <p className="mt-4 text-sm text-red-600">{bookmarksError instanceof Error ? bookmarksError.message : "Failed to load bookmarks"}</p>}
        {!bookmarksLoading && !bookmarksError && (!bookmarks || bookmarks.length === 0) && (
          <p className="mt-4 text-sm text-neutral-500">You haven't bookmarked anything yet.</p>
        )}
        {!bookmarksLoading && !bookmarksError && bookmarks && bookmarks.length > 0 && (
          <ul className="mt-4 divide-y divide-neutral-200 overflow-hidden rounded-2xl border border-white/10 bg-white/60 shadow-[0_20px_40px_rgba(59,130,246,0.08)]">
            {bookmarks.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <Link href={`/library/${item.id}`} className="truncate text-sm font-semibold text-blueberry-700 hover:underline">{item.title}</Link>
                  <p className="mt-0.5 text-xs text-stone-500">
                    <span className="text-black">{item.claim_count} claim{item.claim_count === 1 ? "" : "s"}</span>
                    {" · "}
                    <span className={item.source_type === "video" || item.source_type === "text" ? "text-blueberry-600 font-medium" : "text-black"}>
                      {item.source_type}
                    </span>
                    {" · "}
                    <span className="text-black">{formatDate(item.published_at || item.created_at)}</span>
                  </p>
                </div>
                <Link href={`/library/${item.id}`} className="shrink-0 rounded-md border border-blueberry-300 px-2.5 py-1 text-xs font-medium text-blueberry-700 hover:bg-blueberry-50">View</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      </div>

      <ShareDialog
        open={sharingItem !== null}
        analysis={
          sharingItem ?? { id: "", visibility: "private", share_token: null }
        }
        onClose={() => setSharingItem(null)}
      />

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this analysis?"
        description="This permanently removes the analysis and all its claims and sources."
        confirmLabel="Delete"
        danger
        onCancel={() => setPendingDeleteId(null)}
        onConfirm={() => {
          if (pendingDeleteId) deleteMutation.mutate(pendingDeleteId);
          setPendingDeleteId(null);
        }}
      />
    </main>
  );
}
