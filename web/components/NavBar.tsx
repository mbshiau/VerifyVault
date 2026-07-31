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
      return `inline-flex items-center rounded-full px-3 py-1 ${active ? 'border-b-2 border-blueberry-600' : ''} bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100 ${extra}`;
    }

  return (
    <nav className="border-b border-stone-200 bg-white">
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
          <Link href="/live" className={linkClass('/live')}>
            Live
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
              <button type="button" onClick={onLogout} className={`ml-3 inline-flex items-center rounded-full px-3 py-1 bg-blueberry-50 text-blueberry-700 hover:bg-blueberry-100`}>
                Log out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <Link href="/login" className={linkClass('/login')}>
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
