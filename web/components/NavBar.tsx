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
    <nav className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/" className="text-sm font-semibold text-black">
          VerifyVault
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {!loading && user && (
            <Link href="/dashboard" className="text-stone-700 hover:text-black">
              My Analyses
            </Link>
          )}
          {!loading && user && (
            <>
              <span className="text-stone-500">{user.email}</span>
              <button type="button" onClick={onLogout} className="text-stone-700 hover:text-black">
                Log out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <Link href="/login" className="text-stone-700 hover:text-black">
                Sign in
              </Link>
              <Link href="/signup" className="rounded-sm bg-brand-700 px-3 py-1.5 text-white">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
