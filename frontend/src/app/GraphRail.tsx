/** Left rail for the association graph: seed form, canvas/list toggle, edge
 *  classification legend, and "not shown" stubs. Extracted from GraphView so
 *  that component stays under the source-size gate. */
import type { ClassificationInfo, NodeType, Subgraph } from "../lib/graphApi";
import { EDGE_STYLE, NODE_COLORS, NODE_LEGEND, SEED_EXAMPLES, SEED_TYPES } from "./graphConfig";
import type { GraphSeed } from "./GraphView";

interface Props {
  seedType: NodeType;
  seedId: string;
  setSeedType: (t: NodeType) => void;
  setSeedId: (id: string) => void;
  navigate: (s: GraphSeed) => void;
  loading: boolean;
  legend: ClassificationInfo[];
  stubs: Subgraph["stubs"] | undefined;
  expand: (type: NodeType, id: string) => void;
  error: string | null;
}

export function GraphRail({
  seedType, seedId, setSeedType, setSeedId, navigate, loading,
  legend, stubs, expand, error,
}: Props) {
  return (
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

      <p className="section-label">Node type</p>
      <ul className="graph-legend node-legend" aria-label="Node type legend">
        {NODE_LEGEND.map((n) => (
          <li key={n.type}>
            <span
              className="node-dot"
              style={{ background: NODE_COLORS[n.type] ?? "#888" }}
              aria-hidden
            />
            {n.label}
          </li>
        ))}
      </ul>

      <p className="section-label">Edge classification</p>
      <ul className="graph-legend" aria-label="Edge classification legend">
        {legend.map((c) => {
          const s = EDGE_STYLE[c.classification] ?? EDGE_STYLE.FACT;
          return (
            <li key={c.classification}>
              <span
                className="legend-swatch"
                style={{ borderTop: `${Math.max(2, s.width)}px ${s.style} ${s.color}` }}
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
  );
}
