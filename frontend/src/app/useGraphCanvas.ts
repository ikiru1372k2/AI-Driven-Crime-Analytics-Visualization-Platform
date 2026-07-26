/**
 * Cytoscape lifecycle for GraphView, as a hook.
 *
 * Owns the cy instance: (re)builds it when the merged element set changes,
 * wires taps/hovers to the component's callbacks, and runs the zoom-to-cluster
 * animation when a node is focused. Extracted so GraphView stays under the
 * source-size gate; the interaction wiring itself lives in initCytoscape.
 */
import { type Core } from "cytoscape";
import { type MutableRefObject, type RefObject, useEffect } from "react";
import type { GraphEdge, GraphNode, NodeType } from "../lib/graphApi";
import { initCytoscape, type HoverInfo } from "./graphCytoscape";

export interface GraphCanvasParams {
  containerRef: RefObject<HTMLDivElement | null>;
  cyRef: MutableRefObject<Core | null>;
  merged: { nodes: Map<string, GraphNode>; edges: Map<string, GraphEdge> };
  viewDims: Set<string>;
  expandable: Record<string, number>;
  expandedSet: Set<string>;
  seedType: NodeType;
  seedId: string;
  theme: "dark" | "light";
  focusId: string | null;
  focusIdRef: { current: string | null };
  seedRef: { current: { type: NodeType; id: string } };
  onExpand: (type: NodeType, ref: string) => void;
  onOpenNode: (type: NodeType, ref: string) => void;
  onOpenPerson: (role: "accused" | "victim", ref: string) => void;
  clearPanels: () => void;
  setShowDetail: (v: boolean) => void;
  setEdgeDetail: (e: GraphEdge | null) => void;
  setHover: (h: HoverInfo | null) => void;
}

export function useGraphCanvas(p: GraphCanvasParams): void {
  const {
    containerRef, cyRef, merged, viewDims, expandable, expandedSet,
    seedType, seedId, theme, focusId, focusIdRef, seedRef,
    onExpand, onOpenNode, onOpenPerson, clearPanels,
    setShowDetail, setEdgeDetail, setHover,
  } = p;

  // (re)draw cytoscape when the merged element set changes. All layout/style and
  // event wiring lives in initCytoscape; we supply live refs + the callbacks
  // that turn taps/hovers into state changes.
  useEffect(() => {
    if (!containerRef.current) return;
    cyRef.current?.destroy();
    const cy = initCytoscape(containerRef.current, {
      merged,
      viewDims,
      expandable,
      expandedSet,
      seedNodeId: `${seedType}:${seedId}`,
      theme,
      focusIdRef,
      seedRef,
      onExpand,
      onOpenNode: (type, ref) => {
        onOpenNode(type, ref);
        setShowDetail(true);
      },
      onOpenPerson,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [merged, onOpenNode, onOpenPerson, onExpand, clearPanels, expandable, theme, viewDims, seedType, seedId]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, merged]);
}
