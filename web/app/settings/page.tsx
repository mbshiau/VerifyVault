"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { updateProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading: authLoading, refresh } = useAuth();
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [profileVisibility, setProfileVisibility] = useState<"public" | "private">("public");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user) {
      setUsername(user.username ?? "");
      setBio(user.bio ?? "");
      setProfileVisibility(user.profile_visibility ?? "public");
    }
  }, [user]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      await updateProfile({
        username: username.trim() || undefined,
        bio: bio.trim(),
        profile_visibility: profileVisibility,
      });
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading || !user) return null;

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <div className="rounded-2xl bg-white/30 backdrop-blur-sm border border-white/10 p-6 shadow-[0_20px_40px_rgba(59,130,246,0.08)]">
        <h1 className="text-2xl font-semibold">Profile settings</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Set a username to get a public profile page for your public analyses.
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-5">
          <label className="block space-y-2">
            <span className="text-sm font-medium text-neutral-700">Username</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value.toLowerCase())}
              placeholder="lowercase, letters/numbers/underscore, 3-30 chars"
              pattern="[a-z0-9_]{3,30}"
              className="w-full rounded-lg border divider-light bg-stone-50 p-3 text-sm text-stone-900 focus:border-blueberry-600 focus:bg-white focus:outline-none"
            />
            {username && (
              <p className="text-xs text-neutral-500">
                Your public profile will be at /creator/{username}
              </p>
            )}
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-medium text-neutral-700">Bio</span>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              maxLength={280}
              className="min-h-[6rem] w-full rounded-lg border divider-light bg-stone-50 p-3 text-sm text-stone-900 focus:border-blueberry-600 focus:bg-white focus:outline-none"
            />
          </label>

          <label className="flex items-center gap-2 text-sm text-neutral-700">
            <input
              type="checkbox"
              checked={profileVisibility === "private"}
              onChange={(e) => setProfileVisibility(e.target.checked ? "private" : "public")}
            />
            Hide my profile page (your public analyses still work via direct links, just not the /creator page)
          </label>

          <button
            type="submit"
            disabled={saving}
            className="w-full rounded-md bg-blueberry-600 px-5 py-2.5 text-sm font-medium text-white shadow-md shadow-blueberry-400 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          {saved && <p className="text-sm text-green-700">Saved.</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>
      </div>
    </main>
  );
}
