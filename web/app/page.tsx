"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAnalysis } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const a = await createAnalysis(text);
      router.push(`/analysis/${a.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold">VerifyVault</h1>
      <p className="mt-2 text-neutral-600">
        Paste political text to extract claims, entities, and sourced evidence.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste a speech, press release, or statement..."
          className="h-64 w-full rounded-lg border border-neutral-300 bg-white p-4 font-mono text-sm focus:border-neutral-900 focus:outline-none"
          required
          minLength={20}
        />
        <button
          type="submit"
          disabled={loading || text.length < 20}
          className="rounded-lg bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Analyzing..." : "Analyze"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </main>
  );
}
