"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAnalysis } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [speaker, setSpeaker] = useState("");
  const [speechDate, setSpeechDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const a = await createAnalysis(text, speaker.trim(), speechDate || undefined);
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
        <div className="flex gap-3">
          <input
            value={speaker}
            onChange={(e) => setSpeaker(e.target.value)}
            placeholder="Speaker (optional) — e.g. Jane Smith, Senator"
            className="flex-1 rounded-lg border border-neutral-300 bg-white p-3 text-sm focus:border-neutral-900 focus:outline-none"
          />
          <input
            type="date"
            value={speechDate}
            onChange={(e) => setSpeechDate(e.target.value)}
            title="Date this was said or written (optional) — leave blank to assume today, set it for older text"
            className="rounded-lg border border-neutral-300 bg-white p-3 text-sm focus:border-neutral-900 focus:outline-none"
          />
        </div>
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
