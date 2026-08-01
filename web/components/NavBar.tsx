"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function NavBar() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();

  async function onLogout() {
    await logout();
    router.push("/");
  }

  function linkClass(href: string, extra = "") {
      const active = pathname?.startsWith(href);
      return `inline-flex items-center rounded-full px-3 py-1 ${active ? 'border-b-2 border-blueberry-600' : ''} bg-gradient-to-br from-blueberry-100/50 to-blueberry-200/50 text-blueberry-700 hover:from-blueberry-100/70 hover:to-blueberry-200/70 backdrop-blur-2xl shadow-lg shadow-blueberry-200/30 ${extra}`;
    }

  return (
    <nav className="border-b border-blueberry-300/50 bg-gradient-to-r from-white/50 via-blueberry-50/40 to-white/50 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/" className="inline-flex items-center text-black text-2xl font-bold relative px-1" style={{ fontFamily: 'Times New Roman, Times, serif' }}>
                  <span className="relative">
                    VerifyVault
                    <span className="absolute left-0 right-0 bottom-0 translate-y-3 h-[2px] bg-blueberry-600" />
                  </span>
                </Link>
        <div className="flex items-center gap-3 text-sm">
          <Link href="/library" className={linkClass('/library')}>
            Library
          </Link>
          {!loading && user && (
            <>
              <Link href="/dashboard" className={linkClass('/dashboard')}>
                My Analyses
              </Link>
              <Link href="/settings" className={linkClass('/settings')}>
                Settings
              </Link>
              <span className="ml-2 text-xs text-stone-500">{user.email}</span>
              <button type="button" onClick={onLogout} className={`ml-3 inline-flex items-center rounded-full px-3 py-1 bg-gradient-to-br from-blueberry-100/50 to-blueberry-200/50 text-blueberry-700 hover:from-blueberry-100/70 hover:to-blueberry-200/70 backdrop-blur-2xl shadow-lg shadow-blueberry-200/30`}>
                Log out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <Link href="/login" className={linkClass('/login')}>
                Sign in
              </Link>
              <Link href="/signup" className="ml-2 inline-flex items-center rounded-full px-3 py-1 bg-gradient-to-br from-blueberry-600/70 to-blueberry-700/70 text-white hover:from-blueberry-600/85 hover:to-blueberry-700/85 backdrop-blur-2xl shadow-lg shadow-blueberry-600/40 transition">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
