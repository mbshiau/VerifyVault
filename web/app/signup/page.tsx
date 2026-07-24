"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { API_URL } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, password, name.trim() || undefined);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setLoading(false);
    }
  }

  const googleHref = `${API_URL}/auth/google/login`;

  return (
    <main className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-semibold">Create an account</h1>
      <p className="mt-2 text-sm text-neutral-600">Save and revisit your analyses.</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name (optional)"
          className="w-full rounded-lg border border-neutral-300 bg-white p-3 text-sm focus:border-neutral-900 focus:outline-none"
        />
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          required
          className="w-full rounded-lg border border-neutral-300 bg-white p-3 text-sm focus:border-neutral-900 focus:outline-none"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password (min. 8 characters)"
          required
          minLength={8}
          maxLength={72}
          className="w-full rounded-lg border border-neutral-300 bg-white p-3 text-sm focus:border-neutral-900 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Creating account..." : "Create account"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      <div className="mt-4 flex items-center gap-3 text-xs text-neutral-400">
        <div className="h-px flex-1 bg-neutral-200" />
        or
        <div className="h-px flex-1 bg-neutral-200" />
      </div>

      <a
        href={googleHref}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-neutral-300 bg-white px-5 py-2.5 text-sm font-medium hover:bg-neutral-50"
      >
        Sign up with Google
      </a>

      <p className="mt-6 text-sm text-neutral-600">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-neutral-900 underline">
          Sign in
        </Link>
      </p>
    </main>
  );
}
