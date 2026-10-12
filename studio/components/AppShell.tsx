"use client";

// Gate for the whole app: nothing else (repositories, chat, graph) mounts —
// and no repository request is made — until there is a signed-in account.

import { useState } from "react";
import { AuthProvider, useAuth } from "@/lib/auth";
import { RepoProvider } from "@/lib/repo-context";
import { Sidebar } from "./Sidebar";
import { IconSpinner } from "./icons";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Gate>{children}</Gate>
    </AuthProvider>
  );
}

function Gate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex h-screen items-center justify-center text-ink-500">
        <IconSpinner />
      </div>
    );
  if (!user) return <LoginScreen />;
  // key by user id: switching accounts rebuilds all repository state
  return (
    <RepoProvider key={user.id}>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </RepoProvider>
  );
}

function LoginScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name.trim() || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const field =
    "w-full rounded border border-ink-600 bg-ink-850 px-3 py-2 text-sm outline-none placeholder:text-ink-500 focus:border-signal-blue";

  return (
    <div className="flex h-screen items-center justify-center p-6">
      <form onSubmit={submit} className="panel w-full max-w-sm space-y-4 p-6">
        <div>
          <div className="font-mono text-lg font-bold tracking-tight text-ink-100">
            Cortex<span className="text-signal-blue">OS</span>
          </div>
          <p className="mt-1 text-sm text-ink-400">
            {mode === "login"
              ? "Sign in to your workspace."
              : "Create an account. Your repositories and chats are private to it."}
          </p>
        </div>

        {mode === "register" && (
          <input
            className={field}
            placeholder="Name (optional)"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        )}
        <input
          className={field}
          type="email"
          required
          placeholder="Email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className={field}
          type="password"
          required
          minLength={mode === "register" ? 8 : undefined}
          placeholder={mode === "register" ? "Password (8+ characters)" : "Password"}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <p className="text-xs text-signal-red">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-signal-blue px-4 py-2 text-sm font-semibold text-ink-950 transition-opacity disabled:opacity-50"
        >
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>

        <button
          type="button"
          className="w-full text-center text-xs text-ink-400 hover:text-ink-200"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
        >
          {mode === "login" ? "No account? Create one" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
