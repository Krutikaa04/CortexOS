"use client";

// Global "active repository" state. The whole tool operates on one selected,
// ingested repository at a time; Chat, Knowledge Graph and Architecture all
// read the current ready source version from here. Selection is persisted so
// it survives navigation and reloads.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "./api";
import type { SourceSummary } from "./types";

const STORAGE_KEY = "cortex.activeSourceId";

interface RepoContextValue {
  sources: SourceSummary[] | null;
  selected: SourceSummary | null;
  versionId: string | null;
  isReady: boolean;
  offline: boolean;
  loading: boolean;
  select: (sourceId: string) => void;
  refresh: () => Promise<void>;
}

const RepoContext = createContext<RepoContextValue | null>(null);

export function RepoProvider({ children }: { children: React.ReactNode }) {
  const [sources, setSources] = useState<SourceSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const s = await api.sources();
      setSources(s);
      setOffline(false);
      setSelectedId((prev) => {
        if (prev && s.some((x) => x.id === prev)) return prev;
        const stored =
          typeof window !== "undefined"
            ? window.localStorage.getItem(STORAGE_KEY)
            : null;
        if (stored && s.some((x) => x.id === stored)) return stored;
        const firstReady = s.find((x) => x.latest_version?.status === "ready");
        return firstReady?.id ?? s[0]?.id ?? null;
      });
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15_000);
    return () => clearInterval(t);
  }, [refresh]);

  const select = useCallback((sourceId: string) => {
    setSelectedId(sourceId);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, sourceId);
    }
  }, []);

  const selected = useMemo(
    () => sources?.find((s) => s.id === selectedId) ?? null,
    [sources, selectedId],
  );
  const isReady = selected?.latest_version?.status === "ready";
  const versionId = isReady ? (selected!.latest_version!.id ?? null) : null;

  const value: RepoContextValue = {
    sources,
    selected,
    versionId,
    isReady: !!isReady,
    offline,
    loading,
    select,
    refresh,
  };

  return <RepoContext.Provider value={value}>{children}</RepoContext.Provider>;
}

export function useRepo(): RepoContextValue {
  const ctx = useContext(RepoContext);
  if (!ctx) throw new Error("useRepo must be used within RepoProvider");
  return ctx;
}
