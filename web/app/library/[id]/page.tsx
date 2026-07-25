"use client";

import { use } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addBookmark, getPublicAnalysis, removeBookmark } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ReadOnlyAnalysisView } from "@/components/ReadOnlyAnalysisView";

export default function PublicAnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-analysis", id],
    queryFn: () => getPublicAnalysis(id),
    retry: false,
  });

  const bookmarkMutation = useMutation({
    mutationFn: async () => (data?.bookmarked ? removeBookmark(id) : addBookmark(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["public-analysis", id] });
      queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });

  if (error)
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-8 text-center">
        <p className="text-lg font-medium text-slate-900">This analysis isn&apos;t available.</p>
        <p className="text-sm text-slate-500">It may no longer be public.</p>
        <Link href="/library" className="inline-block text-sm text-slate-500 underline hover:text-slate-900">
          Back to the library
        </Link>
      </main>
    );

  if (isLoading || !data)
    return (
      <main className="p-8">
        <p className="text-slate-500">Loading…</p>
      </main>
    );

  return (
    <ReadOnlyAnalysisView
      data={data}
      eyebrow="Public library"
      headerExtra={
        <>
          {data.author && (
            <Link
              href={`/creator/${data.author}`}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              by {data.author}
            </Link>
          )}
          {user && (
            <button
              type="button"
              onClick={() => bookmarkMutation.mutate()}
              disabled={bookmarkMutation.isPending}
              className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                data.bookmarked
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 text-slate-700 hover:bg-slate-50"
              }`}
            >
              {data.bookmarked ? `Bookmarked (${data.bookmark_count})` : `Bookmark (${data.bookmark_count})`}
            </button>
          )}
        </>
      }
    />
  );
}
