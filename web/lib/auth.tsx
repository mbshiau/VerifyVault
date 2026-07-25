"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API_URL } from "./api";
import { setAccessToken } from "./tokenStore";

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  profile_picture_url: string | null;
  auth_provider: string;
  created_at: string;
  username: string | null;
  bio: string;
  avatar_url: string | null;
  profile_visibility: "public" | "private";
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function readErrorMessage(r: Response): Promise<string> {
  try {
    const data = await r.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // fall through
  }
  return r.statusText || "Request failed";
}

async function postTokenRequest(path: string, body?: object): Promise<AuthUser> {
  const r = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(await readErrorMessage(r));
  const data = await r.json();
  setAccessToken(data.access_token);
  return data.user as AuthUser;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Hydrates a session from the httpOnly refresh cookie on first load -
  // this is how "remember me" survives a page reload/browser restart
  // without ever putting the access token in localStorage.
  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
      if (!r.ok) {
        setAccessToken(null);
        setUser(null);
        return false;
      }
      const data = await r.json();
      setAccessToken(data.access_token);
      setUser(data.user);
      return true;
    } catch {
      setAccessToken(null);
      setUser(null);
      return false;
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const login = useCallback(async (email: string, password: string, rememberMe = false) => {
    const u = await postTokenRequest("/auth/login", { email, password, remember_me: rememberMe });
    setUser(u);
  }, []);

  const register = useCallback(async (email: string, password: string, name?: string) => {
    const u = await postTokenRequest("/auth/register", { email, password, name: name || undefined });
    setUser(u);
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
