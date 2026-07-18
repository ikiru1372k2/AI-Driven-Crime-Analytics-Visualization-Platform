/**
 * Crime association graph (UI-005/#63) — provenance-first interaction.
 *
 * Renders /api/v1/graph subgraphs with Cytoscape. Every visual claim is
 * backed by the API's provenance fields: edge click opens the evidence
 * case; node click opens metrics with the constrained interpretation
 * label (#44 vocabulary — structural descriptions only); classification
 * drives edge styling so observed facts, derived links and potential
 * associations are visually distinct (HUMAN_CONFIRMED distinct again).
 * Large neighbourhoods arrive capped with explicit "N more" stubs.
 *
 * A11y: the List tab is a keyboard-navigable alternative to the canvas —
 * same nodes, same detail panel, no pointer required.
 */
import cytoscape, { type Core } from "cytoscape";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchClassifications,
  fetchNodeDetail,
  fetchSubgraph,
  type ClassificationInfo,
  type GraphEdge,
  type GraphNode,
  type NodeDetail,
  type NodeType,
  type Subgraph,
} from "../lib/graphApi";
import { GraphDetailPanel } from "./GraphDetailPanel";
import {
  buildCyStyle,
  DEFAULT_SEED_CASE,
  EDGE_STYLE,
  LENSES,
  type LensKey,
  NODE_COLORS,
  SEED_EXAMPLES,
  SEED_TYPES,
} from "./graphConfig";

export interface GraphSeed {
  type: NodeType;
  id: string;
}

interface Props {
  seed: GraphSeed | null;
  onSeed: (s: GraphSeed) => void;
  theme: "dark" | "light";
}

