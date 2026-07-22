/**
 * Association graph controls — two Google-Maps-style icon buttons at the top
 * right that open popovers:
 *   View   = which dimensions to DRAW (multi-select projection; instant).
 *   Filter = which records QUALIFY (attribute predicates; re-queries the
 *            association universe). View and Filter are orthogonal.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchMeta, type Meta } from "../lib/api";
import type { AssocFilters, NodeType } from "../lib/graphApi";
import { VIEW_DIMS } from "./graphConfig";

interface Props {
  /** View is the overview projection — only shown before you drill into an entity. */
  showView: boolean;
  /** Filter narrows an expansion's cases — only shown after you drill in. */
  showFilter: boolean;
  viewDims: Set<string>;
  onToggleDim: (key: string) => void;
  filters: AssocFilters;
  onApplyFilters: (f: AssocFilters) => void;
  resultCount: number | null;
  /** The entity type currently expanded. All results already share its own
   *  attribute, so filtering on that attribute is redundant and its field is
   *  hidden (e.g. no District dropdown while expanding a district). */
  expandedType?: NodeType | null;
}

export function GraphControls({
  showView, showFilter, viewDims, onToggleDim, filters, onApplyFilters, resultCount,
  expandedType,
}: Props) {
  const [open, setOpen] = useState<"view" | "filter" | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [draft, setDraft] = useState<AssocFilters>(filters);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchMeta().then(setMeta).catch(() => {});
  }, []);
  // close the open popover when clicking anywhere outside the control
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);
  useEffect(() => {
    setDraft(filters);
  }, [filters]);
  // if a control is hidden (level changed), don't leave its popover open
  useEffect(() => {
    if (!showView) setOpen((o) => (o === "view" ? null : o));
  }, [showView]);
  useEffect(() => {
    if (!showFilter) setOpen((o) => (o === "filter" ? null : o));
  }, [showFilter]);

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((v) => v !== undefined && v !== null && v !== "").length,
    [filters],
  );

  const set = (k: keyof AssocFilters, v: string) =>
    setDraft((d) => ({ ...d, [k]: v === "" ? undefined : v }));
  const setNum = (k: keyof AssocFilters, v: string) =>
    setDraft((d) => ({ ...d, [k]: v === "" ? undefined : Number(v) }));

  return (
    <div className="gc" ref={rootRef}>
      <div className="gc-icons">
        {showView && (
          <button
            className={"gc-icon" + (open === "view" ? " open" : "")}
            onClick={() => setOpen(open === "view" ? null : "view")}
            title="View — choose which dimensions to show (overview only)"
          >
            &#9635; View
          </button>
        )}
        {showFilter && (
          <button
            className={"gc-icon" + (open === "filter" ? " open" : "") + (activeFilterCount ? " has" : "")}
            onClick={() => setOpen(open === "filter" ? null : "filter")}
            title="Filter — narrow the cases in this expansion"
          >
            &#9776; Filter{activeFilterCount ? ` (${activeFilterCount})` : ""}
          </button>
        )}
      </div>

      {open === "view" && (
        <div className="gc-pop">
          <p className="gc-title">Show dimensions</p>
          {VIEW_DIMS.map((d) => (
            <label key={d.key} className="gc-check">
              <input
                type="checkbox"
                checked={viewDims.has(d.key)}
                onChange={() => onToggleDim(d.key)}
              />
              {d.label}
            </label>
          ))}
          <p className="gc-note">Cases are always shown. View only changes what's drawn.</p>
        </div>
      )}

      {open === "filter" && (
        <div className="gc-pop wide">
          <p className="gc-title">Filter associations {resultCount != null && <span className="gc-count">· {resultCount} found</span>}</p>

          {/* the crime is already fixed when a crime-type node is expanded */}
          {expandedType !== "CRIME_SUBHEAD" && expandedType !== "CRIME_HEAD" && (
            <label className="gc-field">Crime type
              <select value={draft.subhead_id ?? ""} onChange={(e) => set("subhead_id", e.target.value)}>
                <option value="">any</option>
                {meta?.crime_subheads.map((s) => (
                  <option key={s.subhead_id} value={s.subhead_id}>{s.subhead_name}</option>
                ))}
              </select>
            </label>
          )}

          {/* the district is already fixed when a district node is expanded */}
          {expandedType !== "DISTRICT" && (
            <label className="gc-field">District
              <select value={draft.district_id ?? ""} onChange={(e) => set("district_id", e.target.value)}>
                <option value="">any</option>
                {meta?.districts.map((d) => (
                  <option key={d.district_id} value={d.district_id}>{d.district_name}</option>
                ))}
              </select>
            </label>
          )}

          <label className="gc-field">Name (contains)
            <input value={draft.name_contains ?? ""} placeholder="e.g. Ravi"
              onChange={(e) => set("name_contains", e.target.value)} />
          </label>
          <label className="gc-field">Name (exact)
            <input value={draft.name_exact ?? ""} placeholder="e.g. Suresh Babu"
              onChange={(e) => set("name_exact", e.target.value)} />
          </label>

          <div className="gc-row">
            <label className="gc-field">Age min
              <input type="number" min={0} max={120} value={draft.age_min ?? ""}
                onChange={(e) => setNum("age_min", e.target.value)} />
            </label>
            <label className="gc-field">Age max
              <input type="number" min={0} max={120} value={draft.age_max ?? ""}
                onChange={(e) => setNum("age_max", e.target.value)} />
            </label>
            <label className="gc-field">Gender
              <select value={draft.gender ?? ""} onChange={(e) => set("gender", e.target.value)}>
                <option value="">any</option>
                <option value="M">M</option>
                <option value="F">F</option>
              </select>
            </label>
          </div>

          <div className="gc-row">
            <label className="gc-field">From
              <input type="date" value={draft.date_from ?? ""} onChange={(e) => set("date_from", e.target.value)} />
            </label>
            <label className="gc-field">To
              <input type="date" value={draft.date_to ?? ""} onChange={(e) => set("date_to", e.target.value)} />
            </label>
          </div>

          <div className="gc-actions">
            <button className="gc-clear" onClick={() => { setDraft({}); onApplyFilters({}); }}>Clear</button>
            <button className="gc-apply" onClick={() => { onApplyFilters(draft); setOpen(null); }}>Apply</button>
          </div>
        </div>
      )}
    </div>
  );
}
