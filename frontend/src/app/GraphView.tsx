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
 */
import cytoscape, { type Core } from "cytoscape";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchAssociations,
  fetchClassifications,
  fetchNodeDetail,
  fetchSubgraph,
  type AssocFilters,
  type ClassificationInfo,
  type GraphEdge,
  type GraphNode,
  type NodeDetail,
  type NodeType,
  type Subgraph,
} from "../lib/graphApi";
import { GraphControls } from "./GraphControls";
import { GraphDetailPanel } from "./GraphDetailPanel";
import { GraphRail } from "./GraphRail";
import {
  ALL_VIEW_KEYS,
  buildCyStyle,
  buildGraphElements,
  canNavigateNode,
  DEFAULT_SEED_CASE,
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
  const [viewDims, setViewDims] = useState<Set<string>>(() => new Set(ALL_VIEW_KEYS));
  const [filters, setFilters] = useState<AssocFilters>({});
  const [resultCount, setResultCount] = useState<number | null>(null);
  // related-case count per entity node_id (overview hint / node badge)
  const [expandable, setExpandable] = useState<Record<string, number>>({});
  // whether we've drilled into an entity (View belongs to the overview only)
  const [drilled, setDrilled] = useState(false);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const [focusId, setFocusId] = useState<string | null>(null);
  const focusIdRef = useRef(focusId);
  focusIdRef.current = focusId;
  const [hover, setHover] = useState<
    { x: number; y: number; label: string; type: string; expand: number } | null
  >(null);
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
        // A CASE seed uses the association engine (same-suspect + shared
        // entities + orthogonal filters); other node types use the base
        // subgraph. depth 1 = the record's own direct links; expand to explore.
        let gNodes: GraphNode[];
        let gEdges: GraphEdge[];
        if (type === "CASE") {
          // OVERVIEW: the seed case + its own entities only (no associated
          // cases yet). Each entity carries an `expandable` count; clicking it
          // pulls its related cases (progressive, like zooming a map). Filters
          // belong to the expanded level, so the overview ignores them.
          const a = await fetchAssociations(id);
          gNodes = a.nodes;
          gEdges = a.edges;
          setSubgraph(null);
          setExpandable(a.expandable ?? {});
          setResultCount(a.total_related);
        } else {
          const sg = await fetchSubgraph(type, id, { depth: 1, limit: 40 });
          setSubgraph(sg);
          setResultCount(null);
          gNodes = sg.nodes;
          gEdges = sg.edges;
        }
        setMerged((prev) => {
          const nodes = merge ? new Map(prev.nodes) : new Map<string, GraphNode>();
          const edges = merge ? new Map(prev.edges) : new Map<string, GraphEdge>();
          gNodes.forEach((n) => nodes.set(n.node_id, n));
          gEdges.forEach((e) => edges.set(e.edge_id, e));
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

  // Expand one entity of a CASE-seeded overview into its related cases
  // (server-side, via ?focus=TYPE:id), merged into the current graph.
  const loadFocus = useCallback(async (focus: string) => {
    setLoading(true);
    setError(null);
    try {
      const a = await fetchAssociations(seedRef.current.id, filtersRef.current, focus);
      if (a.expandable) setExpandable((prev) => ({ ...prev, ...a.expandable }));
      setResultCount(a.association_count); // cases revealed in this expansion (filterable)
      setMerged((prev) => {
        const nodes = new Map(prev.nodes);
        const edges = new Map(prev.edges);
        a.nodes.forEach((n) => nodes.set(n.node_id, n));
        a.edges.forEach((e) => edges.set(e.edge_id, e));
        return { nodes, edges };
      });
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Re-apply the current attribute filters to whatever has been expanded:
  // rebuild the overview base (seed + its entities, unfiltered) and re-expand
  // every drilled entity WITH the filters. Filter lives at the expanded level —
  // "show all cases in this district, then narrow them".
  const reloadExpansionsFiltered = useCallback(async () => {
    // Filter narrows the CURRENT expansion only (the entity you last opened),
    // not everything ever expanded — otherwise filtering a station's cases
    // would also drag in a previously-opened district's cases.
    const focus = activeFocusRef.current;
    if (!focus) return;
    setLoading(true);
    setError(null);
    try {
      const id = seedRef.current.id;
      const ex = await fetchAssociations(id, filtersRef.current, focus);
      setExpandable(ex.expandable ?? {});
      // Show ONLY what the filter matched: the seed case, the focus entity and
      // the matching related cases (plus the identity chain for an accused
      // focus). Drop the seed's other sibling entities so the view is exactly
      // "the cases that passed the filter", nothing else.
      const isAccused = focus.startsWith("ACCUSED_RECORD:");
      const keep = (n: GraphNode) =>
        n.node_id === focus ||
        n.node_type === "CASE" ||
        (isAccused && n.node_type === "ACCUSED_RECORD");
      const nodes = new Map<string, GraphNode>();
      const edges = new Map<string, GraphEdge>();
      ex.nodes.forEach((n) => {
        if (keep(n)) nodes.set(n.node_id, n);
      });
      ex.edges.forEach((e) => {
        if (nodes.has(e.source) && nodes.has(e.target)) edges.set(e.edge_id, e);
      });
      setResultCount(ex.association_count);
      setMerged({ nodes, edges });
      // collapse the others back to badges; only the filtered focus stays open
      expandedRef.current = new Set([focus]);
      setFocusId(null); // a filter acts on the whole expansion — show it all, not one cluster
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }, []);

  // seed from URL/props, else bootstrap from the sample case (its accused is
  // "Ravi Kumar" — the same fragmented identity shown on the Identities tab)
  useEffect(() => {
    if (seed) {
      setSeedType(seed.type);
      setSeedId(seed.id);
      expandedRef.current.clear(); // fresh seed = fresh graph
      activeFocusRef.current = null;
      setDrilled(false); // back to the overview → View control returns
      setFocusId(null); // drop any prior zoom-to-cluster so the new seed shows in full
      firstFilter.current = true; // don't let a reset fire the filter effect
      setFilters({}); // filters belong to an expansion; the overview starts clean
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
      onSeed(s);
    },
    [snapshot, onSeed],
  );
  // remember which nodes we've already expanded so a repeat click just refocuses
  const expandedRef = useRef(new Set<string>());
  // the entity currently in focus — what a Filter narrows (the last one opened)
  const activeFocusRef = useRef<string | null>(null);
  const expand = useCallback(
    (type: NodeType, id: string) => {
      const key = `${type}:${id}`;
      setFocusId(key); // zoom to this node's cluster
      activeFocusRef.current = key; // this becomes the Filter's target
      if (expandedRef.current.has(key)) return; // already loaded — just refocus
      expandedRef.current.add(key);
      setDrilled(true); // we've left the overview → hide the View control
      snapshot();
      // In an association (CASE-seeded) view, expand the entity into its related
      // cases via the association engine; otherwise fall back to the base subgraph.
      if (seedRef.current.type === "CASE") void loadFocus(key);
      else void load(type, id, true);
    },
    [snapshot, load, loadFocus],
  );

  // Applying a Filter narrows the cases in whatever you've expanded (Filter
  // lives at the expanded level — expand a district, then filter its cases).
  // At the overview there's nothing expanded, so it's a no-op. Skips the first
  // render so it doesn't double-load with the seed effect.
  const firstFilter = useRef(true);
  useEffect(() => {
    if (firstFilter.current) {
      firstFilter.current = false;
      return;
    }
    void reloadExpansionsFiltered();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

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
      // the first snapshot is always the overview, so an empty stack == overview
      if (historyRef.current.length === 0) {
        setDrilled(false);
        expandedRef.current.clear();
        activeFocusRef.current = null;
        firstFilter.current = true;
        setFilters({}); // back at the overview → clear the expansion-level filter
      }
    } else {
      cy?.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 350 });
    }
  }, []);

  // (re)draw cytoscape when the merged element set changes
  useEffect(() => {
    if (!containerRef.current) return;
    cyRef.current?.destroy();
    // View projection + degree sizing + expandable badges (see buildGraphElements)
    const seedNodeId = `${seedType}:${seedId}`;
    const elements = buildGraphElements(
      merged,
      viewDims,
      expandable,
      expandedRef.current,
      seedNodeId,
    );
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
    // tap a node:
    //  - an entity with related cases still to reveal -> expand it (zoom in +
    //    draw its related cases), staying on the same seed (NOT a rabbit hole);
    //  - anything else (cases, exhausted entities) -> open its details popover.
    // Navigation to a new seed happens only from the button inside the popover.
    cy.on("tap", "node", (ev) => {
      const type = ev.target.data("type") as NodeType;
      const ref = ev.target.data("ref") as string;
      const id = ev.target.id() as string;
      setHover(null);
      // the central node (the focused hub, or the seed case on the overview) is
      // the subject you're already looking at — no detail card for it.
      const centralId = focusIdRef.current ?? `${seedRef.current.type}:${seedRef.current.id}`;
      if (id === centralId) return;
      // an expandable hub always routes through expand(): first tap reveals its
      // related cases, a repeat tap just re-focuses/zooms (no detail popover).
      // Only leaf nodes (cases, non-variant people) open the detail card.
      if ((expandable[id] ?? 0) > 0) {
        expand(type, ref);
      } else {
        openNode(type, ref);
        setShowDetail(true);
      }
    });
    cy.on("tap", "edge", (ev) => {
      const e = merged.edges.get(ev.target.id() as string);
      if (e) {
        setDetail(null);
        setEdgeDetail(e);
        setShowDetail(false); // surface via the info button, open on click
      }
    });
    // tap empty canvas: just dismiss any open detail — keep the current focus
    // and its zoom/dimming (use Back to leave a cluster; clicking away should
    // not suddenly reveal every other case's details)
    cy.on("tap", (ev) => {
      if (ev.target === cy) {
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
      // the central node (focused hub, or the seed case on the overview) is
      // already the subject — no tooltip for it
      const centralId = focusIdRef.current ?? `${seedRef.current.type}:${seedRef.current.id}`;
      if (ev.target.id() === centralId) return;
      const rp = ev.renderedPosition;
      if (rp) {
        const id = ev.target.id() as string;
        setHover({
          x: rp.x,
          y: rp.y,
          label: ev.target.data("label") as string,
          type: ev.target.data("type") as string,
          expand: expandedRef.current.has(id) ? 0 : expandable[id] ?? 0,
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
  }, [merged, openNode, expand, expandable, theme, viewDims, seedType, seedId]);

  // zoom-to-cluster: when a node is focused (tapped), dim the rest and animate
  // the camera to fit that node and its linked records
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    // no focus → whole graph is the subject: clear any dimming and show all
    if (!focusId) {
      cy.elements().removeClass("dim");
      cy.nodes(":selected").unselect();
      return;
    }
    const node = cy.getElementById(focusId);
    if (node.empty()) return;
    const cluster = node.closedNeighborhood();
    cy.elements().removeClass("dim");
    cy.elements().not(cluster).addClass("dim");
    node.select();
    cy.animate({ fit: { eles: cluster, padding: 90 }, duration: 550, easing: "ease-in-out" });
  }, [focusId, merged]);

  const stubs = subgraph?.stubs;

  return (
    <div className="body graph-body">
      <GraphRail
        seedType={seedType}
        seedId={seedId}
        setSeedType={setSeedType}
        setSeedId={setSeedId}
        navigate={navigate}
        loading={loading}
        legend={legend}
        stubs={stubs}
        expand={expand}
        error={error}
      />

      <div className="graph-stage">
        {drilled && (
          <button className="graph-zoomout" onClick={goBack} title="Back to the previous view">
            &#8592; Back
          </button>
        )}
        <GraphControls
          showView={!drilled}
          showFilter={drilled}
          viewDims={viewDims}
          onToggleDim={(k) =>
            setViewDims((prev) => {
              const s = new Set(prev);
              if (s.has(k)) s.delete(k);
              else s.add(k);
              return s;
            })
          }
          filters={filters}
          onApplyFilters={setFilters}
          resultCount={resultCount}
        />
        {hover && (
          <div
            className="graph-tooltip"
            style={{ left: hover.x, top: hover.y }}
            aria-hidden="true"
          >
            <span className="tt-type">{hover.type.replace(/_/g, " ").toLowerCase()}</span>
            <span className="tt-label">{hover.label}</span>
            <span className="tt-hint">
              {hover.expand > 0
                ? hover.type === "ACCUSED_RECORD" || hover.type === "VICTIM_RECORD"
                  ? `click to expand ${hover.expand} similar person${hover.expand > 1 ? "s" : ""}`
                  : `click to expand ${hover.expand} related case${hover.expand > 1 ? "s" : ""}`
                : "click to view details"}
            </span>
          </div>
        )}
        <div ref={containerRef} className="graph-canvas" aria-label="Association graph canvas" />

        {showDetail && (
          <GraphDetailPanel
            detail={detail}
            edgeDetail={edgeDetail}
            canNavigate={canNavigateNode(detail?.node, expandable, merged.edges)}
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