export function GraphView({ seed, onSeed, theme }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const [subgraph, setSubgraph] = useState<Subgraph | null>(null);
  const [merged, setMerged] = useState<{ nodes: Map<string, GraphNode>; edges: Map<string, GraphEdge> }>(
    () => ({ nodes: new Map(), edges: new Map() }),
  );
  const [legend, setLegend] = useState<ClassificationInfo[]>([]);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [edgeDetail, setEdgeDetail] = useState<GraphEdge | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [mode, setMode] = useState<"canvas" | "list">("canvas");
  const [lens, setLens] = useState<LensKey>("full");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; label: string; type: string } | null>(
    null,
  );
  const [seedType, setSeedType] = useState<NodeType>(seed?.type ?? "CASE");
  const [seedId, setSeedId] = useState<string>(seed?.id ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // previous views (graph + seed) so Back restores the prior view AND the seed
  const mergedRef = useRef(merged);
  const seedRef = useRef({ type: seedType, id: seedId });
  const historyRef = useRef<
    Array<{ nodes: Map<string, GraphNode>; edges: Map<string, GraphEdge>; type: NodeType; id: string }>
  >([]);
  useEffect(() => {
    mergedRef.current = merged;
  }, [merged]);
  useEffect(() => {
    seedRef.current = { type: seedType, id: seedId };
  }, [seedType, seedId]);

  // capture the current view before an action changes it
  const snapshot = useCallback(() => {
    if (mergedRef.current.nodes.size > 0) {
      historyRef.current.push({
        nodes: mergedRef.current.nodes,
        edges: mergedRef.current.edges,
        type: seedRef.current.type,
        id: seedRef.current.id,
      });
    }
  }, []);

  useEffect(() => {
    fetchClassifications().then(setLegend).catch(() => {});
  }, []);

  const load = useCallback(
    async (type: NodeType, id: string, merge = false) => {
      setLoading(true);
      setError(null);
      try {
        // depth 1 = THIS record's own direct associations (not the general
        // neighbourhood); expand a node to explore further
        const sg = await fetchSubgraph(type, id, { depth: 1, limit: 40 });
        setSubgraph(sg);
        setMerged((prev) => {
          const nodes = merge ? new Map(prev.nodes) : new Map<string, GraphNode>();
          const edges = merge ? new Map(prev.edges) : new Map<string, GraphEdge>();
          sg.nodes.forEach((n) => nodes.set(n.node_id, n));
          sg.edges.forEach((e) => edges.set(e.edge_id, e));
          return { nodes, edges };
        });
        if (!merge) {
          setDetail(null);
          setEdgeDetail(null);
        }
      } catch (e) {
        setError(String(e instanceof Error ? e.message : e));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // seed from URL/props, else bootstrap from the sample case (its accused is
  // "Ravi Kumar" — the same fragmented identity shown on the Identities tab)
  useEffect(() => {
    if (seed) {
      setSeedType(seed.type);
      setSeedId(seed.id);
      expandedRef.current.clear(); // fresh seed = fresh graph
      void load(seed.type, seed.id);
    } else {
      onSeed({ type: "CASE", id: DEFAULT_SEED_CASE });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.type, seed?.id]);

  const openNode = useCallback((type: NodeType, refId: string) => {
    setEdgeDetail(null);
    setShowDetail(false); // load it, but keep it behind the info button until asked
    fetchNodeDetail(type, refId)
      .then(setDetail)
      .catch((e) => setError(String(e)));
  }, []);

  // navigate (reseed) / expand (merge) — both snapshot first so Back can undo
  const navigate = useCallback(
    (s: GraphSeed) => {
      snapshot();
      setLens("full"); // show the destination's full associations, not a filtered slice
      onSeed(s);
    },
    [snapshot, onSeed],
  );
  // remember which nodes we've already expanded so a repeat click just refocuses
  const expandedRef = useRef(new Set<string>());
  const expand = useCallback(
    (type: NodeType, id: string) => {
      const key = `${type}:${id}`;
      setFocusId(key); // zoom to this node's cluster
      if (expandedRef.current.has(key)) return; // already loaded — just refocus
      expandedRef.current.add(key);
      snapshot();
      void load(type, id, true);
    },
    [snapshot, load],
  );

  // switching lens gives a CLEAN view of the current seed in that dimension —
  // it reloads the seed's base graph so expansions from another lens don't
  // linger (e.g. Charge expansions showing up under Full)
  const changeLens = useCallback(
    (key: LensKey) => {
      if (key === lens) return; // already on this lens — don't reload
      setLens(key);
      setFocusId(null);
      expandedRef.current.clear();
      void load(seedRef.current.type, seedRef.current.id, false);
    },
    [load, lens],
  );

  // Back: restore the previous view AND its seed (so the form's case number
  // resets too). Falls back to fitting the whole graph when history is empty.
  const goBack = useCallback(() => {
    const cy = cyRef.current;
    setFocusId(null);
    cy?.elements().removeClass("dim");
    const prev = historyRef.current.pop();
    if (prev) {
      setMerged({ nodes: prev.nodes, edges: prev.edges });
      setSeedType(prev.type);
      setSeedId(prev.id);
    } else {
      cy?.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 350 });
    }
  }, []);

  // (re)draw cytoscape when the merged element set changes
  useEffect(() => {
    if (mode !== "canvas" || !containerRef.current) return;
    cyRef.current?.destroy();
    // lens filter: keep only this dimension's node types (+ the seed), then drop
    // edges whose endpoints aren't both visible
    const active = LENSES.find((l) => l.key === lens)?.types ?? null;
    const seedNodeId = `${seedType}:${seedId}`;
    const nodes = [...merged.nodes.values()].filter(
      (n) => !active || active.has(n.node_type) || n.node_id === seedNodeId,
    );
    const visibleIds = new Set(nodes.map((n) => n.node_id));
    const edges = [...merged.edges.values()].filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
    );
    // node degree drives size + label priority so hubs read and leaves recede
    const degree = new Map<string, number>();
    for (const e of edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    const maxDeg = Math.max(1, ...degree.values());
    // in a lens, a node with no visible connection says nothing here — drop it
    // (keep the seed) so the view is the relationships, not a field of dots
    const shownNodes = nodes.filter(
      (n) => (degree.get(n.node_id) ?? 0) > 0 || n.node_id === seedNodeId,
    );
    const elements = [
      ...shownNodes.map((n) => ({
        data: {
          id: n.node_id,
          label: n.label,
          type: n.node_type,
          ref: n.entity_ref_id,
          deg: degree.get(n.node_id) ?? 0,
          degNorm: (degree.get(n.node_id) ?? 0) / maxDeg,
        },
      })),
      ...edges.map((e) => ({
        data: {
          id: e.edge_id,
          source: e.source,
          target: e.target,
          classification: e.classification,
          rel: e.relationship_type,
          weight: e.weight,
        },
      })),
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: {
        name: "cose",
        animate: false,
        padding: 60,
        nodeRepulsion: () => 16000,
        // distance encodes association strength: stronger link -> shorter edge
        // (closer). Weight raises strength; unconfirmed/AI links sit farther out.
        idealEdgeLength: (edge: cytoscape.EdgeSingular) => {
          const w = Math.max(1, Number(edge.data("weight")) || 1);
          const cls = edge.data("classification") as string;
          const far =
            cls === "AI_DERIVED" || cls === "POTENTIAL_ASSOCIATION"
              ? 1.7
              : cls === "HUMAN_CONFIRMED"
                ? 0.7
                : 1.0;
          return (55 + 120 / Math.sqrt(w)) * far;
        },
        edgeElasticity: () => 100,
        nodeOverlap: 28,
        componentSpacing: 160,
        gravity: 0.2,
        numIter: 2200,
        randomize: true,
        fit: true,
      },
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      style: buildCyStyle(theme) as cytoscape.StylesheetStyle[],
    });
    // tap a node: open its details popover (NOT navigate — no rabbit hole).
    // Navigation happens only from the explicit button inside the popover.
    cy.on("tap", "node", (ev) => {
      const type = ev.target.data("type") as NodeType;
      const ref = ev.target.data("ref") as string;
      setHover(null);
      openNode(type, ref);
      setShowDetail(true);
    });
    cy.on("tap", "edge", (ev) => {
      const e = merged.edges.get(ev.target.id() as string);
      if (e) {
        setDetail(null);
        setEdgeDetail(e);
        setShowDetail(false); // surface via the info button, open on click
      }
    });
    // tap empty canvas: clear focus, dimming and any pending detail
    cy.on("tap", (ev) => {
      if (ev.target === cy) {
        cy.elements().removeClass("dim");
        setFocusId(null);
        setDetail(null);
        setEdgeDetail(null);
        setShowDetail(false);
      }
    });
    // hover: reveal the node's label + connections, and float a small info card
    cy.on("mouseover", "node", (ev) => {
      ev.target.addClass("hover");
      ev.target.connectedEdges().addClass("incident");
      cy.container()!.style.cursor = "pointer";
      const rp = ev.renderedPosition;
      if (rp) {
        setHover({
          x: rp.x,
          y: rp.y,
          label: ev.target.data("label") as string,
          type: ev.target.data("type") as string,
        });
      }
    });
    cy.on("mouseout", "node", (ev) => {
      ev.target.removeClass("hover");
      ev.target.connectedEdges().removeClass("incident");
      cy.container()!.style.cursor = "";
      setHover(null);
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [merged, mode, openNode, theme, lens, seedType, seedId]);

  // zoom-to-cluster: when a node is focused (tapped), dim the rest and animate
  // the camera to fit that node and its linked records
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !focusId) return;
    const node = cy.getElementById(focusId);
    if (node.empty()) return;
    const cluster = node.closedNeighborhood();
    cy.elements().removeClass("dim");
    cy.elements().not(cluster).addClass("dim");
    node.select();
    cy.animate({ fit: { eles: cluster, padding: 90 }, duration: 550, easing: "ease-in-out" });
  }, [focusId, merged]);

  const stubs = subgraph?.stubs;
  const nodeList = [...merged.nodes.values()].sort((a, b) =>
    a.node_id.localeCompare(b.node_id),
  );

  return (
    <div className="body graph-body">
      <div className="sidebar graph-rail">
        <div className="brand">
          <h1>Association graph</h1>
          <p>Observed record graph · every edge cites its FIR</p>
        </div>

        <p className="section-label">Seed</p>
        <form
          className="graph-seed"
          onSubmit={(e) => {
            e.preventDefault();
            if (seedId.trim()) navigate({ type: seedType, id: seedId.trim() });
          }}
        >
          <select
            value={seedType}
            aria-label="Seed node type"
            onChange={(e) => {
              const t = e.target.value as NodeType;
              setSeedType(t);
              setSeedId(SEED_EXAMPLES[t] ?? ""); // keep the id valid for the new type
            }}
          >
            {SEED_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            value={seedId}
            aria-label="Seed record id"
            placeholder={`record id, e.g. ${SEED_EXAMPLES[seedType] ?? "7231"}`}
            onChange={(e) => setSeedId(e.target.value)}
          />
          <button type="submit" disabled={loading}>
            Load
          </button>
        </form>

        <div role="tablist" aria-label="Graph presentation" className="graph-modes">
          <button
            role="tab"
            aria-selected={mode === "canvas"}
            className={"tab" + (mode === "canvas" ? " active" : "")}
            onClick={() => setMode("canvas")}
          >
            Canvas
          </button>
          <button
            role="tab"
            aria-selected={mode === "list"}
            className={"tab" + (mode === "list" ? " active" : "")}
            onClick={() => setMode("list")}
          >
            List (keyboard)
          </button>
        </div>

        <p className="section-label">Edge classification</p>
        <ul className="graph-legend" aria-label="Edge classification legend">
          {legend.map((c) => {
            const s = EDGE_STYLE[c.classification] ?? EDGE_STYLE.FACT;
            return (
              <li key={c.classification}>
                <span
                  className="legend-swatch"
                  style={{
                    borderTop: `${Math.max(2, s.width)}px ${s.style} ${s.color}`,
                  }}
                />
                {c.label}
              </li>
            );
          })}
        </ul>

        {stubs && (stubs.truncated.length > 0 || stubs.cross_scope.length > 0) && (
          <div className="graph-stubs" role="note">
            <p className="section-label">Not shown</p>
            {stubs.truncated.map((s) => (
              <p key={s.node_id} className="stub-row">
                {s.node_id}: {s.more_edges} more edges (cap) —{" "}
                <button
                  className="linklike"
                  onClick={() => {
                    const [type, ...rest] = s.node_id.split(":");
                    expand(type as NodeType, rest.join(":"));
                  }}
                >
                  expand here
                </button>
              </p>
            ))}
            {stubs.cross_scope.map((s) => (
              <p key={s.node_id} className="stub-row">
                {s.node_id}: {s.cross_scope_edges} edges outside scope
              </p>
            ))}
          </div>
        )}

        {error && <p className="error">{error}</p>}
        {loading && <p className="muted">loading subgraph…</p>}
      </div>

      <div className="graph-stage">
        {mode === "canvas" && (
          <button className="graph-zoomout" onClick={goBack} title="Back to the previous view">
            &#8592; Back
          </button>
        )}
        {mode === "canvas" && (
          <div className="graph-lens-overlay" role="group" aria-label="Graph view lens">
            {LENSES.map((l) => (
              <button
                key={l.key}
                className={"lens-chip" + (lens === l.key ? " active" : "")}
                onClick={() => changeLens(l.key)}
                title={l.types ? `Show: ${[...l.types].join(", ")}` : "Show all node types"}
              >
                {l.label}
              </button>
            ))}
          </div>
        )}
        {mode === "canvas" && hover && (
          <div
            className="graph-tooltip"
            style={{ left: hover.x, top: hover.y }}
            aria-hidden="true"
          >
            <span className="tt-type">{hover.type.replace(/_/g, " ").toLowerCase()}</span>
            <span className="tt-label">{hover.label}</span>
            <span className="tt-hint">click to view details</span>
          </div>
        )}
        {mode === "canvas" ? (
          <div ref={containerRef} className="graph-canvas" aria-label="Association graph canvas" />
        ) : (
          <ul className="graph-nodelist" aria-label="Graph nodes (keyboard navigation)">
            {nodeList.map((n) => (
              <li key={n.node_id}>
                <button
                  className={
                    "node-row" + (detail?.node.node_id === n.node_id ? " active" : "")
                  }
                  onClick={() => openNode(n.node_type, n.entity_ref_id)}
                >
                  <span
                    className="node-dot"
                    style={{ background: NODE_COLORS[n.node_type] ?? "#888" }}
                    aria-hidden
                  />
                  <span className="node-type">{n.node_type}</span> {n.label}
                </button>
              </li>
            ))}
          </ul>
        )}

        {showDetail && (
          <GraphDetailPanel
            detail={detail}
            edgeDetail={edgeDetail}
            onClose={() => setShowDetail(false)}
            onNavigate={(type, id) => {
              setShowDetail(false);
              navigate({ type, id });
            }}
            onNavigateCase={(id) => navigate({ type: "CASE", id })}
          />
        )}
      </div>
    </div>
  );
}
