"use client";

// Dependency-free force-directed graph. Runs a small spring/repulsion
// simulation to a settled layout (animated, then idle), with pan, wheel-zoom,
// node dragging, and hover-neighbour highlighting. Sized for the bounded node
// sets the graph/architecture endpoints return (≲200 nodes).

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export interface FGNode {
  id: string;
  label: string;
  kind: string;
  degree?: number;
  sub?: string;
}
export interface FGEdge {
  from: string;
  to: string;
  kind?: string;
}

export const KIND_COLORS: Record<string, string> = {
  // artifact kinds
  module: "#5aa7ff",
  class: "#a78bfa",
  function: "#4dd0e1",
  method: "#4dd0e1",
  doc_section: "#ffc75f",
  config_entry: "#3ddc97",
  file: "#5aa7ff",
  // change-impact tiers
  changed: "#ff6b6b",
  direct: "#ffc75f",
  indirect: "#5aa7ff",
  // languages (architecture view colours files by language)
  python: "#5aa7ff",
  javascript: "#ffc75f",
  typescript: "#4dd0e1",
  markdown: "#a78bfa",
  json: "#3ddc97",
  yaml: "#3ddc97",
  toml: "#3ddc97",
};
const colorOf = (kind: string) => KIND_COLORS[kind] ?? "#8593ab";

interface Pos {
  x: number;
  y: number;
}

