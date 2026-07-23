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
import { type Core } from "cytoscape";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchAssociations,
  fetchCaseBasic,
  fetchClassifications,
  fetchNodeDetail,
  fetchPerson,
  fetchSubgraph,
  type AssocFilters,
  type CaseBasic,
  type GraphEdge,
  type GraphNode,
  type NodeDetail,
  type NodeType,
  type PersonDetail,
  type Subgraph,
} from "../lib/graphApi";
import { useCachedQuery } from "../lib/queryCache";
import { GraphControls } from "./GraphControls";
import { GraphDetailPanel } from "./GraphDetailPanel";
import { GraphHoverTooltip } from "./GraphHoverTooltip";
import { GraphRail } from "./GraphRail";
import { Spinner } from "./Loading";
import {
  ALL_VIEW_KEYS,
  buildPersonGraph,
  canNavigateNode,
  DEFAULT_SEED_CASE,
  expandLoadingMessage,
  type ViewSnapshot,
} from "./graphConfig";
import { initCytoscape, type HoverInfo } from "./graphCytoscape";
import { buildPreFilter, type SeedAttrs } from "./graphPreFilter";

export interface GraphSeed {
  type: NodeType;
  id: string;
}

/** Related cases per expansion page — keeps the graph readable and instant to
 *  render even when an entity has hundreds of cases; page through the rest. */
