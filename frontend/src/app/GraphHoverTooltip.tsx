/** The floating node-hover card for the association graph. Extracted from
 *  GraphView so that component stays under the source-size gate. Presentational:
 *  it reads a HoverInfo and shows the node type, label, and the tap hint. */
import type { HoverInfo } from "./graphCytoscape";

export function GraphHoverTooltip({ hover }: { hover: HoverInfo }) {
  const hint =
    hover.type === "ACCUSED_RECORD" || hover.type === "VICTIM_RECORD"
      ? "click to view this person"
      : hover.expandable
        ? "click to expand related cases"
        : "click to view details";
  return (
    <div className="graph-tooltip" style={{ left: hover.x, top: hover.y }} aria-hidden="true">
      <span className="tt-type">{hover.type.replace(/_/g, " ").toLowerCase()}</span>
      <span className="tt-label">{hover.label}</span>
      <span className="tt-hint">{hint}</span>
    </div>
  );
}
