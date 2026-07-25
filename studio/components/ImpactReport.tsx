"use client";

import type {
  DependencyChain,
  DimensionEntry,
  ImpactArtifact,
  ImpactReport as Report,
  RevisionComparison,
} from "@/lib/types";
import { BlastRadius } from "./BlastRadius";
import { CodeBlock, CopyButton } from "./CodeBlock";
import { TokenReduction } from "./TokenReduction";
import { IconFile } from "./icons";

const DIMENSION_LABEL: Record<string, string> = {
  architectural: "Architectural",
  api: "API",
  database: "Database",
  configuration: "Configuration",
  frontend: "Frontend",
  background_worker: "Background worker",
  external_service: "External service",
  authentication: "Authentication",
  caching: "Caching",
  dependency: "Dependency",
};

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
  const dims = report.impact_dimensions ?? {};
  const dimKeys = Object.keys(dims).filter((k) => dims[k].length > 0);
  return (
    <div className="animate-fade-up space-y-5">
      {report.revision_comparison && (
        <RevisionBanner cmp={report.revision_comparison} />
      )}

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

        {report.confidence_explanation && (
          <div className="mt-4 border-t border-ink-800/60 pt-3">
            <div className="mb-1.5 text-[10px] uppercase tracking-wider text-ink-500">
              Confidence · {report.confidence_explanation.level}
            </div>
            <ul className="space-y-1">
              {report.confidence_explanation.factors.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-[12.5px] text-ink-300">
                  <span
                    className={
                      f.effect === "raises"
                        ? "text-signal-green"
                        : f.effect === "lowers"
                          ? "text-signal-red"
                          : "text-ink-600"
                    }
                  >
                    {f.effect === "raises" ? "▲" : f.effect === "lowers" ? "▼" : "•"}
                  </span>
                  <span>
                    <span className="text-ink-200">{f.signal}</span> — {f.detail}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
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

          {report.architecture_note && (
            <Section title="Architecture impact">
              <p className="text-sm text-ink-200">{report.architecture_note}</p>
            </Section>
          )}

          {dimKeys.length > 0 && (
            <Section
              title="Impact by dimension"
              subtitle="every affected component, and why it appears"
            >
              <div className="space-y-3">
                {dimKeys.map((k) => (
                  <DimensionGroup
                    key={k}
                    label={DIMENSION_LABEL[k] ?? k}
                    entries={dims[k]}
                    onOpenFile={onOpenFile}
                  />
                ))}
              </div>
            </Section>
          )}

          {report.dependency_chains && report.dependency_chains.length > 0 && (
            <Section title="Evidence — dependency chains" subtitle="how the change reaches each dependent">
              <ul className="space-y-1.5">
                {report.dependency_chains.slice(0, 12).map((c, i) => (
                  <ChainRow key={i} chain={c} />
                ))}
              </ul>
            </Section>
          )}

          {report.follow_ups && report.follow_ups.length > 0 && (
            <Section title="Suggested follow-up changes">
              <ul className="space-y-2">
                {report.follow_ups.map((f, i) => (
                  <li key={i} className="text-sm">
                    <div className="flex gap-2 text-ink-100">
                      <span className="text-signal-blue">→</span>
                      {f.action}
                    </div>
                    <div className="ml-5 text-[12px] text-ink-500">{f.why}</div>
                  </li>
                ))}
              </ul>
            </Section>
          )}

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

function RevisionBanner({ cmp }: { cmp: RevisionComparison }) {
  const trendStyle =
    cmp.risk_trend === "increased"
      ? "text-signal-red"
      : cmp.risk_trend === "decreased"
        ? "text-signal-green"
        : "text-ink-300";
  const arrow =
    cmp.risk_trend === "increased" ? "↑" : cmp.risk_trend === "decreased" ? "↓" : "→";
  return (
    <div className="rounded-xl border border-signal-blue/30 bg-signal-blue/5 p-4">
      <div className="flex items-center gap-2">
        <span className="badge bg-signal-blue/15 text-signal-blue">revision comparison</span>
        <span className={`text-sm font-semibold ${trendStyle}`}>
          Risk {arrow} {cmp.previous_risk_level} → {cmp.current_risk_level} ({cmp.risk_trend})
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px] text-ink-300">
        <span>
          Blast radius {cmp.previous_blast_radius} → {cmp.current_blast_radius}{" "}
          <span className={cmp.blast_radius_delta > 0 ? "text-signal-red" : cmp.blast_radius_delta < 0 ? "text-signal-green" : "text-ink-500"}>
            ({cmp.blast_radius_delta >= 0 ? "+" : ""}{cmp.blast_radius_delta})
          </span>
        </span>
        <span>
          Confidence {cmp.confidence_delta >= 0 ? "+" : ""}
          {cmp.confidence_delta}%
        </span>
      </div>
      {cmp.new_risks.length > 0 && (
        <div className="mt-2 text-[12.5px]">
          <span className="text-signal-red">New risks:</span>{" "}
          <span className="text-ink-300">{cmp.new_risks.join("; ")}</span>
        </div>
      )}
      {cmp.resolved_risks.length > 0 && (
        <div className="mt-1 text-[12.5px]">
          <span className="text-signal-green">Resolved:</span>{" "}
          <span className="text-ink-300">{cmp.resolved_risks.join("; ")}</span>
        </div>
      )}
    </div>
  );
}

function DimensionGroup({
  label,
  entries,
  onOpenFile,
}: {
  label: string;
  entries: DimensionEntry[];
  onOpenFile: (qn: string) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span className="badge bg-ink-800 text-ink-200">{label}</span>
        <span className="text-[11px] text-ink-500">{entries[0]?.reason}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {entries.map((e, i) => (
          <button
            key={`${e.symbol}-${i}`}
            onClick={() => onOpenFile(`${e.path}::${e.symbol}`)}
            title={`${e.path} · ${e.hop}${e.edge_kind ? ` · ${e.edge_kind}` : ""}`}
            className="chip font-mono hover:border-ink-600"
          >
            {e.symbol}
          </button>
        ))}
      </div>
    </div>
  );
}

function ChainRow({ chain }: { chain: DependencyChain }) {
  return (
    <li className="rounded-lg border border-ink-800 bg-ink-900/40 px-2.5 py-1.5">
      <div className="font-mono text-[11.5px] text-ink-200">{chain.chain}</div>
      <div className="font-mono text-[10px] text-ink-600">{chain.path}</div>
    </li>
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
  if (r.revision_comparison) {
    const c = r.revision_comparison;
    L.push("", `**Since last analysis:** risk ${c.risk_trend} (${c.previous_risk_level} → ${c.current_risk_level}), ` +
      `blast radius ${c.blast_radius_delta >= 0 ? "+" : ""}${c.blast_radius_delta}`);
    if (c.new_risks.length) L.push(`- New risks: ${c.new_risks.join("; ")}`);
    if (c.resolved_risks.length) L.push(`- Resolved: ${c.resolved_risks.join("; ")}`);
  }
  if (r.architecture_note) L.push("", "**Architecture impact:** " + r.architecture_note);
  if (r.problems.length)
    L.push("", "**Potential problems:**", ...r.problems.map((p) => `- ${p}`));
  if (r.recommended_tests.length)
    L.push("", "**Recommended tests:** " + r.recommended_tests.map((t) => `\`${t}\``).join(", "));
  if (r.follow_ups && r.follow_ups.length)
    L.push("", "**Follow-up changes:**", ...r.follow_ups.map((f) => `- ${f.action}`));
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