const PAGE_SIZE = 60;

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
  // Legend is tiny and static — cache it so tab revisits don't refetch (PERF-001).
  const { data: legend = [] } = useCachedQuery("graph:classifications", fetchClassifications);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [caseBasic, setCaseBasic] = useState<CaseBasic | null>(null);
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [edgeDetail, setEdgeDetail] = useState<GraphEdge | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [viewDims, setViewDims] = useState<Set<string>>(() => new Set(ALL_VIEW_KEYS));
  const [filters, setFilters] = useState<AssocFilters>({});
  const [resultCount, setResultCount] = useState<number | null>(null);
  // expandable flag per entity node_id (1 = has more to reveal). No counts
  // (PERF-001) — it only gates whether a tap expands vs opens details.
  const [expandable, setExpandable] = useState<Record<string, number>>({});
  // whether we've drilled into an entity (View belongs to the overview only)
  const [drilled, setDrilled] = useState(false);
  // pagination of an expansion's related cases (a district can have hundreds)
  const [page, setPage] = useState(0);
  const [pageInfo, setPageInfo] = useState<{ total: number; offset: number; count: number } | null>(
    null,
  );
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const [focusId, setFocusId] = useState<string | null>(null);
  const focusIdRef = useRef(focusId);
  focusIdRef.current = focusId;
  // mirror the stats/view state into refs so a snapshot can capture the view
  // being LEFT (Back must restore each view's own stats, not the last one seen)
  const pageInfoRef = useRef(pageInfo);
  pageInfoRef.current = pageInfo;
  const expandableRef = useRef(expandable);
  expandableRef.current = expandable;
  const pageRef = useRef(page);
  pageRef.current = page;
  const drilledRef = useRef(drilled);
  drilledRef.current = drilled;
  const resultCountRef = useRef(resultCount);
  resultCountRef.current = resultCount;
  // remember which nodes we've already expanded so a repeat click just refocuses
  const expandedRef = useRef(new Set<string>());
  // the entity currently in focus — what a Filter narrows (the last one opened)
  const activeFocusRef = useRef<string | null>(null);
  // the seed case's own attributes (from the overview) — used to pre-apply a
  // "similar cases" filter (its crime type, district and the suspect's profile)
  // when the user expands an entity (see buildPreFilter)
  const seedAttrsRef = useRef<SeedAttrs | null>(null);
  // Default filter for a fresh expansion: the seed's similar-profile set. Seed
  // attributes come from the overview load, else fall back to the graph's own
  // crime-type + district nodes (see graphPreFilter).
  const preFilterFor = useCallback(
    (type: NodeType): AssocFilters =>
      buildPreFilter(type, seedAttrsRef.current, mergedRef.current.nodes.values()),
    [],
  );
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [seedType, setSeedType] = useState<NodeType>(seed?.type ?? "CASE");
  const [seedId, setSeedId] = useState<string>(seed?.id ?? "");
  const [loading, setLoading] = useState(false);
  // A specific message for the centered loading cover, set per action so the
  // user knows exactly what's being fetched ("Loading theft cases similar to
  // this case…", "Filtering cases, please wait…").
  const [loadingMsg, setLoadingMsg] = useState("Loading…");
  const [error, setError] = useState<string | null>(null);
  // previous views (graph + seed) so Back restores the prior view AND the seed
  const mergedRef = useRef(merged);
  const seedRef = useRef({ type: seedType, id: seedId });
  // Back stack of ViewSnapshots (see graphConfig) — restores a view exactly.
  const historyRef = useRef<ViewSnapshot[]>([]);
  useEffect(() => {
    mergedRef.current = merged;
  }, [merged]);
  useEffect(() => {
    seedRef.current = { type: seedType, id: seedId };
  }, [seedType, seedId]);

  // capture the current view before an action changes it. Reads only refs, so
  // it MUST run before those refs are mutated toward the next view.
  const snapshot = useCallback(() => {
    if (mergedRef.current.nodes.size > 0) {
      historyRef.current.push({
        nodes: mergedRef.current.nodes,
        edges: mergedRef.current.edges,
        type: seedRef.current.type,
        id: seedRef.current.id,
        pageInfo: pageInfoRef.current,
        activeFocus: activeFocusRef.current,
        focusId: focusIdRef.current,
        expandable: expandableRef.current,
        page: pageRef.current,
        drilled: drilledRef.current,
        filters: filtersRef.current,
        resultCount: resultCountRef.current,
      });
    }
  }, []);

  // drop every detail-panel subject at once (a click always replaces the panel).
  const clearPanels = useCallback(() => {
    setDetail(null);
    setCaseBasic(null);
    setPerson(null);
    setEdgeDetail(null);
  }, []);

  const load = useCallback(
    async (type: NodeType, id: string, merge = false) => {
      if (!merge) setLoadingMsg("Loading case overview…");
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
          // cases yet). Each entity is flagged `expandable` (no counts —
          // PERF-001); clicking it pulls its related cases (progressive, like
          // zooming a map). Filters belong to the expanded level, so the
          // overview ignores them.
          const a = await fetchAssociations(id);
          gNodes = a.nodes;
          gEdges = a.edges;
          setSubgraph(null);
          setExpandable(a.expandable ?? {});
          // the overview computes no related-case universe (PERF-001) — the
          // stats bar only appears once an entity is expanded.
          setResultCount(null);
          // remember the seed's attributes so expansions can pre-filter to its
          // crime type (see preFilterFor / expand); buildPreFilter reads only the
          // profile fields, so passing the whole seed object is harmless.
          seedAttrsRef.current = a.seed;
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
        if (!merge) clearPanels();
      } catch (e) {
        setError(String(e instanceof Error ? e.message : e));
      } finally {
        setLoading(false);
      }
    },
    [clearPanels],
  );

  // Show ONE entity's expansion (a place or charge) as a self-contained view:
  // the focus entity, the seed case, and the related cases; sibling entities
  // dropped. It REPLACES the graph (Back returns to the overview). Persons never
  // reach here — they route to openPerson (their own detail + cases).
  const showFocus = useCallback(async (focus: string, pg = 0) => {
    setLoading(true);
    setError(null);
    try {
      const id = seedRef.current.id;
      const ex = await fetchAssociations(id, filtersRef.current, focus, {
        limit: PAGE_SIZE,
        offset: pg * PAGE_SIZE,
      });
      setExpandable(ex.expandable ?? {});
      // Keep the focus entity, the seed case, and the related cases; drop the
      // sibling entities so the expansion reads as a self-contained cluster.
      const seedNodeId = `CASE:${id}`;
      const nodes = new Map<string, GraphNode>();
      const edges = new Map<string, GraphEdge>();
      const keep = (n: GraphNode) =>
        n.node_id === focus || n.node_id === seedNodeId || n.node_type === "CASE";
      ex.nodes.forEach((n) => {
        if (keep(n)) nodes.set(n.node_id, n);
      });
      ex.edges.forEach((e) => {
        if (nodes.has(e.source) && nodes.has(e.target)) edges.set(e.edge_id, e);
      });
      setResultCount(ex.total_matches);
      setPage(pg);
      setPageInfo({ total: ex.total_matches, offset: ex.offset, count: ex.association_count });
      setMerged({ nodes, edges }); // REPLACE — not merged onto the overview
      expandedRef.current = new Set([focus]);
      setFocusId(null); // whole view is the expansion → fit it, no cluster dimming
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Applying a Filter re-runs the current expansion from the first page.
  const reloadExpansionsFiltered = useCallback(async () => {
    if (activeFocusRef.current) {
      setLoadingMsg("Filtering cases, please wait…");
      await showFocus(activeFocusRef.current, 0);
    }
  }, [showFocus]);
  // page through a large expansion
  const gotoPage = useCallback(
    (pg: number) => {
      if (activeFocusRef.current) {
        setLoadingMsg("Loading more cases…");
        void showFocus(activeFocusRef.current, pg);
      }
    },
    [showFocus],
  );

  // seed from URL/props, else bootstrap from the sample case (its accused is
  // "Ravi Kumar" — the same fragmented identity shown on the Identities tab)
  useEffect(() => {
    if (seed) {
      setSeedType(seed.type);
      setSeedId(seed.id);
      expandedRef.current.clear(); // fresh seed = fresh graph
      activeFocusRef.current = null;
      setDrilled(false); // back to the overview → View control returns
      setPageInfo(null);
      setFocusId(null); // drop any prior zoom-to-cluster so the new seed shows in full
      firstFilter.current = true; // don't let a reset fire the filter effect
      setFilters({}); // filters belong to an expansion; the overview starts clean
      void load(seed.type, seed.id);
    } else {
      onSeed({ type: "CASE", id: DEFAULT_SEED_CASE });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.type, seed?.id]);

  const openNode = useCallback(
    (type: NodeType, refId: string) => {
      clearPanels();
      setShowDetail(false); // load it, but keep it behind the info button until asked
      if (type === "CASE") {
        // A case click shows the FIR at a glance — served instantly from the warm
        // case cache (no heavy graph metrics / cross-FIR linking — PERF-001).
        fetchCaseBasic(refId)
          .then((r) => setCaseBasic(r.case))
          .catch((e) => setError(String(e)));
        return;
      }
      fetchNodeDetail(type, refId)
        .then(setDetail)
        .catch((e) => setError(String(e)));
    },
    [clearPanels],
  );

  // A person click opens that accused/victim's detail + the cases sharing their
  // exact name+age+gender (never the old similar-people expansion).
  const openPerson = useCallback((role: "accused" | "victim", refId: string) => {
    fetchPerson(role, refId)
      .then((r) => {
        setPerson(r.person);
        setShowDetail(true);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // "Show their N cases": a person-centered view (person + one node per case).
  const showPersonCases = useCallback(
    (p: PersonDetail) => {
      snapshot();
      const { nodes, edges, centerId } = buildPersonGraph(p);
      setShowDetail(false);
      setMerged({ nodes, edges });
      setDrilled(true);
      setFocusId(centerId);
      setExpandable({});
      setPageInfo(null);
      setResultCount(null);
      activeFocusRef.current = null;
    },
    [snapshot],
  );

  // navigate (reseed) / expand (merge) — both snapshot first so Back can undo
  const navigate = useCallback(
    (s: GraphSeed) => {
      snapshot();
      onSeed(s);
    },
    [snapshot, onSeed],
  );
  const expand = useCallback(
    (type: NodeType, id: string) => {
      const key = `${type}:${id}`;
      if (expandedRef.current.has(key)) {
        // already loaded — just refocus/zoom, no new history entry
        setFocusId(key);
        activeFocusRef.current = key;
        return;
      }
      // snapshot the view we're leaving BEFORE mutating focus/drill state, so
      // its own stats are what Back restores (not this new expansion's).
      snapshot();
      setFocusId(key); // zoom to this node's cluster
      activeFocusRef.current = key; // this becomes the Filter's target
      expandedRef.current.add(key);
      setDrilled(true); // we've left the overview → hide the View control
      if (seedRef.current.type !== "CASE") {
        void load(type, id, true); // non-CASE seed → base subgraph
        return;
      }
      // A fresh expansion is pre-scoped to the seed case's crime type, so it
      // surfaces SIMILAR cases by default ("did a similar case happen in this
      // district / did this person commit similar crimes?"). The user can widen
      // it via the Filter control. This replaces any filter left from a prior one.
      const pre = preFilterFor(type);
      filtersRef.current = pre;
      firstFilter.current = true; // we load below; don't double-fire the filter effect
      setFilters(pre);
      const label = mergedRef.current.nodes.get(key)?.label ?? "";
      setLoadingMsg(expandLoadingMessage(type, label));
      void showFocus(key, 0);
    },
    [snapshot, load, showFocus, preFilterFor],
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
    cy?.elements().removeClass("dim");
    // the level we're leaving must be re-expandable from scratch on a later click
    const leaving = activeFocusRef.current;
    const prev = historyRef.current.pop();
    if (prev) {
      setMerged({ nodes: prev.nodes, edges: prev.edges });
      setSeedType(prev.type);
      setSeedId(prev.id);
      // restore the view's OWN stats/zoom state so the bar matches what's shown
      setFocusId(prev.focusId);
      activeFocusRef.current = prev.activeFocus;
      setPageInfo(prev.pageInfo);
      setPage(prev.page);
      setExpandable(prev.expandable);
      setResultCount(prev.resultCount);
      setDrilled(prev.drilled);
      firstFilter.current = true; // restoring filters must not re-run the expansion
      setFilters(prev.filters);
      if (leaving) expandedRef.current.delete(leaving);
      // the first snapshot is always the overview, so an empty stack == overview
      if (historyRef.current.length === 0) expandedRef.current.clear();
    } else {
      setFocusId(null);
      cy?.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 350 });
    }
  }, []);

  // (re)draw cytoscape when the merged element set changes. All layout/style
  // and event wiring lives in initCytoscape; the component supplies live refs
  // and the callbacks that turn taps/hovers into state changes.
  useEffect(() => {
    if (!containerRef.current) return;
    cyRef.current?.destroy();
    const cy = initCytoscape(containerRef.current, {
      merged,
      viewDims,
      expandable,
      expandedSet: expandedRef.current,
      seedNodeId: `${seedType}:${seedId}`,
      theme,
      focusIdRef,
      seedRef,
      onExpand: expand,
      onOpenNode: (type, ref) => {
        openNode(type, ref);
        setShowDetail(true);
      },
      onOpenPerson: openPerson,
      onEdgeTap: (edgeId) => {
        const e = merged.edges.get(edgeId);
        if (e) {
          clearPanels();
          setEdgeDetail(e);
          setShowDetail(false); // surface via the info button, open on click
        }
      },
      onCanvasTap: () => {
        clearPanels();
        setShowDetail(false);
      },
      onHover: setHover,
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [merged, openNode, openPerson, expand, clearPanels, expandable, theme, viewDims, seedType, seedId]);

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
  // label of the entity currently expanded (for the stats bar)
  const focusLabel = activeFocusRef.current
    ? merged.nodes.get(activeFocusRef.current)?.label ?? ""
    : "";
  // the expanded entity's type — its own attribute is redundant to filter on
  // (every result already shares it), so that field is hidden in the Filter
  const focusType = (activeFocusRef.current?.split(":")[0] as NodeType | undefined) ?? null;

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
          expandedType={focusType}
        />
        {drilled && pageInfo && (
          <div className="graph-stats" role="status">
            {focusLabel ? `${focusLabel} · ` : ""}
            {pageInfo.total} case{pageInfo.total === 1 ? "" : "s"}
            {pageInfo.total > PAGE_SIZE
              ? ` (showing ${pageInfo.offset + 1}–${pageInfo.offset + pageInfo.count})`
              : ""}
          </div>
        )}
        {hover && <GraphHoverTooltip hover={hover} />}
        <div ref={containerRef} className="graph-canvas" aria-label="Association graph canvas" />
        {loading && (
          <div className="graph-loading" role="status" aria-live="polite">
            <Spinner label={loadingMsg} />
          </div>
        )}

        {drilled && pageInfo && pageInfo.total > PAGE_SIZE && (
          <div className="graph-pager" role="navigation" aria-label="Case pages">
            <button disabled={page === 0 || loading} onClick={() => gotoPage(page - 1)}>
              &#8249; Prev
            </button>
            <span>
              Page {page + 1} / {Math.ceil(pageInfo.total / PAGE_SIZE)}
            </span>
            <button
              disabled={(page + 1) * PAGE_SIZE >= pageInfo.total || loading}
              onClick={() => gotoPage(page + 1)}
            >
              Next &#8250;
            </button>
          </div>
        )}

        {showDetail && (
          <GraphDetailPanel
            detail={detail}
            edgeDetail={edgeDetail}
            caseBasic={caseBasic}
            person={person}
            canNavigate={canNavigateNode(detail?.node, expandable, merged.edges)}
            onClose={() => setShowDetail(false)}
            onNavigate={(type, id) => {
              setShowDetail(false);
              navigate({ type, id });
            }}
            onNavigateCase={(id) => navigate({ type: "CASE", id })}
            onShowPersonCases={showPersonCases}
          />
        )}
      </div>
    </div>
  );
}
