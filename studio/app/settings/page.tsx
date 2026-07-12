"use client";

import { useEffect, useState } from "react";
import { API_URL, api } from "@/lib/api";
import { useRepo } from "@/lib/repo-context";
import type { HealthStatus } from "@/lib/types";

function Row({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-ink-800 px-4 py-3 last:border-0">
      <span className="text-sm text-ink-400">{label}</span>
      <span className={`text-sm text-ink-100 ${mono ? "font-mono text-[13px]" : ""}`}>{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { selected, sources } = useRepo();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let active = true;
    const check = () =>
      api
        .health()
        .then((h) => active && (setHealth(h), setErr(false)))
        .catch(() => active && setErr(true));
    check();
    const t = setInterval(check, 10_000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, []);

  const dot =
    err || health?.status === "unavailable"
      ? "bg-signal-red"
      : health?.status === "ok"
        ? "bg-signal-green"
        : "bg-signal-amber";

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-3xl px-8 py-8">
        <h1 className="text-xl font-semibold text-ink-100">Settings</h1>
        <p className="mt-1 text-sm text-ink-400">Runtime connection and model configuration.</p>

        <section className="mt-6">
          <div className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Runtime</div>
          <div className="panel">
            <Row
              label="Status"
              mono={false}
              value={
                <span className="inline-flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
                  <span className="capitalize">{err ? "offline" : (health?.status ?? "…")}</span>
                </span>
              }
            />
            <Row label="API endpoint" value={API_URL} />
            <Row label="Version" value={health?.version ?? "—"} />
            {health &&
              Object.entries(health.checks).map(([k, v]) => (
                <Row key={k} label={`Check · ${k}`} value={v} />
              ))}
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Workspace</div>
          <div className="panel">
            <Row label="Active repository" value={selected?.display_name ?? "none"} mono={false} />
            <Row label="Ingested repositories" value={sources?.length ?? "—"} />
            <Row
              label="Active commit"
              value={selected?.latest_version?.commit_sha.slice(0, 12) ?? "—"}
            />
          </div>
        </section>

        <p className="mt-6 text-[11px] text-ink-600">
          CortexOS runs locally through Docker at zero mandatory cost. All values
          above are read live from the runtime.
        </p>
      </div>
    </div>
  );
}
