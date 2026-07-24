"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { claimAnalysisOwnership } from "@/lib/api";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      // The backend already set the refresh cookie server-side during the
      // Google redirect - this call just mints an access token from it.
      const ok = await refresh();
      if (cancelled) return;
      if (!ok) {
        setError("Google sign-in failed. Please try again.");
        return;
      }
      const claimId = searchParams.get("claim");
      const next = searchParams.get("next");
      if (claimId) {
        try {
          await claimAnalysisOwnership(claimId);
        } catch {
          // Non-fatal - proceed regardless.
        }
        router.replace(`/analysis/${claimId}`);
        return;
      }
      router.replace(next || "/dashboard");
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [refresh, router, searchParams]);

  return (
    <main className="mx-auto max-w-sm px-6 py-16 text-center">
      {error ? <p className="text-sm text-red-600">{error}</p> : <p className="text-sm text-neutral-500">Signing you in…</p>}
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackHandler />
    </Suspense>
  );
}
