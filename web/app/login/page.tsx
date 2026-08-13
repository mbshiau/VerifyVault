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
    <main className="mx-auto max-w-md px-6 py-16 lg:py-24">
      <div className="rounded-2xl border border-white/10 bg-white/60 backdrop-blur-sm p-8 shadow-[0_20px_40px_rgba(59,130,246,0.16)]">
        <p className="text-sm uppercase tracking-[0.25em] text-stone-500 font-medium">VerifyVault</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-black">Sign in</h1>
        <p className="mt-2 text-sm text-stone-600">Welcome back to VerifyVault.</p>

        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="block space-y-2">
            <span className="text-sm font-medium text-black">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full rounded-md border divider-light bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-blueberry-600 focus:bg-white"
            />
          </label>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-black">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
              className="w-full rounded-md border divider-light bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-blueberry-600 focus:bg-white"
            />
          </label>
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
            className="w-full rounded-md bg-blueberry-600 px-6 py-3 text-sm font-semibold text-white shadow-md shadow-blueberry-400 transition hover:bg-blueberry-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
          {error && <p className="text-sm text-red-600 font-medium">{error}</p>}
        </form>

        <div className="mt-6 flex items-center gap-3 text-xs text-stone-400">
          <div className="h-px flex-1 bg-stone-200" />
          or
          <div className="h-px flex-1 bg-stone-200" />
        </div>

        <a
          href={googleHref}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-md border divider-light bg-white px-6 py-3 text-sm font-semibold text-stone-700 transition hover:bg-stone-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.91 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z" />
          </svg>
          Sign in with Google
        </a>

        <p className="mt-6 text-center text-sm text-stone-600">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="font-semibold text-blueberry-600 hover:text-blueberry-700 transition">
            Sign up
          </Link>
        </p>
      </div>
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
