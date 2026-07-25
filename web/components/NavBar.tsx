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
        <Link href="/" className="text-2xl font-bold text-black" style={{ fontFamily: 'Times New Roman, Times, serif' }}>
                  VerifyVault
        </Link>
        <div className="flex items-center gap-3 text-sm">
          <Link href="/library" className="inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100">
            Library
          </Link>
          {!loading && user && (
            <>
              <Link href="/dashboard" className="inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100">
                My Analyses
              </Link>
              <Link href="/bookmarks" className="inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100">
                My Library
              </Link>
              <Link href="/settings" className="inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100">
                Settings
              </Link>
              <span className="ml-2 text-xs text-stone-500">{user.email}</span>
              <button type="button" onClick={onLogout} className="ml-3 inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100">
                Log out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <Link href="/login" className="inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100">
                Sign in
              </Link>
              <Link href="/signup" className="ml-2 inline-flex items-center rounded-full px-3 py-1 bg-blueberry-600 text-white hover:bg-blueberry-700">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
