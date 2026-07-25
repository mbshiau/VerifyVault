"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { API_URL, claimAnalysisOwnership } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const next = searchParams.get("next");
  const claimId = searchParams.get("claim");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password, rememberMe);
      if (claimId) {
        try {
          await claimAnalysisOwnership(claimId);
        } catch {
          // Non-fatal - the analysis may already be claimed or gone; still proceed.
        }
        router.push(`/analysis/${claimId}`);
        return;
      }
      router.push(next || "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  const googleHref = `${API_URL}/auth/google/login`;

  return (
    <main className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-semibold text-black">Sign in</h1>
      <p className="mt-2 text-sm text-stone-600">Welcome back to VerifyVault.</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          required
          className="w-full rounded-md border border-stone-200 bg-white p-3 text-sm text-stone-900 focus:border-blueberry-600 focus:outline-none"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          required
          minLength={8}
          className="w-full rounded-md border border-stone-200 bg-white p-3 text-sm text-stone-900 focus:border-blueberry-600 focus:outline-none"
        />
        <label className="flex items-center gap-2 text-sm text-stone-600">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            className="rounded border-stone-300"
          />
          Remember me
        </label>
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-blueberry-600 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      <div className="mt-4 flex items-center gap-3 text-xs text-stone-400">
        <div className="h-px flex-1 bg-stone-200" />
        or
        <div className="h-px flex-1 bg-stone-200" />
      </div>

      <a
        href={googleHref}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-md border border-stone-200 bg-white px-5 py-2.5 text-sm font-medium hover:bg-stone-50"
      >
        Sign in with Google
      </a>

      <p className="mt-6 text-sm text-stone-600">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-medium text-black underline">
          Sign up
        </Link>
      </p>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
