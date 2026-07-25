"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listBookmarks, removeBookmark } from "@/lib/api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function BookmarksPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["bookmarks"], queryFn: listBookmarks });

  const removeMutation = useMutation({
    mutationFn: (id: string) => removeBookmark(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bookmarks"] }),
  });

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">My Library</h1>
        <Link href="/library" className="text-sm text-neutral-600 hover:text-neutral-900">
          Browse public library
        </Link>
      </header>

      {isLoading && <p className="mt-8 text-sm text-neutral-500">Loading…</p>}
      {error && <p className="mt-8 text-sm text-red-600">{error instanceof Error ? error.message : "Failed to load"}</p>}
      {!isLoading && !error && (data ?? []).length === 0 && (
        <p className="mt-8 text-sm text-neutral-500">
          You haven&apos;t bookmarked anything yet. Find something in the{" "}
          <Link href="/library" className="underline">
            public library
          </Link>
          .
        </p>
      )}

      <ul className="mt-6 divide-y divide-neutral-200 overflow-hidden rounded-lg border border-neutral-200 bg-white">
        {(data ?? []).map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-4 px-4 py-3">
            <div className="min-w-0 flex-1">
              <Link href={`/library/${item.id}`} className="truncate text-sm font-medium text-neutral-900 hover:underline">
                {item.title}
              </Link>
              <p className="mt-0.5 text-xs text-neutral-500">
                {item.author && <>by {item.author} · </>}
                {item.claim_count} claim{item.claim_count === 1 ? "" : "s"} · {item.source_type} ·{" "}
                {formatDate(item.published_at || item.created_at)}
              </p>
            </div>
            <button
              type="button"
              onClick={() => removeMutation.mutate(item.id)}
              className="shrink-0 rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