export function ForceGraph({
  nodes,
  edges,
  onSelect,
  height = 560,
}: {
  nodes: FGNode[];
  edges: FGEdge[];
  onSelect?: (node: FGNode) => void;
  height?: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [pos, setPos] = useState<Record<string, Pos>>({});
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [hover, setHover] = useState<string | null>(null);

  const posRef = useRef<Record<string, Pos>>({});
  const velRef = useRef<Record<string, Pos>>({});
  const dragRef = useRef<string | null>(null);
  const panRef = useRef<{ x: number; y: number } | null>(null);

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const e of edges) {
      if (!map.has(e.from)) map.set(e.from, new Set());
      if (!map.has(e.to)) map.set(e.to, new Set());
      map.get(e.from)!.add(e.to);
      map.get(e.to)!.add(e.from);
    }
    return map;
  }, [edges]);

  // --- simulation ---
  useEffect(() => {
    if (nodes.length === 0) return;
    const W = 800;
    const H = height;
    const p: Record<string, Pos> = {};
    const v: Record<string, Pos> = {};
    nodes.forEach((n, i) => {
      const a = (i / nodes.length) * Math.PI * 2;
      const r = 120 + (i % 7) * 24;
      p[n.id] = { x: W / 2 + Math.cos(a) * r, y: H / 2 + Math.sin(a) * r };
      v[n.id] = { x: 0, y: 0 };
    });
    posRef.current = p;
    velRef.current = v;

    const idList = nodes.map((n) => n.id);
    const REPULSE = 5200;
    const SPRING = 0.02;
    const SPRING_LEN = 74;
    const CENTER = 0.006;
    const DAMP = 0.86;
    let alpha = 1;
    let raf = 0;
    let ticks = 0;

    const step = () => {
      const P = posRef.current;
      const V = velRef.current;
      for (let i = 0; i < idList.length; i++) {
        const a = P[idList[i]];
        for (let j = i + 1; j < idList.length; j++) {
          const b = P[idList[j]];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) {
            dx = Math.random() - 0.5;
            dy = Math.random() - 0.5;
            d2 = 0.01;
          }
          const f = (REPULSE / d2) * alpha;
          const d = Math.sqrt(d2);
          const fx = (dx / d) * f;
          const fy = (dy / d) * f;
          V[idList[i]].x += fx;
          V[idList[i]].y += fy;
          V[idList[j]].x -= fx;
          V[idList[j]].y -= fy;
        }
      }
      for (const e of edges) {
        const a = P[e.from];
        const b = P[e.to];
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (d - SPRING_LEN) * SPRING * alpha;
        const fx = (dx / d) * f;
        const fy = (dy / d) * f;
        V[e.from].x += fx;
        V[e.from].y += fy;
        V[e.to].x -= fx;
        V[e.to].y -= fy;
      }
      for (const id of idList) {
        if (id === dragRef.current) {
          V[id].x = 0;
          V[id].y = 0;
          continue;
        }
        V[id].x += (400 - P[id].x) * CENTER * alpha;
        V[id].y += (H / 2 - P[id].y) * CENTER * alpha;
        V[id].x *= DAMP;
        V[id].y *= DAMP;
        P[id].x += V[id].x;
        P[id].y += V[id].y;
      }
      alpha *= 0.985;
      ticks++;
      setPos({ ...P });
      if (ticks < 260 && alpha > 0.02) {
        raf = requestAnimationFrame(step);
      }
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [nodes, edges, height]);

  // --- interaction ---
  const toGraph = useCallback(
    (clientX: number, clientY: number) => {
      const rect = svgRef.current!.getBoundingClientRect();
      const sx = ((clientX - rect.left) / rect.width) * 800;
      const sy = ((clientY - rect.top) / rect.height) * height;
      return { x: (sx - transform.x) / transform.k, y: (sy - transform.y) / transform.k };
    },
    [transform, height],
  );

  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (dragRef.current) {
        const g = toGraph(e.clientX, e.clientY);
        const next = { ...posRef.current, [dragRef.current]: g };
        posRef.current = next;
        setPos({ ...next });
      } else if (panRef.current) {
        const rect = svgRef.current!.getBoundingClientRect();
        const scale = 800 / rect.width;
        setTransform((t) => ({
          ...t,
          x: t.x + (e.movementX * scale),
          y: t.y + (e.movementY * scale),
        }));
      }
    };
    const up = () => {
      dragRef.current = null;
      panRef.current = null;
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [toGraph]);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    setTransform((t) => ({ ...t, k: Math.min(3, Math.max(0.3, t.k * factor)) }));
  };

  const neighbours = hover ? adjacency.get(hover) : null;
  const isDim = (id: string) =>
    hover != null && id !== hover && !(neighbours?.has(id));

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 800 ${height}`}
        className="w-full cursor-grab touch-none rounded-xl border border-ink-800 bg-ink-950 active:cursor-grabbing"
        onWheel={onWheel}
        onPointerDown={(e) => {
          if (e.target === svgRef.current) panRef.current = { x: e.clientX, y: e.clientY };
        }}
      >
        <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.k})`}>
          {edges.map((e, i) => {
            const a = pos[e.from];
            const b = pos[e.to];
            if (!a || !b) return null;
            const active = hover && (e.from === hover || e.to === hover);
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={active ? "#5aa7ff" : "#2a3348"}
                strokeWidth={active ? 1.4 : 0.7}
                strokeOpacity={hover && !active ? 0.15 : 0.6}
              />
            );
          })}
          {nodes.map((n) => {
            const p = pos[n.id];
            if (!p) return null;
            const r = 4 + Math.min(9, Math.sqrt(n.degree ?? 1) * 1.6);
            const dim = isDim(n.id);
            return (
              <g
                key={n.id}
                transform={`translate(${p.x} ${p.y})`}
                opacity={dim ? 0.25 : 1}
                className="cursor-pointer"
                onPointerDown={(e) => {
                  e.stopPropagation();
                  dragRef.current = n.id;
                }}
                onPointerEnter={() => setHover(n.id)}
                onPointerLeave={() => setHover((h) => (h === n.id ? null : h))}
                onClick={() => onSelect?.(n)}
              >
                <circle
                  r={r}
                  fill={colorOf(n.kind)}
                  stroke="#07090e"
                  strokeWidth={1.5}
                />
                {(n.id === hover || (n.degree ?? 0) >= 12) && (
                  <text
                    x={r + 3}
                    y={3}
                    fontSize={9}
                    className="pointer-events-none fill-ink-200 font-mono"
                  >
                    {n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* zoom controls */}
      <div className="absolute right-3 top-3 flex flex-col overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        <button
          className="btn-icon rounded-none"
          onClick={() => setTransform((t) => ({ ...t, k: Math.min(3, t.k * 1.2) }))}
        >
          +
        </button>
        <button
          className="btn-icon rounded-none border-t border-ink-800"
          onClick={() => setTransform((t) => ({ ...t, k: Math.max(0.3, t.k * 0.83) }))}
        >
          −
        </button>
        <button
          className="btn-icon rounded-none border-t border-ink-800 text-[9px]"
          onClick={() => setTransform({ x: 0, y: 0, k: 1 })}
          title="Reset view"
        >
          ⤢
        </button>
      </div>
    </div>
  );
}
