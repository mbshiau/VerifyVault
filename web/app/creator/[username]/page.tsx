"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getProfile } from "@/lib/api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function CreatorProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = use(params);
  const { data, isLoading, error } = useQuery({
    queryKey: ["profile", username],
    queryFn: () => getProfile(username),
    retry: false,
  });

  if (error)
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-8 text-center">
        <p className="text-lg font-medium text-slate-900">No such profile.</p>
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
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center gap-4 border-b border-neutral-200 pb-6">
        {data.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={data.avatar_url} alt={data.username} className="h-16 w-16 rounded-full object-cover" />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-neutral-200 text-xl font-semibold text-neutral-600">
            {data.username.slice(0, 1).toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">@{data.username}</h1>
          {data.bio && <p className="mt-1 text-sm text-neutral-600">{data.bio}</p>}
          <p className="mt-1 text-xs text-neutral-500">
            Joined {formatDate(data.joined_at)} · {data.public_analysis_count} public analys
            {data.public_analysis_count === 1 ? "is" : "es"}
          </p>
        </div>
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {data.analyses.length === 0 ? (
          <p className="text-sm text-neutral-500">No public analyses yet.</p>
        ) : (
          data.analyses.map((item) => (
            <Link
              key={item.id}
              href={`/library/${item.id}`}
              className="rounded-lg border border-neutral-200 bg-white p-4 hover:border-neutral-300"
            >
              <p className="text-sm font-semibold text-neutral-900">{item.title}</p>
              <p className="mt-2 text-xs text-neutral-500">
                {item.claim_count} claim{item.claim_count === 1 ? "" : "s"} · {item.source_type} ·{" "}
                {formatDate(item.published_at || item.created_at)}
              </p>
            </Link>
          ))
        )}
      </div>
    </main>
  );
}
