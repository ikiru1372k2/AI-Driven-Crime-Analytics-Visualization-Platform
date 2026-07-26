/** Left rail for the association graph: seed form (case id, or district /
 *  police-station pickers), the node-type legend, and "not shown" stubs.
 *  Extracted from GraphView so that component stays under the source-size gate. */
import { useMemo, useState } from "react";
import type { Meta } from "../lib/api";
import type { NodeType, Subgraph } from "../lib/graphApi";
import { NODE_COLORS, NODE_LEGEND, SEED_EXAMPLES, SEED_TYPES, SEED_TYPE_LABELS } from "./graphConfig";
import type { GraphSeed } from "./GraphView";

interface Props {
  seedType: NodeType;
  seedId: string;
  setSeedType: (t: NodeType) => void;
  setSeedId: (id: string) => void;
  navigate: (s: GraphSeed) => void;
  loading: boolean;
  /** District/station lookups for the seed pickers (null until loaded). */
  meta: Meta | null;
  stubs: Subgraph["stubs"] | undefined;
  expand: (type: NodeType, id: string) => void;
  error: string | null;
}

export function GraphRail({
  seedType, seedId, setSeedType, setSeedId, navigate, loading,
  meta, stubs, expand, error,
}: Props) {
  // The district chosen in the police-station flow, used to list its stations.
  const [psDistrict, setPsDistrict] = useState("");
  const stationsForDistrict = useMemo(
    () => (meta?.stations ?? []).filter((s) => String(s.district_id) === String(psDistrict)),
    [meta, psDistrict],
  );

  // Switching seed type resets the id: a case keeps its example id (free text),
  // a district/station starts empty so its picker shows the placeholder.
  const onTypeChange = (t: NodeType) => {
    setSeedType(t);
    setPsDistrict("");
    setSeedId(t === "CASE" ? SEED_EXAMPLES[t] ?? "" : "");
  };

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
          // Only the case flow submits; the pickers navigate on change.
          if (seedType === "CASE" && seedId.trim()) navigate({ type: "CASE", id: seedId.trim() });
        }}
      >
        <select
          value={seedType}
          aria-label="Seed node type"
          onChange={(e) => onTypeChange(e.target.value as NodeType)}
        >
          {SEED_TYPES.map((t) => (
            <option key={t} value={t}>
              {SEED_TYPE_LABELS[t] ?? t}
            </option>
          ))}
        </select>

        {seedType === "CASE" && (
          <>
            <input
              value={seedId}
              aria-label="Seed case id"
              placeholder={`case id, e.g. ${SEED_EXAMPLES.CASE ?? "7231"}`}
              onChange={(e) => setSeedId(e.target.value)}
            />
            <button type="submit" disabled={loading}>
              Load
            </button>
          </>
        )}

        {seedType === "DISTRICT" && (
          <select
            value={seedId}
            aria-label="Select district"
            disabled={loading || !meta}
            onChange={(e) => {
              const id = e.target.value;
              setSeedId(id);
              if (id) navigate({ type: "DISTRICT", id });
            }}
          >
            <option value="">Select district…</option>
            {meta?.districts.map((d) => (
              <option key={d.district_id} value={d.district_id}>
                {d.district_name}
              </option>
            ))}
          </select>
        )}

        {seedType === "POLICE_STATION" && (
          <>
            <select
              value={psDistrict}
              aria-label="Select district"
              disabled={loading || !meta}
              onChange={(e) => {
                setPsDistrict(e.target.value);
                setSeedId(""); // station list changes → clear the old station
              }}
            >
              <option value="">Select district…</option>
              {meta?.districts.map((d) => (
                <option key={d.district_id} value={d.district_id}>
                  {d.district_name}
                </option>
              ))}
            </select>
            <select
              value={seedId}
              aria-label="Select police station"
              disabled={loading || !psDistrict}
              onChange={(e) => {
                const id = e.target.value;
                setSeedId(id);
                if (id) navigate({ type: "POLICE_STATION", id });
              }}
            >
              <option value="">
                {psDistrict ? "Select police station…" : "Select a district first"}
              </option>
              {stationsForDistrict.map((s) => (
                <option key={s.station_id} value={s.station_id}>
                  {s.station_name}
                </option>
              ))}
            </select>
          </>
        )}
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
    </div>
  );
}
