"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type State = "ok" | "degraded" | "offline";

export function HealthIndicator() {
  const [state, setState] = useState<State>("offline");

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const health = await api.health();
        if (active) setState(health.status === "ok" ? "ok" : "degraded");
      } catch {
        if (active) setState("offline");
      }
    };
    check();
    const interval = setInterval(check, 15_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const styles: Record<State, { dot: string; label: string; text: string }> = {
    ok: { dot: "bg-signal-green", label: "RUNTIME LIVE", text: "text-signal-green" },
    degraded: { dot: "bg-signal-amber", label: "DEGRADED", text: "text-signal-amber" },
    offline: { dot: "bg-signal-red", label: "RUNTIME OFFLINE", text: "text-signal-red" },
  };
  const s = styles[state];

  return (
    <span className={`badge border border-ink-700 ${s.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${state === "ok" ? "animate-pulse" : ""}`} />
      {s.label}
    </span>
  );
}
