/**
 * Cytoscape instance factory for the association graph.
 *
 * Builds the cy instance (elements, layout, style) and wires all pointer
 * events, delegating every state change back to the GraphView component via
 * callbacks. Kept out of GraphView.tsx so the component stays focused on state
 * and layout; the interaction contract is the `CyParams` object below.
 */
import cytoscape, { type Core } from "cytoscape";
import type { GraphEdge, GraphNode, NodeType } from "../lib/graphApi";
import { buildCyStyle, buildGraphElements } from "./graphConfig";

/** Floating info card shown while hovering a node. */
export interface HoverInfo {
  x: number;
  y: number;
  label: string;
  type: string;
  expand: number;
}

export interface CyParams {
  merged: { nodes: Map<string, GraphNode>; edges: Map<string, GraphEdge> };
  viewDims: Set<string>;
  expandable: Record<string, number>;
  expandedSet: Set<string>;
  seedNodeId: string;
  theme: "dark" | "light";
  /** live refs so handlers see the current focus/seed, not the init-time value */
  focusIdRef: { current: string | null };
  seedRef: { current: { type: NodeType; id: string } };
  onExpand: (type: NodeType, ref: string) => void;
  onOpenNode: (type: NodeType, ref: string) => void;
  onEdgeTap: (edgeId: string) => void;
  onCanvasTap: () => void;
  onHover: (h: HoverInfo | null) => void;
}

/** The central node (focused hub, or the seed case on the overview) — the
 *  subject already in view, so it gets no tooltip and no detail card. */
function centralIdOf(p: CyParams): string {
  return p.focusIdRef.current ?? `${p.seedRef.current.type}:${p.seedRef.current.id}`;
}

/** Create a Cytoscape instance for the merged graph and bind all events.
 *  Caller owns the returned instance and must `.destroy()` it. */
export function initCytoscape(container: HTMLDivElement, p: CyParams): Core {
  // View projection + degree sizing + expandable badges (see buildGraphElements)
  const elements = buildGraphElements(
    p.merged,
    p.viewDims,
    p.expandable,
    p.expandedSet,
    p.seedNodeId,
  );
  const cy = cytoscape({
    container,
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
      // deterministic start: same subgraph → same layout every load, instead of
      // reshuffling on each redraw (random seed positions make cose settle
      // differently every run even for identical nodes/edges)
      randomize: false,
      fit: true,
    },
    minZoom: 0.2,
    maxZoom: 2.5,
    wheelSensitivity: 0.2,
    style: buildCyStyle(p.theme) as cytoscape.StylesheetStyle[],
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
    p.onHover(null);
    if (id === centralIdOf(p)) return;
    // an expandable hub always routes through expand(): first tap reveals its
    // related cases, a repeat tap just re-focuses/zooms (no detail popover).
    // Only leaf nodes (cases, non-variant people) open the detail card.
    if ((p.expandable[id] ?? 0) > 0) p.onExpand(type, ref);
    else p.onOpenNode(type, ref);
  });
  cy.on("tap", "edge", (ev) => p.onEdgeTap(ev.target.id() as string));
  // tap empty canvas: just dismiss any open detail — keep the current focus
  // and its zoom/dimming (use Back to leave a cluster; clicking away should
  // not suddenly reveal every other case's details)
  cy.on("tap", (ev) => {
    if (ev.target === cy) p.onCanvasTap();
  });
  // hover: reveal the node's label + connections, and float a small info card
  cy.on("mouseover", "node", (ev) => {
    ev.target.addClass("hover");
    ev.target.connectedEdges().addClass("incident");
    cy.container()!.style.cursor = "pointer";
    if (ev.target.id() === centralIdOf(p)) return;
    const rp = ev.renderedPosition;
    if (rp) {
      const id = ev.target.id() as string;
      p.onHover({
        x: rp.x,
        y: rp.y,
        label: ev.target.data("label") as string,
        type: ev.target.data("type") as string,
        expand: p.expandedSet.has(id) ? 0 : p.expandable[id] ?? 0,
      });
    }
  });
  cy.on("mouseout", "node", (ev) => {
    ev.target.removeClass("hover");
    ev.target.connectedEdges().removeClass("incident");
    cy.container()!.style.cursor = "";
    p.onHover(null);
  });
  return cy;
}
