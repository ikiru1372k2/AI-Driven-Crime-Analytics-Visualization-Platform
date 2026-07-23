/** The node / edge detail card for the association graph. Extracted from
 *  GraphView so that component stays under the source-size gate. Provenance-
 *  first: every edge shows its evidence FIR; every metric its method/run. */
import type { CaseBasic, CasePerson, GraphEdge, NodeDetail, NodeType } from "../lib/graphApi";
import { NODE_COLORS } from "./graphConfig";

interface Props {
  detail: NodeDetail | null;
  edgeDetail: GraphEdge | null;
  /** Basic detail for a clicked case node — everything we know about the FIR,
   *  served instantly from the warm cache (no graph metrics — PERF-001). */
  caseBasic: CaseBasic | null;
  /** Whether "Navigate here" is offered. For people it's only meaningful when
   *  the person has an identity match under a different name (else there's
   *  nothing new to explore); places/charges/cases can always be navigated. */
  canNavigate: boolean;
  onClose: () => void;
  onNavigate: (type: NodeType, id: string) => void;
  onNavigateCase: (caseId: string) => void;
}

/** "Name, 34" — a person as we know them on the FIR (age omitted if unknown). */
function personLabel(p: CasePerson): string {
  const name = p.name ?? "Unknown";
  return p.age != null ? `${name}, ${p.age}` : name;
}

export function GraphDetailPanel({
  detail,
  edgeDetail,
  caseBasic,
  canNavigate,
  onClose,
  onNavigate,
  onNavigateCase,
}: Props) {
  if (caseBasic) {
    const c = caseBasic;
    const crime = c.subhead_name ?? c.head_name ?? "—";
    return (
      <aside className="graph-panel" aria-label="Case detail">
        <header>
          <span className="node-dot" style={{ background: NODE_COLORS.CASE }} aria-hidden />
          <strong>FIR {c.CrimeNo ?? c.CaseMasterID}</strong>
          <button className="close" aria-label="Close detail" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="badge">Case record</p>
        <dl className="metric-grid">
          <dt>Crime</dt>
          <dd>{crime}</dd>
          <dt>District</dt>
          <dd>{c.district_name ?? "—"}</dd>
          <dt>Station</dt>
          <dd>{c.station_name ?? "—"}</dd>
          <dt>Registered</dt>
          <dd>{c.registered_date ?? "—"}</dd>
          <dt>Status</dt>
          <dd>{c.status ?? "—"}</dd>
        </dl>
        <p className="section-label">Accused ({c.accused.length})</p>
        {c.accused.length ? (
          <ul className="case-list">
            {c.accused.map((p, i) => (
              <li key={i}>{personLabel(p)}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">None recorded.</p>
        )}
        {c.victims.length > 0 && (
          <>
            <p className="section-label">Victims ({c.victims.length})</p>
            <ul className="case-list">
              {c.victims.map((p, i) => (
                <li key={i}>{personLabel(p)}</li>
              ))}
            </ul>
          </>
        )}
        {c.narrative && (
          <>
            <p className="section-label">Narrative</p>
            <p className="interpretation">{c.narrative}</p>
          </>
        )}
        <button className="nav-btn" onClick={() => onNavigateCase(c.CaseMasterID)}>
          Explore this case →
        </button>
        <p className="muted small">What we know from the FIR — no inference.</p>
      </aside>
    );
  }

  if (detail) {
    return (
      <aside className="graph-panel" aria-label="Node detail">
        <header>
          <span
            className="node-dot"
            style={{ background: NODE_COLORS[detail.node.node_type] ?? "#888" }}
            aria-hidden
          />
          <strong>{detail.node.label}</strong>
          <button className="close" aria-label="Close detail" onClick={onClose}>
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
              <button className="linklike" onClick={() => onNavigateCase(String(c))}>
                Case {c}
              </button>
            </li>
          ))}
          {detail.linked_cases.length > 12 && (
            <li className="muted">and {detail.linked_cases.length - 12} more</li>
          )}
        </ul>
        {canNavigate && (
          <button
            className="nav-btn"
            onClick={() => onNavigate(detail.node.node_type, detail.node.entity_ref_id)}
          >
            Navigate here →
          </button>
        )}
        {detail.intelligence.limitations?.map((l) => (
          <p key={l} className="muted small">
            {l}
          </p>
        ))}
      </aside>
    );
  }

  if (edgeDetail) {
    return (
      <aside className="graph-panel" aria-label="Edge evidence">
        <header>
          <strong>{edgeDetail.relationship_type}</strong>
          <button className="close" aria-label="Close evidence" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="badge">{edgeDetail.classification}</p>
        <dl className="metric-grid">
          <dt>Evidence FIR</dt>
          <dd>
            <button
              className="linklike"
              onClick={() => onNavigateCase(String(edgeDetail.evidence_case_id))}
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
    );
  }

  return null;
}
