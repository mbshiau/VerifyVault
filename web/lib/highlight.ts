import { Claim } from "@/lib/api";

export type ClaimSpan = { start: number; end: number; claim: Claim; index: number };
export type UnmatchedClaim = { claim: Claim; index: number };

function normalize(text: string): { norm: string; map: number[] } {
  let norm = "";
  const map: number[] = [];
  let lastWasSpace = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (/\s/.test(ch)) {
      if (!lastWasSpace) {
        norm += " ";
        map.push(i);
        lastWasSpace = true;
      }
    } else {
      norm += ch.toLowerCase();
      map.push(i);
      lastWasSpace = false;
    }
  }
  return { norm, map };
}

function splitSentences(text: string): { start: number; end: number }[] {
  const spans: { start: number; end: number }[] = [];
  const re = /[^.!?\n]+[.!?]*/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m[0].trim().length === 0) continue;
    spans.push({ start: m.index, end: m.index + m[0].length });
  }
  return spans;
}

function wordSet(s: string): Set<string> {
  return new Set(
    s
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2)
  );
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let intersection = 0;
  for (const w of a) if (b.has(w)) intersection++;
  return intersection / (a.size + b.size - intersection);
}

function overlaps(a: { start: number; end: number }, ranges: { start: number; end: number }[]) {
  return ranges.some((r) => a.start < r.end && a.end > r.start);
}

/**
 * Locates each claim's source sentence within the original text: first via
 * exact (whitespace/case-insensitive) substring match on the model's quote,
 * falling back to the best-overlapping sentence when the quote isn't verbatim.
 */
export function matchClaimsToText(
  text: string,
  claims: Claim[]
): { spans: ClaimSpan[]; unmatched: UnmatchedClaim[] } {
  const { norm, map } = normalize(text);
  const spans: ClaimSpan[] = [];
  const unmatched: UnmatchedClaim[] = [];
  const sentences = splitSentences(text);

  claims.forEach((claim, index) => {
    const quote = (claim.quote || "").trim();
    let found: { start: number; end: number } | null = null;

    if (quote.length >= 8) {
      const { norm: qnorm } = normalize(quote);
      const idx = norm.indexOf(qnorm);
      if (idx !== -1 && qnorm.length > 0) {
        const start = map[idx];
        const end = map[idx + qnorm.length - 1] + 1;
        found = { start, end };
      }
    }

    if (!found) {
      const target = wordSet(quote.length >= 8 ? quote : claim.text);
      let best: { start: number; end: number } | null = null;
      let bestScore = 0;
      for (const s of sentences) {
        const score = jaccard(target, wordSet(text.slice(s.start, s.end)));
        if (score > bestScore) {
          bestScore = score;
          best = s;
        }
      }
      if (best && bestScore >= 0.35) found = best;
    }

    if (found && !overlaps(found, spans)) {
      spans.push({ ...found, claim, index });
    } else {
      unmatched.push({ claim, index });
    }
  });

  spans.sort((a, b) => a.start - b.start);
  return { spans, unmatched };
}
