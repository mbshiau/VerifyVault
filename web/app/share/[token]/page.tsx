"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getSharedAnalysis } from "@/lib/api";
import { ReadOnlyAnalysisView } from "@/components/ReadOnlyAnalysisView";

export default function SharedAnalysisPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);

  const { data, isLoading, error } = useQuery({
    queryKey: ["shared-analysis", token],
    queryFn: () => getSharedAnalysis(token),
    retry: false,
  });

  if (error)
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-8 text-center">
        <p className="text-lg font-medium text-slate-900">This link isn&apos;t available.</p>
        <p className="text-sm text-slate-500">It may be private, or the owner may have removed it.</p>
        <Link href="/" className="inline-block text-sm text-slate-500 underline hover:text-slate-900">
          Go to VerifyVault
        </Link>
      </main>
    );

  if (isLoading || !data)
    return (
      <main className="p-8">
        <p className="text-slate-500">Loading…</p>
      </main>
    );

  return <ReadOnlyAnalysisView data={data} eyebrow="Shared analysis" />;
}
