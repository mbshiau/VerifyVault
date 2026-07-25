"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnalysisListItem, deleteAnalysis, listAnalyses, renameAnalysis, updateVisibility } from "@/lib/api";
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
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">My Analyses</h1>
        <Link href="/" className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white">
          New Analysis
        </Link>
      </header>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by title..."
        className="mt-6 w-full rounded-lg border border-neutral-300 bg-white p-3 text-sm focus:border-neutral-900 focus:outline-none"
      />

      {isLoading && <p className="mt-8 text-sm text-neutral-500">Loading…</p>}
      {error && <p className="mt-8 text-sm text-red-600">{error instanceof Error ? error.message : "Failed to load"}</p>}

      {!isLoading && !error && filtered.length === 0 && (
        <p className="mt-8 text-sm text-neutral-500">
          {debouncedQuery.trim() ? "No analyses match your search." : "No saved analyses yet."}
        </p>
      )}

      <ul className="mt-6 divide-y divide-neutral-200 overflow-hidden rounded-lg border border-neutral-200 bg-white">
        {filtered.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-4 px-4 py-3">
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
                  className="w-full rounded border border-neutral-300 px-2 py-1 text-sm"
                />
              ) : (
                <Link href={`/analysis/${item.id}`} className="truncate text-sm font-medium text-neutral-900 hover:underline">
                  {item.title}
                </Link>
              )}
              <p className="mt-0.5 text-xs text-neutral-500">
                {item.claim_count} claim{item.claim_count === 1 ? "" : "s"} · {item.source_type} · Updated{" "}
                {formatDate(item.updated_at)}
                {item.status !== "complete" && <> · {item.status}</>}
                {" · "}
                {VISIBILITY_BADGE[item.visibility]}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => setSharingItem(item)}
                className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
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
                className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
              >
                {item.visibility === "public" ? "Unpublish" : "Publish"}
              </button>
              <button
                type="button"
                onClick={() => startRename(item)}
                className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
              >
                Rename
              </button>
              <button
                type="button"
                onClick={() => setPendingDeleteId(item.id)}
                className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>

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
