"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useRepo } from "@/lib/repo-context";
import {
  IconArchitecture,
  IconChat,
  IconChevron,
  IconGraph,
  IconPR,
  IconRepo,
  IconSettings,
} from "./icons";

const NAV = [
  { href: "/chat", label: "Chat", icon: IconChat },
  { href: "/repositories", label: "Repositories", icon: IconRepo },
  { href: "/pull-requests", label: "Impact Guard", icon: IconPR },
  { href: "/architecture", label: "Architecture", icon: IconArchitecture },
  { href: "/graph", label: "Knowledge Graph", icon: IconGraph },
  { href: "/settings", label: "Settings", icon: IconSettings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside
      className="flex h-screen shrink-0 flex-col border-r border-ink-800 bg-ink-950/80"
      style={{ width: "var(--sidebar-w)" }}
    >
      <div className="px-3 pt-3">
        <RepoSwitcher />
      </div>

      <nav className="mt-2 flex-1 space-y-0.5 px-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={`nav-item ${active ? "nav-item-active" : ""}`}
            >
              <Icon className={active ? "text-signal-blue" : "text-ink-400"} />
              {label}
            </Link>
          );
        })}
      </nav>

      <RuntimeFooter />
    </aside>
  );
}

function RepoSwitcher() {
  const { sources, selected, select, isReady } = useRepo();
  const [open, setOpen] = useState(false);
  const ready = (sources ?? []).filter(
    (s) => s.latest_version?.status === "ready",
  );

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg border border-ink-800 bg-ink-900 px-2.5 py-2 text-left transition-colors hover:border-ink-600"
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-signal-blue/15 font-mono text-[11px] font-bold text-signal-blue">
          {(selected?.display_name ?? "?").slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-medium text-ink-100">
            {selected?.display_name ?? "No repository"}
          </span>
          <span className="block text-[10px] text-ink-500">
            {selected
              ? isReady
                ? `${selected.latest_version?.stats?.artifacts ?? "?"} artifacts`
                : (selected.latest_version?.status ?? "empty")
              : "select one"}
          </span>
        </span>
        <IconChevron
          className={`text-ink-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute left-0 right-0 z-20 mt-1 max-h-80 overflow-auto rounded-lg border border-ink-700 bg-ink-900 p-1 shadow-2xl shadow-black/50">
            {ready.length === 0 && (
              <div className="px-2 py-3 text-center text-[11px] text-ink-500">
                No ready repositories.
                <Link
                  href="/repositories"
                  onClick={() => setOpen(false)}
                  className="mt-1 block text-signal-blue hover:underline"
                >
                  Add one →
                </Link>
              </div>
            )}
            {ready.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  select(s.id);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition-colors hover:bg-ink-800 ${
                  s.id === selected?.id ? "text-ink-100" : "text-ink-300"
                }`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-signal-green" />
                <span className="truncate">{s.display_name}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function RuntimeFooter() {
  const { offline, loading } = useRepo();
  const state = loading ? "connecting" : offline ? "offline" : "live";
  const styles = {
    live: { dot: "bg-signal-green", label: "Runtime live", text: "text-ink-400" },
    offline: { dot: "bg-signal-red", label: "Runtime offline", text: "text-signal-red" },
    connecting: { dot: "bg-signal-amber", label: "Connecting…", text: "text-ink-400" },
  }[state];

  return (
    <div className="border-t border-ink-800 px-4 py-3">
      <div className="flex items-center gap-2 text-[11px]">
        <span
          className={`h-1.5 w-1.5 rounded-full ${styles.dot} ${state === "live" ? "animate-pulse" : ""}`}
        />
        <span className={styles.text}>{styles.label}</span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="font-mono text-xs font-bold tracking-tight text-ink-200">
          Cortex<span className="text-signal-blue">OS</span>
        </span>
        <span className="text-[9px] uppercase tracking-[0.2em] text-ink-600">
          Engineering OS
        </span>
      </div>
    </div>
  );
}
