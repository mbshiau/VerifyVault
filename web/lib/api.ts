export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Source = { title: string; url: string; snippet?: string; relation?: string };
export type Claim = {
  text: string;
  quote?: string;
  explanation?: string;
  context?: string;
  related_entities?: string[];
  confidence: number;
  sources: Source[];
};
export type Entity = { name: string; type: string };
export type Analysis = {
  id: string;
  status: string;
  text: string;
  summary: string;
  claims: Claim[];
  topics: string[];
  entities: Entity[];
  created_at: string;
};

export async function createAnalysis(text: string): Promise<Analysis> {
  const r = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getAnalysis(id: string): Promise<Analysis> {
  const r = await fetch(`${API_URL}/analyze/${id}`, { cache: "no-store" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
