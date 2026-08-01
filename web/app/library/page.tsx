"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PublicAnalysisListItem, addBookmark, listBookmarks, listPublicAnalyses, removeBookmark } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function LibraryPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounced(query, 300);
  const [sort, setSort] = useState<"recent" | "trending">("recent");
  const [topic, setTopic] = useState<string | null>(null);
  const [pendingOverrides, setPendingOverrides] = useState<Map<string, boolean>>(new Map());

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-analyses", debouncedQuery, sort, topic],
    queryFn: () => listPublicAnalyses({ q: debouncedQuery, sort, topic: topic || undefined }),
  });
  const { data: myBookmarks } = useQuery({
    queryKey: ["bookmarks"],
    queryFn: listBookmarks,
    enabled: !!user,
  });

  const items = useMemo(() => data ?? [], [data]);
  const topics = useMemo(() => {
    const set = new Set<string>();
    items.forEach((item) => item.topics.forEach((t) => set.add(t)));
    return Array.from(set).slice(0, 12);
  }, [items]);
  const bookmarkedIds = useMemo(() => new Set((myBookmarks ?? []).map((b) => b.id)), [myBookmarks]);

  function isBookmarked(id: string): boolean {
    return pendingOverrides.has(id) ? pendingOverrides.get(id)! : bookmarkedIds.has(id);
  }

  const bookmarkMutation = useMutation({
    mutationFn: async ({ id, wasBookmarked }: { id: string; wasBookmarked: boolean }) =>
      wasBookmarked ? removeBookmark(id) : addBookmark(id),
    onMutate: ({ id, wasBookmarked }) => {
      setPendingOverrides((prev) => new Map(prev).set(id, !wasBookmarked));
    },
    onSettled: (_data, _error, { id }) => {
      setPendingOverrides((prev) => {
        const next = new Map(prev);
        next.delete(id);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="rounded-2xl p-4 bg-white/30 backdrop-blur-sm shadow-[0_12px_24px_rgba(59,130,246,0.12)] border border-white/10">
        <h1 className="text-2xl font-semibold">Public Library</h1>
        <p className="mt-1 text-sm text-neutral-500">Browse fact-checks other users have made public.</p>
      </header>

      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search title, claims, or creator..."
          className="w-full max-w-sm rounded-lg border border-neutral-300 bg-white/70 backdrop-blur-sm p-3 text-sm focus:border-neutral-900 focus:outline-none focus:shadow-md focus:shadow-blueberry-200"
        />
        <div className="inline-flex rounded-lg border border-neutral-300 bg-neutral-50/90 p-1 text-sm font-medium shadow-sm shadow-blueberry-50">
          {(["recent", "trending"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSort(s)}
              className={`rounded-md px-4 py-1.5 capitalize transition ${sort === s ? "bg-blueberry-600 text-white" : "text-neutral-600 hover:text-neutral-900"}`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {topics.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTopic(null)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              topic === null ? "border-blueberry-600 bg-blueberry-600 text-white" : "border-neutral-300 text-neutral-600"
            }`}
          >
            All topics
          </button>
          {topics.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTopic(t === topic ? null : t)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                topic === t ? "border-blueberry-600 bg-blueberry-600 text-white" : "border-neutral-300 text-neutral-600"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {isLoading && <p className="mt-8 text-sm text-neutral-500">Loading…</p>}
      {error && <p className="mt-8 text-sm text-red-600">{error instanceof Error ? error.message : "Failed to load"}</p>}
      {!isLoading && !error && items.length === 0 && (
        <p className="mt-8 text-sm text-neutral-500">Nothing public matches yet.</p>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <LibraryCard
            key={item.id}
            item={item}
            canBookmark={!!user}
            isBookmarked={isBookmarked(item.id)}
            onToggleBookmark={() => bookmarkMutation.mutate({ id: item.id, wasBookmarked: isBookmarked(item.id) })}
          />
        ))}
      </div>
    </main>
  );
}

function LibraryCard({
  item,
  canBookmark,
  isBookmarked,
  onToggleBookmark,
}: {
  item: PublicAnalysisListItem;
  canBookmark: boolean;
  isBookmarked: boolean;
  onToggleBookmark: () => void;
}) {
  return (
    <article className="flex flex-col justify-between rounded-lg border border-neutral-200 bg-white/60 backdrop-blur-sm p-4 shadow-[0_8px_24px_rgba(59,130,246,0.08)] hover:shadow-[0_12px_36px_rgba(59,130,246,0.12)] transition">
      <div>
        <Link href={`/library/${item.id}`} className="text-sm font-semibold text-neutral-900 hover:underline">
          {item.title}
        </Link>
        {item.author && (
          <p className="mt-1 text-xs text-neutral-500">
            by{" "}
            <Link href={`/creator/${item.author}`} className="underline hover:text-neutral-900">
              {item.author}
            </Link>
          </p>
        )}
        <p className="mt-2 text-xs text-neutral-500">
          {item.claim_count} claim{item.claim_count === 1 ? "" : "s"} · {item.source_type} ·{" "}
          {formatDate(item.published_at || item.created_at)}
        </p>
        <p className="mt-1 text-xs text-neutral-500">
          {item.view_count} view{item.view_count === 1 ? "" : "s"} · {item.bookmark_count} bookmark
          {item.bookmark_count === 1 ? "" : "s"}
        </p>
      </div>
      {canBookmark && (
        <button
          type="button"
          onClick={onToggleBookmark}
          className={`mt-3 self-start rounded-md border px-2.5 py-1 text-xs font-medium shadow-sm ${
            isBookmarked
                          ? "border-blueberry-600 bg-blueberry-600 text-white"
              : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
          }`}
        >
          {isBookmarked ? "Bookmarked" : "Bookmark"}
        </button>
      )}
    </article>
  );
}
