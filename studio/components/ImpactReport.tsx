"use client";

import type { ImpactArtifact, ImpactReport as Report } from "@/lib/types";
import { BlastRadius } from "./BlastRadius";
import { CodeBlock, CopyButton } from "./CodeBlock";
import { TokenReduction } from "./TokenReduction";
import { IconFile } from "./icons";

const RISK_STYLE = {
  HIGH: { bar: "border-signal-red/50 bg-signal-red/10", text: "text-signal-red", dot: "bg-signal-red" },
  MEDIUM: { bar: "border-signal-amber/50 bg-signal-amber/10", text: "text-signal-amber", dot: "bg-signal-amber" },
  LOW: { bar: "border-signal-green/40 bg-signal-green/10", text: "text-signal-green", dot: "bg-signal-green" },
} as const;

export function ImpactReport({
  report,
  onOpenFile,
}: {
  report: Report;
  onOpenFile: (qn: string) => void;
}) {
  const s = RISK_STYLE[report.risk_level];
  return (
    <div className="animate-fade-up space-y-5">
      {/* risk banner */}
      <div className={`rounded-xl border p-5 ${s.bar}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-full ${s.dot} animate-pulse`} />
            <span className={`text-2xl font-bold tracking-tight ${s.text}`}>
              {report.risk_level} RISK
            </span>
          </div>
          <div className="text-right">
            <div className="font-mono text-2xl font-semibold text-ink-100">
              {report.confidence}%
            </div>
            <div className="text-[10px] uppercase tracking-wider text-ink-500">
              measured confidence
            </div>
          </div>
        </div>
        {report.summary && <p className="mt-3 text-sm text-ink-200">{report.summary}</p>}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {report.sensitivity.map((c) => (
            <span key={c} className="badge bg-ink-900 text-ink-300">
              {c}
            </span>
          ))}
        </div>
        <ul className="mt-3 space-y-1">
          {report.risk_reasons.map((r, i) => (
            <li key={i} className="flex gap-2 text-[13px] text-ink-300">
              <span className="text-ink-600">•</span>
              {r}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
        <div className="space-y-5">
          {/* impact lists */}
          <ImpactList
            title="Direct impact"
            subtitle="depends directly on the changed code"
            items={report.direct_impact}
            onOpenFile={onOpenFile}
            tone="text-signal-amber"
          />
          <ImpactList
            title="Indirect impact"
            subtitle="transitive dependents (2 hops)"
            items={report.indirect_impact}
            onOpenFile={onOpenFile}
            tone="text-signal-blue"
          />

          {report.problems.length > 0 && (
            <Section title="Potential problems">
              <ul className="space-y-1.5">
                {report.problems.map((p, i) => (
                  <li key={i} className="flex gap-2 text-sm text-ink-200">
                    <span className="text-signal-red">⚠</span>
                    {p}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {report.recommended_tests.length > 0 && (
            <Section title="Recommended tests">
              <div className="flex flex-wrap gap-2">
                {report.recommended_tests.map((t, i) => (
                  <span key={i} className="chip font-mono">
                    {t}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {report.suggested_patch && (
            <Section title="Suggested patch">
              <CodeBlock code={report.suggested_patch} language="patch" />
            </Section>
          )}
        </div>

        {/* right rail: blast radius + measured metrics + PR comment */}
        <div className="space-y-4">
          {(report.direct_impact.length > 0 || report.indirect_impact.length > 0) && (
            <BlastRadius
              direct={report.direct_impact}
              indirect={report.indirect_impact}
              onSelect={onOpenFile}
            />
          )}
          <TokenReduction metrics={report.metrics} baselineTokens={null} baselinePending={false} />
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Model calls" value={report.metrics.model_calls ?? 0} />
            <Metric
              label="Latency"
              value={
                report.metrics.total_ms
                  ? `${(report.metrics.total_ms / 1000).toFixed(1)}s`
                  : "—"
              }
            />
          </div>
          <PrComment report={report} />
        </div>
      </div>
    </div>
  );
}

function ImpactList({
  title,
  subtitle,
  items,
  onOpenFile,
  tone,
}: {
  title: string;
  subtitle: string;
  items: ImpactArtifact[];
  onOpenFile: (qn: string) => void;
  tone: string;
}) {
  return (
    <Section title={`${title} (${items.length})`} subtitle={subtitle}>
      {items.length === 0 ? (
        <div className="text-sm text-ink-500">None found in the graph.</div>
      ) : (
        <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
          {items.map((a) => (
            <li key={a.qualified_name}>
              <button
                onClick={() => onOpenFile(a.qualified_name)}
                className="group flex w-full items-center gap-2 rounded-lg border border-transparent px-2 py-1.5 text-left hover:border-ink-700 hover:bg-ink-850/60"
              >
                <IconFile className={`shrink-0 text-ink-600 group-hover:${tone}`} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-mono text-[12.5px] text-ink-100">
                    {a.symbol}
                  </span>
                  <span className="block truncate font-mono text-[10px] text-ink-500">
                    {a.path}
                  </span>
                </span>
                {a.edge_kind && (
                  <span className="badge shrink-0 bg-ink-800 text-ink-400">{a.edge_kind}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel p-4">
      <div className="mb-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-300">
          {title}
        </div>
        {subtitle && <div className="text-[11px] text-ink-500">{subtitle}</div>}
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/50 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ink-500">{label}</div>
      <div className="mt-0.5 font-mono text-sm text-ink-100">{value}</div>
    </div>
  );
}

function buildPrComment(r: Report): string {
  const L = [`## 🛡️ CortexOS Change Impact Guard — ${r.risk_level} RISK (${r.confidence}% confidence)`];
  if (r.summary) L.push("", r.summary);
  if (r.risk_reasons.length) L.push("", "**Why:** " + r.risk_reasons.join("; "));
  if (r.direct_impact.length)
    L.push("", `**Direct impact (${r.direct_impact.length}):** ` +
      r.direct_impact.slice(0, 10).map((a) => `\`${a.symbol}\``).join(", "));
  if (r.indirect_impact.length)
    L.push(`**Indirect impact (${r.indirect_impact.length}):** ` +
      r.indirect_impact.slice(0, 10).map((a) => `\`${a.symbol}\``).join(", "));
  if (r.problems.length)
    L.push("", "**Potential problems:**", ...r.problems.map((p) => `- ${p}`));
  if (r.recommended_tests.length)
    L.push("", "**Recommended tests:** " + r.recommended_tests.map((t) => `\`${t}\``).join(", "));
  if (r.suggested_patch) L.push("", "**Suggested patch:**", "```", r.suggested_patch, "```");
  const m = r.metrics;
  L.push(
    "",
    `_Measured on the repository graph · ${m.context_reduction_pct ?? 0}% context reduction · ` +
      `${m.model_calls ?? 0} model call · ${m.total_ms ? (m.total_ms / 1000).toFixed(1) + "s" : "—"}_`,
  );
  return L.join("\n");
}

function PrComment({ report }: { report: Report }) {
  const md = buildPrComment(report);
  return (
    <div className="panel">
      <div className="flex items-center justify-between border-b border-ink-800 px-3 py-2">
        <span className="text-[10px] uppercase tracking-wider text-ink-500">
          PR comment (ready to post)
        </span>
        <CopyButton text={md} label="Copy PR comment" />
      </div>
      <pre className="max-h-52 overflow-auto px-3 py-3 text-[11px] leading-relaxed text-ink-300">
        {md}
      </pre>
    </div>
  );
}
