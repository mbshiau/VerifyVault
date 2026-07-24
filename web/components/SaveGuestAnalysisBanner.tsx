"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const DISMISS_KEY_PREFIX = "vv_guest_save_dismissed_";

export function SaveGuestAnalysisBanner({ analysisId }: { analysisId: string }) {
  const router = useRouter();
  const [dismissed, setDismissed] = useState(
    () => typeof window !== "undefined" && sessionStorage.getItem(DISMISS_KEY_PREFIX + analysisId) === "1"
  );

  if (dismissed) return null;

  function continueAsGuest() {
    sessionStorage.setItem(DISMISS_KEY_PREFIX + analysisId, "1");
    setDismissed(true);
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-neutral-300 bg-neutral-100 px-4 py-3 text-sm">
      <p className="text-neutral-700">Want to save this analysis to your account?</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => router.push(`/login?claim=${analysisId}`)}
          className="rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-700"
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={continueAsGuest}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-white"
        >
          Continue as guest
        </button>
      </div>
    </div>
  );
}
