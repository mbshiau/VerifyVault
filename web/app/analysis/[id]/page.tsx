"use client";

import { use, useEffect, useState } from "react";
import { Analysis, getAnalysis } from "@/lib/api";

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const a = await getAnalysis(id);
        if (stop) return;
        setData(a);
        if (a.status === "processing") setTimeout(tick, 1500);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed");
      }
    }
    tick();
    return () => {
      stop = true;
    };
  }, [id]);

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!data) return <main className="p-8 text-neutral-500">Loading…</main>;

  const processing = data.status === "processing";

  return (
    <main className="mx-auto max-w-3xl px-6 py-12 space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Analysis</h1>
        <p className="text-sm text-neutral-500">Status: {data.status}</p>
      </header>

      {processing ? (
        <p className="text-neutral-500">Running pipeline…</p>
      ) : (
        <>
          <section>
            <h2 className="mb-2 text-lg font-semibold">Summary</h2>
            <p className="whitespace-pre-wrap leading-relaxed">{data.summary}</p>
          </section>

          {data.topics.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-semibold">Topics</h2>
              <div className="flex flex-wrap gap-2">
                {data.topics.map((t) => (
                  <span key={t} className="rounded-full bg-neutral-200 px-3 py-1 text-xs">
                    {t}
                  </span>
                ))}
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-2 text-lg font-semibold">Claims</h2>
            <ul className="space-y-4">
              {data.claims.map((c, i) => (
                <li key={i} className="rounded-lg border border-neutral-200 bg-white p-4">
                  <p className="font-medium">{c.text}</p>
                  <p className="mt-1 text-xs text-neutral-500">
                    Confidence: {(c.confidence * 100).toFixed(0)}%
                  </p>
                  {c.sources?.length > 0 && (
                    <ul className="mt-3 space-y-2">
                      {c.sources.map((s, j) => (
                        <li key={j} className="text-sm">
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-700 underline"
                          >
                            {s.title || s.url}
                          </a>
                          {s.snippet && (
                            <p className="text-xs text-neutral-600">{s.snippet}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {data.entities.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-semibold">Entities</h2>
              <ul className="grid grid-cols-2 gap-2 text-sm">
                {data.entities.map((e, i) => (
                  <li key={i} className="rounded border border-neutral-200 bg-white px-3 py-2">
                    <span className="font-medium">{e.name}</span>{" "}
                    <span className="text-xs text-neutral-500">({e.type})</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </main>
  );
}
