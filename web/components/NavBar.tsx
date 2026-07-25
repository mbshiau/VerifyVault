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
<<<<<<< HEAD
          {!loading && user && (
            <Link href="/dashboard" className="text-stone-700 hover:text-black">
              My Analyses
            </Link>
          )}
          {!loading && user && (
            <>
              <span className="text-stone-500">{user.email}</span>
              <button type="button" onClick={onLogout} className="text-stone-700 hover:text-black">
=======
          <Link href="/library" className="text-neutral-600 hover:text-neutral-900">
            Library
          </Link>
          {!loading && user && (
            <>
              <Link href="/dashboard" className="text-neutral-600 hover:text-neutral-900">
                My Analyses
              </Link>
              <Link href="/bookmarks" className="text-neutral-600 hover:text-neutral-900">
                My Library
              </Link>
              <Link href="/settings" className="text-neutral-600 hover:text-neutral-900">
                Settings
              </Link>
              <span className="text-neutral-400">{user.email}</span>
              <button type="button" onClick={onLogout} className="text-neutral-600 hover:text-neutral-900">
>>>>>>> 7c88e61e36cba2dda7750997aac76af84298086a
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
