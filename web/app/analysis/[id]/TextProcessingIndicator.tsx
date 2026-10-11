"use client";

import { ProcessingIndicator, ProcessingStep } from "./ProcessingIndicator";

// Text analysis runs claim extraction, source search, and confidence scoring
// as one pipeline.run() call on the backend with no intermediate status to
// poll - unlike video, which has real discrete stages. These steps are a
// self-advancing approximation (see ProcessingIndicator's autoAdvanceMs) so
// the UI reads the same way video's does, not a precise progress signal.
const STEPS: ProcessingStep[] = [
  { key: "reading", label: "Reading the text" },
  { key: "extracting_claims", label: "Extracting claims" },
  { key: "finding_sources", label: "Finding sources" },
  { key: "scoring", label: "Scoring confidence" },
];

export function TextProcessingIndicator({ startedAt }: { startedAt: string }) {
  return <ProcessingIndicator steps={STEPS} autoAdvanceMs={7000} startedAt={startedAt} />;
}
