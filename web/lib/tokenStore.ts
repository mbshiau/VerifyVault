// Holds the current JWT access token in memory only (never localStorage,
// to reduce XSS blast radius) so lib/api.ts and lib/auth.tsx can share it
// without a circular import between the two.
type Listener = (token: string | null) => void;

let accessToken: string | null = null;
const listeners = new Set<Listener>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  listeners.forEach((l) => l(token));
}

export function subscribeAccessToken(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
