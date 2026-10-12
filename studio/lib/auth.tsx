"use client";

// Account state. The session token is kept in this browser (localStorage) and
// sent as a Bearer header by lib/api.ts. A 401 from any call signs the user out.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { API_URL, getAccessToken, setAccessToken, UNAUTHORIZED_EVENT } from "./api";

export interface AccountUser {
  id: string;
  email: string | null;
  display_name: string;
}

interface AuthValue {
  user: AccountUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

async function authCall<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(
      typeof detail.detail === "string" ? detail.detail : `Request failed (HTTP ${res.status})`,
    );
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Who am I? Works for a login session, a configured service token, and the
  // open local mode (where no sign-in is required at all).
  useEffect(() => {
    let active = true;
    authCall<{ user: AccountUser }>("/v1/auth/me", undefined, "GET")
      .then((r) => active && setUser(r.user))
      .catch(() => active && setUser(null))
      .finally(() => active && setLoading(false));
    const onUnauthorized = () => {
      setAccessToken("");
      setUser(null);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => {
      active = false;
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    };
  }, []);

  const finish = useCallback((r: { token: string; user: AccountUser }) => {
    setAccessToken(r.token);
    setUser(r.user);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      setAccessToken(""); // never send a stale token while signing in
      finish(await authCall("/v1/auth/login", { email, password }));
    },
    [finish],
  );

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      setAccessToken("");
      finish(
        await authCall("/v1/auth/register", {
          email,
          password,
          display_name: displayName || null,
        }),
      );
    },
    [finish],
  );

  const logout = useCallback(async () => {
    try {
      await authCall("/v1/auth/logout");
    } catch {
      /* the local session is dropped regardless */
    }
    setAccessToken("");
    setUser(null);
    try {
      window.localStorage.removeItem("cortex.activeSourceId");
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
