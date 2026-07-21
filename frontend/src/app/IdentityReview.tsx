/**
 * Cross-FIR Identity Resolution review (#65). A candidate queue of possible
 * same-person identities discovered across FIRs, each with its member records
 * and the explainable signal breakdown (contributing + contradictory). The
 * analyst accepts or rejects — nothing is auto-merged (human-in-the-loop).
 */
import { useEffect, useMemo, useState } from "react";
import {
  fetchIdentities,
  fetchIdentityDetail,
  type IdentitiesResponse,
  type IdentityCandidate,
} from "../lib/api";
import { fetchDecisions, postDecision } from "../lib/evidenceApi";

type Decision = "accepted" | "rejected";

export function IdentityReview() {
  const [data, setData] = useState<IdentitiesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  // Per-candidate evidence is fetched on expand: shipping it for all 512
  // candidates was 88% of a 1.1 MB response and made the queue slow to load.
  const [details, setDetails] = useState<Record<string, IdentityCandidate>>({});

  useEffect(() => {
    fetchIdentities().then(setData).catch((e) => setError(String(e)));
    // loop closure (design review P0): accept/reject survives reload,
    // each action lands in the append-only audit trail (PROV-003)
    fetchDecisions()
      .then((d) => {
        const restored: Record<string, Decision> = {};
        for (const x of d.decisions) {
          if (x.kind !== "IDENTITY") continue;
          if (x.decision === "CONFIRMED") restored[x.target_ref] = "accepted";
          if (x.decision === "REJECTED") restored[x.target_ref] = "rejected";
        }
        setDecisions((prev) => ({ ...restored, ...prev }));
      })
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    const list = q
      ? data.candidates.filter((c) => c.name_variants.some((n) => n.toLowerCase().includes(q)))
      : data.candidates;
    return list.slice(0, 60);
  }, [data, query]);

  if (error) return <div className="idr"><div className="empty">Backend unreachable — {error}</div></div>;
  if (!data) return <div className="idr"><div className="empty">Resolving identities…</div></div>;

  const decide = (id: string, d: Decision) => {
    const cleared = decisions[id] === d;
    setDecisions((prev) => ({ ...prev, [id]: cleared ? undefined! : d }));
    postDecision({
      kind: "IDENTITY",
      target_ref: id,
      decision: cleared ? "NEEDS_MORE_EVIDENCE" : d === "accepted" ? "CONFIRMED" : "REJECTED",
    }).catch(() => {});
  };
  const tally = Object.values(decisions).filter(Boolean);

  return (
    <div className="idr">
      <div className="idr-head">
        <div>
          <h2>Cross-FIR Identity Resolution</h2>
          <p className="sub">
            {data.candidate_count.toLocaleString()} candidate identities from{" "}
            {data.accused_total.toLocaleString()} accused records · human-in-the-loop, nothing
            auto-merged
          </p>
        </div>
        <input
          className="idr-search"
          placeholder="Search a name (e.g. Ravi)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search identity by name"
        />
      </div>

      <div className="idr-tally">
        <span className="chip-stat accept">{tally.filter((d) => d === "accepted").length} accepted</span>
        <span className="chip-stat reject">{tally.filter((d) => d === "rejected").length} rejected</span>
        <span className="chip-stat">
          {filtered.length} shown{query ? " (filtered)" : ` of ${data.candidate_count}`}
        </span>
      </div>

      <div className="idr-list">
        {filtered.map((c) => (
          <IdentityCard
            key={c.cluster_id}
            c={c}
            open={expanded === c.cluster_id}
            detail={details[c.cluster_id]}
            decision={decisions[c.cluster_id]}
            onToggle={() => {
              const next = expanded === c.cluster_id ? null : c.cluster_id;
              setExpanded(next);
              if (next && !details[next]) {
                fetchIdentityDetail(next)
                  .then((d) => setDetails((prev) => ({ ...prev, [next]: d })))
                  .catch(() => {});
              }
            }}
            onDecide={(d) => decide(c.cluster_id, d)}
          />
        ))}
        {filtered.length === 0 && <div className="empty">No identities match “{query}”.</div>}
      </div>
    </div>
  );
}

function IdentityCard({
  c,
  open,
  detail,
  decision,
  onToggle,
  onDecide,
}: {
  c: IdentityCandidate;
  open: boolean;
  /** evidence fetched on expand; undefined until it arrives */
  detail?: IdentityCandidate;
  decision?: Decision;
  onToggle: () => void;
  onDecide: (d: Decision) => void;
}) {
  const crossDistrict = c.districts.length > 1;
  const members = detail?.members;
  const signals = detail?.signals;
  return (
    <article className={"id-card" + (decision ? ` ${decision}` : "")}>
      <button className="id-summary" onClick={onToggle} aria-expanded={open}>
        <span className="id-names">{c.name_variants.join(" · ")}</span>
        <span className="id-facts">
          <span className="conf">{(c.confidence * 100).toFixed(0)}%</span>
          <span>{c.size} records</span>
          <span>{c.gender ?? "?"}</span>
          {c.age_range && <span>age {c.age_range[0]}–{c.age_range[1]}</span>}
          {crossDistrict && <span className="cross">▲ {c.districts.length} districts</span>}
        </span>
      </button>

      {open && (
        <div className="id-detail">
          <div className="id-districts">
            {c.districts.map((d) => (
              <span key={d} className="dchip">{d}</span>
            ))}
          </div>

          <div className="section-label">Records</div>
          {!members && <div className="muted small">loading evidence…</div>}
          <div className="id-members">
            {(members ?? []).map((m) => (
              <div className="id-member" key={m.accused_id}>
                <span className="mn">{m.name}</span>
                <span className="ma">{m.age ?? "?"}</span>
                <span className="md">{m.district_name ?? "—"}</span>
                <span className="mc">FIR case {m.case_id}</span>
              </div>
            ))}
          </div>

          <div className="section-label">Match signals</div>
          <div className="id-signals">
            {(signals ?? []).slice(0, 8).map((s, i) => (
              <div className="sig" key={i}>
                <span className="sig-score">{(s.score * 100).toFixed(0)}%</span>
                <span className="sig-body">
                  {s.contributing.map((t, j) => (
                    <span className="tag ok" key={j}>{t}</span>
                  ))}
                  {s.contradictory.map((t, j) => (
                    <span className="tag bad" key={j}>{t}</span>
                  ))}
                </span>
              </div>
            ))}
          </div>

          <div className="id-actions">
            <button className={"act accept" + (decision === "accepted" ? " on" : "")} onClick={() => onDecide("accepted")}>
              {decision === "accepted" ? "✓ Same person" : "Confirm same person"}
            </button>
            <button className={"act reject" + (decision === "rejected" ? " on" : "")} onClick={() => onDecide("rejected")}>
              {decision === "rejected" ? "✗ Not a match" : "Reject"}
            </button>
            <span className="status-note">status: {decision ?? c.status.replace("_", " ")}</span>
          </div>
        </div>
      )}
    </article>
  );
}
