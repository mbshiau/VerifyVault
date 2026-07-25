import { getAccessToken, setAccessToken } from "./tokenStore";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Source = {
  title: string;
  url: string;
  snippet?: string;
  publisher?: string | null;
  retrieval_score?: number | null;
  relation?: string;
  // Only populated on entity-level sources (search_entity_sources), not
  // on per-claim sources - kept optional so the one Source type covers both.
  summary?: string;
  category?: string;
};
export type Claim = {
  id?: string;
  text: string;
  quote?: string;
  explanation?: string;
  context?: string;
  related_entities?: string[];
  confidence: number;
  confidence_explanation?: string;
  materiality?: number;
  source?: string;
  start_ms?: number | null;
  end_ms?: number | null;
  sources: Source[];
};
export type Entity = { name: string; type: string };
export type VideoInfo = { filename: string; duration_seconds: number | null };
export type TranscriptSegment = {
  text: string;
  start_ms: number;
  end_ms: number;
  confidence?: number | null;
};
export type Transcript = { segments: TranscriptSegment[] };
export type EntityDetail = {
  name: string;
  type: string;
  description: string;
  related_claims: string[];
  related_sources: Source[];
};
export type Analysis = {
  id: string;
  status: string;
  title: string;
  source_type: string;
  text: string;
  speaker?: string | null;
  speech_date?: string | null;
  summary: string;
  claims: Claim[];
  topics: string[];
  entities: Entity[];
  entity_details?: EntityDetail[];
  user_id?: string | null;
  created_at: string;
  updated_at: string;
  video?: VideoInfo | null;
  transcript?: Transcript | null;
};

export type AnalysisListItem = {
  id: string;
  title: string;
  status: string;
  source_type: string;
  speaker?: string | null;
  claim_count: number;
  created_at: string;
  updated_at: string;
};

export type SelectedClaimAnalysis = {
  is_claim: boolean;
  reason: string;
  claim: Claim | null;
};

async function readErrorMessage(r: Response): Promise<string> {
  try {
    const data = await r.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // fall through to status-text fallback
  }
  return r.statusText || "Request failed";
}

// Wraps fetch with the current access token, credentials for the refresh
// cookie, and a single silent-refresh-and-retry on 401 - so callers never
// have to think about token expiry themselves.
async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const r = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (r.status === 401 && retry) {
    const refreshed = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
    if (refreshed.ok) {
      const data = await refreshed.json();
      setAccessToken(data.access_token);
      return apiFetch(path, init, false);
    }
  }
  return r;
}

export async function createAnalysis(text: string, speaker?: string, speechDate?: string): Promise<Analysis> {
  const r = await apiFetch(`/api/analysis`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, speaker: speaker || undefined, speech_date: speechDate || undefined }),
  });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

export async function getAnalysis(id: string): Promise<Analysis> {
  const r = await apiFetch(`/api/analysis/${id}`, { cache: "no-store" });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

export async function listAnalyses(q?: string): Promise<AnalysisListItem[]> {
  const query = q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
  const r = await apiFetch(`/api/analysis${query}`, { cache: "no-store" });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

export async function renameAnalysis(id: string, title: string): Promise<Analysis> {
  const r = await apiFetch(`/api/analysis/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

export async function deleteAnalysis(id: string): Promise<void> {
  const r = await apiFetch(`/api/analysis/${id}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(await readErrorMessage(r));
}

export async function claimAnalysisOwnership(id: string): Promise<Analysis> {
  const r = await apiFetch(`/api/analysis/${id}/claim-ownership`, { method: "POST" });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

export async function deleteClaim(analysisId: string, claimId: string): Promise<void> {
  const r = await apiFetch(`/api/analysis/${analysisId}/claims/${claimId}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(await readErrorMessage(r));
}

export async function findMoreSources(analysisId: string, claimId: string): Promise<Claim> {
  const r = await apiFetch(`/api/analysis/${analysisId}/claims/${claimId}/more-sources`, { method: "POST" });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

// Statuses a video analysis passes through before "complete"/"failed: ..." -
// the frontend keeps polling and shows a step label while status is one of these.
export const VIDEO_PROCESSING_STATUSES = [
  "uploading",
  "extracting_audio",
  "transcribing",
  "detecting_claims",
] as const;

export function getVideoFileUrl(id: string): string {
  return `${API_URL}/api/video/${id}/file`;
}

// Uses XMLHttpRequest rather than apiFetch/fetch: `fetch` has no upload
// progress event, so tracking the upload bar requires xhr.upload.onprogress.
export function uploadVideo(
  file: File,
  opts: { speaker?: string; speechDate?: string; onProgress?: (fraction: number) => void } = {}
): Promise<{ id: string }> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    if (opts.speaker) formData.append("speaker", opts.speaker);
    if (opts.speechDate) formData.append("speech_date", opts.speechDate);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/video/upload`);
    xhr.withCredentials = true;
    const token = getAccessToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && opts.onProgress) opts.onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
        return;
      }
      let message = xhr.statusText || "Upload failed";
      try {
        const data = JSON.parse(xhr.responseText);
        if (typeof data?.detail === "string") message = data.detail;
      } catch {
        // fall through to status-text fallback
      }
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(formData);
  });
}

export async function getVideoStatus(id: string): Promise<{ status: string }> {
  const r = await apiFetch(`/api/video/${id}/status`, { cache: "no-store" });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}

export async function analyzeSelectedClaim(id: string, selectedText: string): Promise<SelectedClaimAnalysis> {
  const r = await apiFetch(`/api/analysis/${id}/claim-sentence`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ selected_text: selectedText }),
  });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  return r.json();
}
