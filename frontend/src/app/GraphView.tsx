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
import {
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
  const [mode, setMode] = useState<"canvas" | "list">("canvas");
  const [lens, setLens] = useState<LensKey>("full");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [seedType, setSeedType] = useState<NodeType>(seed?.type ?? "CASE");
  const [seedId, setSeedId] = useState<string>(seed?.id ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      void load(seed.type, seed.id);
    } else {
      onSeed({ type: "CASE", id: DEFAULT_SEED_CASE });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.type, seed?.id]);

  const openNode = useCallback((type: NodeType, refId: string) => {
    setEdgeDetail(null);
    fetchNodeDetail(type, refId)
      .then(setDetail)
      .catch((e) => setError(String(e)));
  }, []);

  // back out of a cluster focus: clear the dimming and zoom out to the full view
  const zoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("dim");
    setFocusId(null);
    cy.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 400 });
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
    const labelInk = theme === "light" ? "#0b0b0b" : "#e8eef4";
    const labelHalo = theme === "light" ? "#ffffff" : "#12161b";
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
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            // size by degree: hubs large, leaf records small
            width: "mapData(degNorm, 0, 1, 16, 52)",
            height: "mapData(degNorm, 0, 1, 16, 52)",
            "background-color": (el: cytoscape.NodeSingular) =>
              NODE_COLORS[el.data("type") as string] ?? "#888",
            "border-width": 1.5,
            "border-color": theme === "light" ? "#ffffff" : "#12161b",
            // label styling: bigger for hubs; a halo keeps text legible on the graph
            "font-size": "mapData(degNorm, 0, 1, 8, 15)",
            color: labelInk,
            "text-outline-color": labelHalo,
            "text-outline-width": 2,
            "text-wrap": "ellipsis",
            "text-max-width": "120px",
            "text-valign": "bottom",
            "text-margin-y": 3,
            // hide labels when zoomed out; small (leaf) labels drop out first
            "min-zoomed-font-size": 11,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": theme === "light" ? "#0b0b0b" : "#e8eef4",
            "min-zoomed-font-size": 0,
            "font-size": 13,
            "z-index": 10,
          },
        },
        {
          selector: "node.hover",
          style: { "min-zoomed-font-size": 0, "z-index": 9 },
        },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "line-color": (el: cytoscape.EdgeSingular) =>
              (EDGE_STYLE[el.data("classification") as string] ?? EDGE_STYLE.FACT).color,
            "line-style": (el: cytoscape.EdgeSingular) =>
              (EDGE_STYLE[el.data("classification") as string] ?? EDGE_STYLE.FACT)
                .style as cytoscape.Css.LineStyle,
            width: (el: cytoscape.EdgeSingular) =>
              (EDGE_STYLE[el.data("classification") as string] ?? EDGE_STYLE.FACT).width,
            opacity: 0.3,
          },
        },
        { selector: "edge:selected", style: { opacity: 1, width: 5 } },
        { selector: "node:selected, node.hover", style: {} },
        { selector: "edge.incident", style: { opacity: 0.9 } },
        // dimmed = not part of the focused cluster
        { selector: ".dim", style: { opacity: 0.08 } },
      ],
    });
    // tap a node:
    //  - a CASE is a focal record -> navigate to it (reseed, replaces the view)
    //    so it never accumulates alongside the form's case
    //  - a hub (place/person/charge) -> reveal its cluster in place and zoom
    cy.on("tap", "node", (ev) => {
      const [type, ...rest] = (ev.target.id() as string).split(":");
      const id = rest.join(":");
      if (type === "CASE") {
        openNode("CASE", id);
        onSeed({ type: "CASE", id });
        return;
      }
      openNode(type as NodeType, id);
      setFocusId(ev.target.id() as string);
      void load(type as NodeType, id, true); // merge = keep the current graph, add neighbours
    });
    cy.on("tap", "edge", (ev) => {
      const e = merged.edges.get(ev.target.id() as string);
      if (e) {
        setDetail(null);
        setEdgeDetail(e);
      }
    });
    // tap empty canvas: clear the focus + dimming
    cy.on("tap", (ev) => {
      if (ev.target === cy) {
        cy.elements().removeClass("dim");
        setFocusId(null);
      }
    });
    // hover: reveal the node's label + its connections even when zoomed out
    cy.on("mouseover", "node", (ev) => {
      ev.target.addClass("hover");
      ev.target.connectedEdges().addClass("incident");
      cy.container()!.style.cursor = "pointer";
    });
    cy.on("mouseout", "node", (ev) => {
      ev.target.removeClass("hover");
      ev.target.connectedEdges().removeClass("incident");
      cy.container()!.style.cursor = "";
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [merged, mode, openNode, load, onSeed, theme, lens, seedType, seedId]);

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
            if (seedId.trim()) onSeed({ type: seedType, id: seedId.trim() });
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
                    void load(type as NodeType, rest.join(":"), true);
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
          <button className="graph-zoomout" onClick={zoomOut} title="Zoom out to the full graph">
            &#8592; Zoom out
          </button>
        )}
        {mode === "canvas" && (
          <div className="graph-lens-overlay" role="group" aria-label="Graph view lens">
            {LENSES.map((l) => (
              <button
                key={l.key}
                className={"lens-chip" + (lens === l.key ? " active" : "")}
                onClick={() => setLens(l.key)}
                title={l.types ? `Show: ${[...l.types].join(", ")}` : "Show all node types"}
              >
                {l.label}
              </button>
            ))}
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

        {detail && (
          <aside className="graph-panel" aria-label="Node detail">
            <header>
              <span
                className="node-dot"
                style={{ background: NODE_COLORS[detail.node.node_type] ?? "#888" }}
                aria-hidden
              />
              <strong>{detail.node.label}</strong>
              <button className="close" aria-label="Close detail" onClick={() => setDetail(null)}>
                ×
              </button>
            </header>
            <p className="badge">{detail.intelligence.classification_label}</p>
            {detail.metrics && (
              <dl className="metric-grid">
                <dt>Co-occurring records</dt>
                <dd>{detail.metrics.degree}</dd>
                <dt>Shared-case links</dt>
                <dd>{detail.metrics.co_occurrence_count}</dd>
                <dt>Betweenness</dt>
                <dd>{detail.metrics.betweenness.toFixed(4)}</dd>
                <dt>Community</dt>
                <dd>{detail.metrics.community_id}</dd>
                <dt>Method</dt>
                <dd>
                  v{detail.metrics.method_version} · run {detail.metrics.run_id.slice(0, 8)}…
                </dd>
              </dl>
            )}
            {detail.metrics?.interpretation && (
              <p className="interpretation">{detail.metrics.interpretation}</p>
            )}
            <p className="section-label">Linked FIRs ({detail.linked_cases.length})</p>
            <ul className="case-list">
              {detail.linked_cases.slice(0, 12).map((c) => (
                <li key={c}>
                  <button className="linklike" onClick={() => onSeed({ type: "CASE", id: String(c) })}>
                    Case {c}
                  </button>
                </li>
              ))}
              {detail.linked_cases.length > 12 && (
                <li className="muted">and {detail.linked_cases.length - 12} more</li>
              )}
            </ul>
            <button
              className="expand"
              onClick={() => void load(detail.node.node_type, detail.node.entity_ref_id, true)}
            >
              Expand neighbourhood
            </button>
            {detail.intelligence.limitations?.map((l) => (
              <p key={l} className="muted small">
                {l}
              </p>
            ))}
          </aside>
        )}

        {edgeDetail && (
          <aside className="graph-panel" aria-label="Edge evidence">
            <header>
              <strong>{edgeDetail.relationship_type}</strong>
              <button className="close" aria-label="Close evidence" onClick={() => setEdgeDetail(null)}>
                ×
              </button>
            </header>
            <p className="badge">{edgeDetail.classification}</p>
            <dl className="metric-grid">
              <dt>Evidence FIR</dt>
              <dd>
                <button
                  className="linklike"
                  onClick={() => onSeed({ type: "CASE", id: String(edgeDetail.evidence_case_id) })}
                >
                  Case {edgeDetail.evidence_case_id}
                </button>
              </dd>
              <dt>Derivation</dt>
              <dd>{edgeDetail.derivation}</dd>
              <dt>From</dt>
              <dd>{edgeDetail.source}</dd>
              <dt>To</dt>
              <dd>{edgeDetail.target}</dd>
            </dl>
            <p className="muted small">
              No edge exists without an evidence case — click through to verify.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
