/**
 * MO Profiles — narrative beside the structured extraction (MO-002/#38).
 *
 * The point of this view is that nothing is asserted without showing where it
 * came from: hovering an extracted attribute highlights the exact span of the
 * FIR narrative that produced it. UNKNOWN is displayed as a first-class value,
 * because "no evidence in the text" is a real answer (ADR-006), not a gap to
 * paper over.
 */
import { useEffect, useState } from "react";
import {
  fetchMoCase,
  fetchMoProfiles,
  fetchMoRun,
  MO_FIELDS,
  type MoCase,
  type MoListRow,
  type MoRun,
} from "../lib/moApi";

const UNKNOWN = "UNKNOWN";

function confidenceClass(v: number): string {
  if (v >= 0.85) return "hi";
  if (v >= 0.7) return "mid";
  return "lo";
}

/** Narrative with the active attribute's source span highlighted. */
function Narrative({ text, span }: { text: string; span: [number, number] | null }) {
  if (!span || span[0] >= span[1] || span[1] > text.length) {
    return <p className="mo-narrative">{text}</p>;
  }
  return (
    <p className="mo-narrative">
      {text.slice(0, span[0])}
      <mark className="mo-span">{text.slice(span[0], span[1])}</mark>
      {text.slice(span[1])}
    </p>
  );
}

export function MoView() {
  const [run, setRun] = useState<MoRun | null>(null);
  const [rows, setRows] = useState<MoListRow[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<MoCase | null>(null);
  const [span, setSpan] = useState<[number, number] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMoRun().then(setRun).catch((e) => setError(String(e)));
    fetchMoProfiles(60)
      .then((r) => {
        setRows(r.profiles);
        if (r.profiles.length) setSelected(r.profiles[0].case_master_id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (selected == null) return;
    setSpan(null);
    fetchMoCase(selected).then(setDetail).catch((e) => setError(String(e)));
  }, [selected]);

  if (error) {
    return (
      <div className="mo-body">
        <div className="empty">Backend unreachable — {error}</div>
      </div>
    );
  }

  return (
    <div className="mo-body">
      {/* extracted cases */}
      <aside className="mo-rail">
        <div className="brand">
          <h1>MO Profiles</h1>
          <p>UNDERSTAND · structured modus operandi from FIR narratives</p>
        </div>

        {run && (
          <div className="mo-run">
            <p className="section-label">Extraction run</p>
            <dl className="metric-grid">
              <dt>Extractor</dt>
              <dd>{run.extractor}</dd>
              <dt>Profiles</dt>
              <dd>
                {run.processed} extracted · {run.failed} failed · {run.skipped} skipped
              </dd>
              <dt>Method</dt>
              <dd>
                <code>{run.model_version}</code>
              </dd>
            </dl>
            {run.zia_unavailable_reason && (
              <p className="muted small" title={run.zia_unavailable_reason}>
                Extracted on the deterministic path — every value is still anchored to
                the narrative and validated against the MO schema.
              </p>
            )}
          </div>
        )}

        <p className="section-label">Cases ({rows.length})</p>
        <ul className="mo-cases" aria-label="Cases with extracted MO">
          {rows.map((r) => (
            <li key={r.case_master_id}>
              <button
                className={"mo-case" + (selected === r.case_master_id ? " active" : "")}
                onClick={() => setSelected(r.case_master_id)}
              >
                <span className="mo-case-id">FIR {r.case_master_id}</span>
                <span className="mo-case-tags">
                  {String(r.crime_action.value)} · {String(r.target_type.value)}
                </span>
              </button>
            </li>
          ))}
          {rows.length === 0 && <li className="muted">loading…</li>}
        </ul>
      </aside>

      {/* narrative + extraction */}
      <section className="mo-main" aria-label="Narrative and extracted MO">
        {detail ? (
          <>
            <div className="mo-panel">
              <header className="mo-panel-head">
                <strong>FIR {detail.case_master_id} — narrative</strong>
                <span className="badge">{detail.intelligence.classification_label}</span>
              </header>
              <Narrative text={detail.narrative} span={span} />
              <p className="muted small">
                Hover an attribute to highlight the words it was extracted from.
              </p>
            </div>

            <div className="mo-panel">
              <header className="mo-panel-head">
                <strong>Extracted MO</strong>
                <code className="muted small">{detail.profile.extractor}</code>
              </header>
              <ul className="mo-attrs">
                {MO_FIELDS.map(({ key, label }) => {
                  const attr = detail.profile[key] as {
                    value: string | number;
                    confidence: number;
                    source_span?: [number, number] | null;
                  };
                  const isUnknown = attr.value === UNKNOWN;
                  return (
                    <li
                      key={key}
                      className={"mo-attr" + (isUnknown ? " unknown" : "")}
                      onMouseEnter={() => setSpan(attr.source_span ?? null)}
                      onMouseLeave={() => setSpan(null)}
                      onFocus={() => setSpan(attr.source_span ?? null)}
                      onBlur={() => setSpan(null)}
                      tabIndex={0}
                    >
                      <span className="mo-attr-label">{label}</span>
                      <span className="mo-attr-value">{String(attr.value)}</span>
                      <span className={"mo-conf " + confidenceClass(attr.confidence)}>
                        {(attr.confidence * 100).toFixed(0)}%
                      </span>
                    </li>
                  );
                })}
              </ul>
              <p className="muted small">
                UNKNOWN means the narrative contains no evidence for that attribute — it
                is never guessed.
              </p>
              {detail.intelligence.limitations?.map((l) => (
                <p key={l} className="muted small">
                  {l}
                </p>
              ))}
            </div>
          </>
        ) : (
          <p className="muted" style={{ padding: "2rem" }}>
            select a case to see its narrative and extracted MO
          </p>
        )}
      </section>
    </div>
  );
}
