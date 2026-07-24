"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function NavBar() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  async function onLogout() {
    await logout();
    router.push("/");
  }

  return (
    <nav className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/" className="text-sm font-semibold text-neutral-900">
          VerifyVault
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {!loading && user && (
            <Link href="/dashboard" className="text-neutral-600 hover:text-neutral-900">
              My Analyses
            </Link>
          )}
          {!loading && user && (
            <>
              <span className="text-neutral-400">{user.email}</span>
              <button type="button" onClick={onLogout} className="text-neutral-600 hover:text-neutral-900">
                Log out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <Link href="/login" className="text-neutral-600 hover:text-neutral-900">
                Sign in
              </Link>
              <Link href="/signup" className="rounded-md bg-neutral-900 px-3 py-1.5 text-white">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
