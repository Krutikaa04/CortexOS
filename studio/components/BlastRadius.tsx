"use client";

import type { ImpactArtifact } from "@/lib/types";

// A radial blast-radius view: the change at the centre, its direct dependents
// on the inner ring, indirect dependents on the outer ring. Spokes mean
// "depends on the change" (directly or transitively) — the tiers encode hop
// distance, not exact call edges, so nothing here overstates the graph.
export function BlastRadius({
  direct,
  indirect,
  onSelect,
}: {
  direct: ImpactArtifact[];
  indirect: ImpactArtifact[];
  onSelect: (qn: string) => void;
}) {
  const CX = 170;
  const CY = 170;
  const R1 = 78;
  const R2 = 140;
  const cap = 22;
  const d = direct.slice(0, cap);
  const ind = indirect.slice(0, cap);

  const place = (i: number, n: number, r: number) => {
    const a = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2;
    return { x: CX + Math.cos(a) * r, y: CY + Math.sin(a) * r };
  };

  return (
    <div className="panel p-3">
      <svg viewBox="0 0 340 340" className="w-full">
        <circle cx={CX} cy={CY} r={R1} fill="none" stroke="#1e2534" strokeDasharray="3 4" />
        <circle cx={CX} cy={CY} r={R2} fill="none" stroke="#1e2534" strokeDasharray="3 4" />

        {ind.map((a, i) => {
          const p = place(i, ind.length, R2);
          return (
            <g key={`i${i}`}>
              <line x1={CX} y1={CY} x2={p.x} y2={p.y} stroke="#5aa7ff" strokeOpacity={0.12} />
              <circle
                cx={p.x}
                cy={p.y}
                r={4.5}
                fill="#5aa7ff"
                className="cursor-pointer"
                onClick={() => onSelect(a.qualified_name)}
              >
                <title>{a.qualified_name}</title>
              </circle>
            </g>
          );
        })}
        {d.map((a, i) => {
          const p = place(i, d.length, R1);
          return (
            <g key={`d${i}`}>
              <line x1={CX} y1={CY} x2={p.x} y2={p.y} stroke="#ffc75f" strokeOpacity={0.22} />
              <circle
                cx={p.x}
                cy={p.y}
                r={5.5}
                fill="#ffc75f"
                className="cursor-pointer"
                onClick={() => onSelect(a.qualified_name)}
              >
                <title>{a.qualified_name}</title>
              </circle>
            </g>
          );
        })}

        <circle cx={CX} cy={CY} r={13} fill="#ff6b6b" />
        <circle cx={CX} cy={CY} r={13} fill="none" stroke="#ff6b6b" strokeOpacity={0.3} strokeWidth={6} />
        <text x={CX} y={CY + 30} textAnchor="middle" fontSize={10} className="fill-ink-400 font-mono">
          changed
        </text>
      </svg>
      <div className="flex justify-center gap-4 text-[11px]">
        <Legend color="#ff6b6b" label="changed" />
        <Legend color="#ffc75f" label={`direct (${direct.length})`} />
        <Legend color="#5aa7ff" label={`indirect (${indirect.length})`} />
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-ink-400">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
