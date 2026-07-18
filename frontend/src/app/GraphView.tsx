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
  fetchSeedCaseId,
  fetchSubgraph,
  type ClassificationInfo,
  type GraphEdge,
  type GraphNode,
  type NodeDetail,
  type NodeType,
  type Subgraph,
} from "../lib/graphApi";

/** Node colours by type (status-neutral palette; classification colours
 * are reserved for edges so inference-vs-fact stays unambiguous). */
const NODE_COLORS: Record<string, string> = {
  CASE: "#4f7cc9",
  ACCUSED_RECORD: "#a76fb9",
  VICTIM_RECORD: "#5aa9a3",
  POLICE_STATION: "#7d8a97",
  DISTRICT: "#5b6d84",
  CRIME_HEAD: "#c98a4f",
  CRIME_SUBHEAD: "#c9a94f",
  COURT: "#8a7dc9",
  SECTION: "#6f8f5a",
};

/** Edge styling by classification — the provenance-first rule (#25/#43):
 * observed FACT restatements: solid grey; DERIVED_METRIC co-occurrence:
 * solid blue; POTENTIAL_ASSOCIATION (identity candidates / MO similarity):
 * dashed amber; HUMAN_CONFIRMED identity: solid green, heavy. */
const EDGE_STYLE: Record<string, { color: string; style: string; width: number }> = {
  FACT: { color: "#9aa4ae", style: "solid", width: 1.5 },
  DERIVED_METRIC: { color: "#4f7cc9", style: "solid", width: 2.5 },
  STATISTICAL_INFERENCE: { color: "#4f7cc9", style: "solid", width: 2.5 },
  AI_DERIVED: { color: "#d9a13b", style: "dashed", width: 2.5 },
  POTENTIAL_ASSOCIATION: { color: "#d9a13b", style: "dashed", width: 2.5 },
  HUMAN_CONFIRMED: { color: "#3c9a5f", style: "solid", width: 4 },
};

const SEED_TYPES: NodeType[] = ["CASE", "ACCUSED_RECORD", "POLICE_STATION", "DISTRICT"];

export interface GraphSeed {
  type: NodeType;
  id: string;
}

interface Props {
  seed: GraphSeed | null;
  onSeed: (s: GraphSeed) => void;
}

export function GraphView({ seed, onSeed }: Props) {
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
        const sg = await fetchSubgraph(type, id, { depth: 2 });
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

  // seed from URL/props, else bootstrap from the first mapped case
  useEffect(() => {
    if (seed) {
      setSeedType(seed.type);
      setSeedId(seed.id);
      void load(seed.type, seed.id);
    } else {
      fetchSeedCaseId()
        .then((id) => {
          if (id) onSeed({ type: "CASE", id });
        })
        .catch((e) => setError(String(e)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.type, seed?.id]);

  const openNode = useCallback((type: NodeType, refId: string) => {
    setEdgeDetail(null);
    fetchNodeDetail(type, refId)
      .then(setDetail)
      .catch((e) => setError(String(e)));
  }, []);

  // (re)draw cytoscape when the merged element set changes
  useEffect(() => {
    if (mode !== "canvas" || !containerRef.current) return;
    cyRef.current?.destroy();
    const elements = [
      ...[...merged.nodes.values()].map((n) => ({
        data: { id: n.node_id, label: n.label, type: n.node_type, ref: n.entity_ref_id },
      })),
      ...[...merged.edges.values()].map((e) => ({
        data: {
          id: e.edge_id,
          source: e.source,
          target: e.target,
          classification: e.classification,
          rel: e.relationship_type,
        },
      })),
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: "cose", animate: false, padding: 40 },
      wheelSensitivity: 0.2,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 9,
            color: "#dce3ea",
            "text-wrap": "ellipsis",
            "text-max-width": "110px",
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: 22,
            height: 22,
            "background-color": (el: cytoscape.NodeSingular) =>
              NODE_COLORS[el.data("type") as string] ?? "#888",
            "border-width": 1,
            "border-color": "#1c232b",
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#e8eef4" },
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
            opacity: 0.85,
          },
        },
        { selector: "edge:selected", style: { opacity: 1, width: 5 } },
      ],
    });
    cy.on("tap", "node", (ev) => {
      const [type, ...rest] = (ev.target.id() as string).split(":");
      openNode(type as NodeType, rest.join(":"));
    });
    cy.on("tap", "edge", (ev) => {
      const e = merged.edges.get(ev.target.id() as string);
      if (e) {
        setDetail(null);
        setEdgeDetail(e);
      }
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [merged, mode, openNode]);

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
            onChange={(e) => setSeedType(e.target.value as NodeType)}
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
            placeholder="record id, e.g. 5001"
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
