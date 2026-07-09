/**
 * Interactive force-directed knowledge graph — pure React + SVG, no extra deps.
 *
 * Runs a Fruchterman–Reingold force simulation in a requestAnimationFrame loop.
 * Pan with drag, zoom with wheel. Click a node to see its details.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import type { KGEdge, KGNode } from "../types";
import { X, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

// ── Entity-type colour palette ─────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  Method:      "#0284c7",   // sky
  Dataset:     "#059669",   // emerald
  Metric:      "#d97706",   // amber
  Model:       "#7c3aed",   // violet (low saturation)
  Author:      "#e11d48",   // rose
  Finding:     "#0d9488",   // teal
  Limitation:  "#dc2626",   // red
  Concept:     "#71717a",   // zinc (default)
};

function nodeColor(type: string) {
  return TYPE_COLORS[type] ?? TYPE_COLORS["Concept"];
}

// ── Simulation types ───────────────────────────────────────────────────────

interface SimNode extends KGNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface SimEdge {
  source: SimNode;
  target: SimNode;
  relation: string;
}

// ── Force simulation (Fruchterman-Reingold) ────────────────────────────────

function runStep(nodes: SimNode[], edges: SimEdge[], width: number, height: number, k: number) {
  const area = width * height;
  const kk = k * k;

  // Repulsion between every pair
  for (let i = 0; i < nodes.length; i++) {
    nodes[i].vx = 0;
    nodes[i].vy = 0;
    for (let j = 0; j < nodes.length; j++) {
      if (i === j) continue;
      const dx = nodes[i].x - nodes[j].x;
      const dy = nodes[i].y - nodes[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const force = kk / dist;
      nodes[i].vx += (dx / dist) * force;
      nodes[i].vy += (dy / dist) * force;
    }
  }

  // Attraction along edges
  for (const e of edges) {
    const dx = e.target.x - e.source.x;
    const dy = e.target.y - e.source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
    const force = (dist * dist) / k;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    e.source.vx += fx;
    e.source.vy += fy;
    e.target.vx -= fx;
    e.target.vy -= fy;
  }

  // Apply velocities with damping and boundary clamp
  const damping = 0.85;
  const margin = 60;
  for (const n of nodes) {
    n.x += n.vx * damping;
    n.y += n.vy * damping;
    n.x = Math.max(margin, Math.min(width - margin, n.x));
    n.y = Math.max(margin, Math.min(height - margin, n.y));
  }
}

// ── Component ──────────────────────────────────────────────────────────────

interface Props {
  nodes: KGNode[];
  edges: KGEdge[];
}

export default function KnowledgeGraphViewer({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const animRef = useRef<number>(0);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [simEdges, setSimEdges] = useState<SimEdge[]>([]);
  const [selected, setSelected] = useState<SimNode | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<SimEdge | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const dragRef = useRef<{ dragging: boolean; startX: number; startY: number; panX: number; panY: number }>({
    dragging: false, startX: 0, startY: 0, panX: 0, panY: 0,
  });
  const stepsRef = useRef(0);

  const W = 900;
  const H = 580;
  const k = Math.sqrt((W * H) / Math.max(nodes.length, 1)) * 0.9;

  // Initialise simulation from props
  useEffect(() => {
    if (!nodes.length) { setSimNodes([]); setSimEdges([]); return; }

    const nodeMap = new Map<string, SimNode>();
    const sn: SimNode[] = nodes.map((n) => {
      const sn: SimNode = {
        ...n,
        x: W / 2 + (Math.random() - 0.5) * W * 0.6,
        y: H / 2 + (Math.random() - 0.5) * H * 0.6,
        vx: 0, vy: 0,
      };
      nodeMap.set(n.entity, sn);
      return sn;
    });

    const se: SimEdge[] = edges
      .map((e) => ({ source: nodeMap.get(e.source_entity)!, target: nodeMap.get(e.target_entity)!, relation: e.relation }))
      .filter((e) => e.source && e.target);

    setSimNodes(sn);
    setSimEdges(se);
    stepsRef.current = 0;
  }, [nodes, edges]);

  // Animation loop
  useEffect(() => {
    if (!simNodes.length) return;
    const MAX_STEPS = 250;

    function tick() {
      if (stepsRef.current >= MAX_STEPS) return;
      stepsRef.current++;
      // Mutate in-place then trigger a re-render via shallow copy
      runStep(simNodes, simEdges, W, H, k);
      setSimNodes([...simNodes]);
      animRef.current = requestAnimationFrame(tick);
    }
    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, [simNodes, simEdges, k]);

  // Pan events
  function onMouseDown(e: React.MouseEvent) {
    if ((e.target as SVGElement).closest(".kg-node")) return;
    dragRef.current = { dragging: true, startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
  }
  function onMouseMove(e: React.MouseEvent) {
    const d = dragRef.current;
    if (!d.dragging) return;
    setPan({ x: d.panX + (e.clientX - d.startX), y: d.panY + (e.clientY - d.startY) });
  }
  function onMouseUp() { dragRef.current.dragging = false; }

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    setZoom((z) => Math.min(3, Math.max(0.3, z - e.deltaY * 0.001)));
  }

  function resetView() { setPan({ x: 0, y: 0 }); setZoom(1); }

  const typeSet = Array.from(new Set(nodes.map((n) => n.entity_type))).sort();

  if (!nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-zinc-500 gap-3 py-16">
        <svg viewBox="0 0 60 60" width={60} height={60} fill="none">
          <circle cx="10" cy="30" r="6" stroke="#a1a1aa" strokeWidth="2"/>
          <circle cx="50" cy="10" r="6" stroke="#a1a1aa" strokeWidth="2"/>
          <circle cx="50" cy="50" r="6" stroke="#a1a1aa" strokeWidth="2"/>
          <line x1="16" y1="30" x2="44" y2="12" stroke="#d4d4d8" strokeWidth="1.5"/>
          <line x1="16" y1="30" x2="44" y2="48" stroke="#d4d4d8" strokeWidth="1.5"/>
        </svg>
        <p className="text-sm">No knowledge graph yet.</p>
        <p className="text-xs text-zinc-400">Click "Build Knowledge Graph" in the top bar to extract entities and relations from your corpus.</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-zinc-50 border border-zinc-200/60 rounded-lg overflow-hidden select-none">
      {/* Toolbar */}
      <div className="absolute top-3 left-3 z-10 flex gap-1.5">
        <button onClick={() => setZoom((z) => Math.min(3, z + 0.2))}
          className="p-1.5 rounded bg-white border border-zinc-200/60 hover:bg-zinc-100 text-zinc-600 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
          <ZoomIn className="w-4 h-4" />
        </button>
        <button onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}
          className="p-1.5 rounded bg-white border border-zinc-200/60 hover:bg-zinc-100 text-zinc-600 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
          <ZoomOut className="w-4 h-4" />
        </button>
        <button onClick={resetView}
          className="p-1.5 rounded bg-white border border-zinc-200/60 hover:bg-zinc-100 text-zinc-600 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
          <Maximize2 className="w-4 h-4" />
        </button>
        <span className="text-xs text-zinc-500 self-center ml-1 font-mono tabular-nums">{Math.round(zoom * 100)}%</span>
      </div>

      {/* Legend */}
      <div className="absolute top-3 right-3 z-10 bg-white/90 border border-zinc-200/60 rounded-lg p-2.5 text-xs max-w-[200px]">
        <div className="flex flex-wrap gap-1">
          {typeSet.map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 border border-zinc-200/60 px-2 py-0.5">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: nodeColor(t) }} />
              <span className="text-zinc-600">{t}</span>
            </span>
          ))}
        </div>
        <div className="mt-1.5 pt-1.5 border-t border-zinc-200/60 text-zinc-500 font-mono tabular-nums">
          {nodes.length} nodes · {edges.length} edges
        </div>
      </div>

      {/* SVG canvas */}
      <svg
        ref={svgRef}
        width="100%" height="100%"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ cursor: dragRef.current.dragging ? "grabbing" : "grab" }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onWheel={onWheel}
      >
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="16" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#a1a1aa" />
          </marker>
        </defs>

        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {simEdges.map((e, i) => {
            const mx = (e.source.x + e.target.x) / 2;
            const my = (e.source.y + e.target.y) / 2;
            const isHov = hoveredEdge === e;
            return (
              <g key={i}>
                <line
                  x1={e.source.x} y1={e.source.y}
                  x2={e.target.x} y2={e.target.y}
                  stroke={isHov ? "#a1a1aa" : "#d4d4d8"}
                  strokeWidth={isHov ? 1.5 : 1}
                  markerEnd="url(#arrow)"
                  style={{ cursor: "default" }}
                  onMouseEnter={() => setHoveredEdge(e)}
                  onMouseLeave={() => setHoveredEdge(null)}
                />
                {isHov && (
                  <text x={mx} y={my - 5} textAnchor="middle"
                    fill="#52525b" fontSize={10}
                    className="pointer-events-none">
                    {e.relation}
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {simNodes.map((n) => {
            const color = nodeColor(n.entity_type);
            const isSel = selected?.id === n.id;
            return (
              <g key={n.id} className="kg-node"
                style={{ cursor: "pointer" }}
                onClick={() => setSelected(isSel ? null : n)}>
                <circle
                  cx={n.x} cy={n.y} r={isSel ? 14 : 10}
                  fill={color}
                  fillOpacity={isSel ? 1 : 0.85}
                  stroke={isSel ? "#18181b" : color}
                  strokeWidth={isSel ? 2 : 0}
                />
                <text
                  x={n.x} y={n.y + 22}
                  textAnchor="middle"
                  fill="#3f3f46"
                  fontSize={9}
                  className="pointer-events-none"
                  style={{ fontFamily: "system-ui, sans-serif" }}
                >
                  {n.entity.length > 18 ? n.entity.slice(0, 16) + "…" : n.entity}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Node detail panel */}
      {selected && (
        <div className="absolute bottom-4 left-4 z-20 bg-white border border-zinc-200/60 rounded-xl p-4 w-72 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ background: nodeColor(selected.entity_type) }} />
              <span className="font-semibold text-zinc-900 text-sm">{selected.entity}</span>
            </div>
            <button onClick={() => setSelected(null)} className="text-zinc-400 hover:text-zinc-600 transition">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="text-xs text-zinc-500 mb-1">
            <span className="uppercase tracking-wide font-medium" style={{ color: nodeColor(selected.entity_type) }}>
              {selected.entity_type}
            </span>
          </div>
          {selected.description && (
            <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{selected.description}</p>
          )}
          {/* Connected edges */}
          {(() => {
            const connected = simEdges.filter(
              (e) => e.source.id === selected.id || e.target.id === selected.id
            );
            if (!connected.length) return null;
            return (
              <div className="mt-3 border-t border-zinc-200/60 pt-2">
                <p className="text-xs text-zinc-500 mb-1.5 font-medium">Relations</p>
                <div className="space-y-1 max-h-28 overflow-y-auto">
                  {connected.map((e, i) => {
                    const isSource = e.source.id === selected.id;
                    const other = isSource ? e.target : e.source;
                    return (
                      <div key={i} className="text-xs flex items-center gap-1 text-zinc-500">
                        {!isSource && (
                          <span className="truncate max-w-[80px] text-zinc-700">{other.entity}</span>
                        )}
                        <span className="text-zinc-400 shrink-0">
                          {isSource ? "→" : "←"}
                        </span>
                        <span className="text-brand-700 shrink-0">{e.relation}</span>
                        {isSource && (
                          <span className="truncate max-w-[80px] text-zinc-700">{other.entity}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
