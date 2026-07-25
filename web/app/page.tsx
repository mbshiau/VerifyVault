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
    <main className="mx-auto max-w-7xl px-6 py-12 lg:py-16">
      <div className="max-w-3xl">
        <p className="text-sm uppercase tracking-[0.25em] text-slate-500">VerifyVault</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
          Analyze political text with more clarity.
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-600">
          Paste a speech, press release, or statement and get a structured breakdown of claims, context, and evidence.
        </p>
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <form
          onSubmit={onSubmit}
          className="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm shadow-slate-200/60 backdrop-blur"
        >
          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Speaker</span>
                <input
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  placeholder="Jane Smith, Senator"
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                />
              </label>
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Date</span>
                <input
                  type="date"
                  value={speechDate}
                  onChange={(e) => setSpeechDate(e.target.value)}
                  title="Date this was said or written (optional) — leave blank to assume today, set it for older text"
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                />
              </label>
            </div>

            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700">Text to analyze</span>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste a speech, press release, or statement..."
                className="min-h-[22rem] w-full rounded-xl border border-slate-300 bg-slate-50 p-5 text-base leading-8 text-slate-900 outline-none transition focus:border-slate-500 focus:bg-white"
                required
                minLength={20}
              />
            </label>
          </div>

          <div className="sticky bottom-4 z-20 mt-6 border-t border-slate-200 bg-white/90 pt-4">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-slate-500">The Analyze button stays visible as you scroll.</p>
              <button
                type="submit"
                disabled={loading || text.length < 20}
                className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-sm shadow-slate-300 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Analyzing..." : "Analyze"}
              </button>
            </div>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </div>
        </form>

        <aside className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-slate-50 p-6">
            <h2 className="text-lg font-semibold text-slate-900">What you can analyze</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>• Campaign speeches and debate transcripts</p>
              <p>• Press releases, newsletters, and policy statements</p>
              <p>• Social posts or short public remarks</p>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/60">
            <h2 className="text-lg font-semibold text-slate-900">Tips</h2>
            <div className="mt-4 space-y-4 text-sm leading-7 text-slate-600">
              <p>Keep the source text intact so claims can be matched cleanly.</p>
              <p>Add a speaker and date when you know them to improve context.</p>
              <p>Whitespace and line breaks are fine — they make review easier.</p>
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}
