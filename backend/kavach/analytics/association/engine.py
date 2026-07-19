"""Investigative association search (EPIC-ASSOC).

Given a seed case, surface *related* cases across the dataset so an analyst can
find "anything relatable". Associations come from several channels, each with a
strength weight and its own evidence:

  same_suspect  - an accused resolves to the SAME PERSON as one of the seed's
                  accused (entity resolution, #46-50). Strongest signal; drawn
                  as a POTENTIAL_ASSOCIATION (candidate for human review).
  same_station  - filed at the same police station.
  same_subhead  - the same crime sub-head (e.g. Robbery).
  same_district - occurred in the same district (weak on its own).

The graph is entity-mediated: associated cases hang off the shared entity node
(station / district / crime) so the link is visible and explainable, and
same-suspect accused pairs are joined directly.

Two orthogonal controls (design):
  * View   = which node types the client renders (projection; done client-side).
  * Filter = which records QUALIFY (predicates applied HERE, server-side), so
             filtering narrows the association universe regardless of the View.

Edge shape mirrors the crime-graph API so the same renderer can draw it.
All data is SYNTHETIC (ADR-011); nothing reads the planted answer key.
"""

from __future__ import annotations

import functools

import pandas as pd

from kavach.analytics.entity import resolve_identities
from kavach.api import data

#: association channel -> (relationship_type, classification, strength weight)
_CHANNELS = {
    "same_suspect": ("SAME_IDENTITY", "POTENTIAL_ASSOCIATION", 1.0),
    "same_station": ("REGISTERED_AT", "FACT", 0.4),
    "same_subhead": ("CLASSIFIED_AS", "FACT", 0.35),
    "same_district": ("OCCURRED_IN", "FACT", 0.2),
}


def _nid(node_type: str, ref: object) -> str:
    return f"{node_type}:{ref}"


class _G:
    """Accumulates unique nodes/edges keyed by id."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}

    def node(self, node_type: str, ref: object, label: str) -> str:
        nid = _nid(node_type, ref)
        self.nodes.setdefault(
            nid, {"node_id": nid, "node_type": node_type, "entity_ref_id": str(ref), "label": label}
        )
        return nid

    def edge(self, rel: str, cls: str, src: str, dst: str, weight: float, evidence: object) -> None:
        eid = f"{rel}|{src}|{dst}"
        self.edges.setdefault(
            eid,
            {
                "edge_id": eid, "source": src, "target": dst,
                "relationship_type": rel, "classification": cls,
                "weight": round(weight, 3), "evidence_case_id": int(evidence),
                "derivation": "OBSERVED_FK" if cls == "FACT" else "CASE_CO_OCCURRENCE",
            },
        )


@functools.lru_cache(maxsize=1)
def _same_suspect_index() -> dict[str, list[dict]]:
    """accused_id -> the identity cluster's members (same-person candidates).

    Cached for the process lifetime — entity resolution is the expensive step
    and the dataset is static per run. Tests that swap KAVACH_DATA_DIR call
    ``_same_suspect_index.cache_clear()``.
    """
    idx: dict[str, list[dict]] = {}
    for cluster in resolve_identities()["candidates"]:
        for m in cluster["members"]:
            idx[m["accused_id"]] = cluster["members"]
    return idx


def _passes_filters(cid: str, row, acc_by_case, vic_by_case, f: dict) -> bool:
    """Orthogonal attribute filters — a case qualifies only if it matches ALL given."""
    if f.get("subhead_id") and row.subhead_id != str(f["subhead_id"]):
        return False
    if f.get("district_id") and row.district_id != str(f["district_id"]):
        return False
    if f.get("station_id") and row.station_id != str(f["station_id"]):
        return False
    rdate = row.registered_date
    if f.get("date_from") and (pd.isna(rdate) or rdate < pd.to_datetime(f["date_from"])):
        return False
    if f.get("date_to") and (pd.isna(rdate) or rdate > pd.to_datetime(f["date_to"])):
        return False
    people = acc_by_case.get(cid, []) + vic_by_case.get(cid, [])
    if f.get("name_exact"):
        q = f["name_exact"].strip().lower()
        if not any(q == (p["name"] or "").strip().lower() for p in people):
            return False
    if f.get("name_contains"):
        q = f["name_contains"].lower()
        if not any(q in (p["name"] or "").lower() for p in people):
            return False
    if f.get("gender"):
        if not any(p["gender"] == f["gender"] for p in acc_by_case.get(cid, [])):
            return False
    if f.get("age_min") is not None or f.get("age_max") is not None:
        lo = f.get("age_min") if f.get("age_min") is not None else 0
        hi = f.get("age_max") if f.get("age_max") is not None else 200
        if not any(a["age"] is not None and lo <= a["age"] <= hi for a in acc_by_case.get(cid, [])):
            return False
    return True


def find_associations(
    case_id: int | str, *, focus: str | None = None, limit: int = 40, **filters
) -> dict:
    """Association graph for a seed case, revealed progressively.

    focus=None  -> the OVERVIEW: the seed case + its own entities (station,
                   district, sub-head, accused, victims). Each entity carries an
                   ``expandable`` count of related cases reachable through it.
    focus="TYPE:id" -> EXPAND that entity: the related cases reached through it
                   (same station/district/sub-head), or, for an accused, the
                   SAME-PERSON cases (entity resolution). Meant to be merged into
                   the current graph client-side.

    Filters are orthogonal and applied throughout.
    """
    df = data.enriched_cases()
    cid0 = str(case_id)
    seed = df[df["CaseMasterID"] == cid0]
    active = {k: v for k, v in filters.items() if v not in (None, "")}
    params = {"case_id": cid0, "focus": focus, "limit": limit, "filters": active}
    if seed.empty:
        return {"synthetic": True, "params": params, "seed": None,
                "association_count": 0, "expandable": {}, "nodes": [], "edges": []}
    s = seed.iloc[0]

    acc_by_case: dict[str, list[dict]] = {}
    vic_by_case: dict[str, list[dict]] = {}
    for a in data.accused_records():
        acc_by_case.setdefault(a["case_id"], []).append(a)
    for v in data.victim_records():
        vic_by_case.setdefault(v["case_id"], []).append(v)
    seed_accused = acc_by_case.get(cid0, [])
    ident_idx = _same_suspect_index()
    rows_by_cid = {r.CaseMasterID: r for r in df.itertuples(index=False)}

    def qualifies(cid: str) -> bool:
        row = rows_by_cid.get(cid)
        return row is not None and _passes_filters(cid, row, acc_by_case, vic_by_case, filters)

    # candidate related cases per channel (filtered), excluding the seed
    station_cases, district_cases, subhead_cases = [], [], []
    for row in df.itertuples(index=False):
        cid = row.CaseMasterID
        if cid == cid0 or not qualifies(cid):
            continue
        if row.station_id == s["station_id"]:
            station_cases.append(cid)
        if row.district_id == s["district_id"]:
            district_cases.append(cid)
        if row.subhead_id == s["subhead_id"]:
            subhead_cases.append(cid)
    # same-suspect: seed accused id -> {other case_id: other member}
    suspect_by_acc: dict[str, dict[str, dict]] = {}
    for sa in seed_accused:
        for m in ident_idx.get(sa["accused_id"], []):
            if m["case_id"] != cid0 and qualifies(m["case_id"]):
                suspect_by_acc.setdefault(sa["accused_id"], {})[m["case_id"]] = m

    # ---- seed + its own entities (the overview base, always present) ----
    g = _G()
    seed_case = g.node("CASE", case_id, f"Case {case_id}")
    st = g.node("POLICE_STATION", s["station_id"], s["station_name"] or "Station")
    di = g.node("DISTRICT", s["district_id"], s["district_name"] or "District")
    sh = g.node("CRIME_SUBHEAD", s["subhead_id"], s["subhead_name"] or "Sub-head")
    g.edge("REGISTERED_AT", "FACT", seed_case, st, 1.0, case_id)
    g.edge("OCCURRED_IN", "FACT", seed_case, di, 1.0, case_id)
    g.edge("CLASSIFIED_AS", "FACT", seed_case, sh, 1.0, case_id)
    for a in seed_accused:
        g.node("ACCUSED_RECORD", a["accused_id"], a["name"])
        g.edge("ACCUSED_IN", "FACT", f"ACCUSED_RECORD:{a['accused_id']}", seed_case, 1.0, case_id)
    for v in vic_by_case.get(cid0, []):
        g.node("VICTIM_RECORD", v["victim_id"], v["name"])
        g.edge("VICTIM_IN", "FACT", f"VICTIM_RECORD:{v['victim_id']}", seed_case, 1.0, case_id)

    # how many related cases each entity would reveal (a hint on the overview)
    expandable = {
        st: len(set(station_cases)),
        di: len(set(district_cases)),
        sh: len(set(subhead_cases)),
    }
    for sa in seed_accused:
        aid = sa["accused_id"]
        expandable[f"ACCUSED_RECORD:{aid}"] = len(suspect_by_acc.get(aid, {}))

    # ---- expand one entity into its related cases ----
    assoc_count = 0
    channel = None
    if focus:
        ftype, fid = focus.split(":", 1)
        if ftype == "ACCUSED_RECORD":
            channel = "same_suspect"
            _, cls, w = _CHANNELS[channel]
            members = suspect_by_acc.get(fid, {})
            for cid in list(members)[:limit]:
                m = members[cid]
                cn = g.node("CASE", cid, f"Case {cid}")
                g.node("ACCUSED_RECORD", m["accused_id"], m["name"])
                g.edge("ACCUSED_IN", "FACT", f"ACCUSED_RECORD:{m['accused_id']}", cn, 1.0, cid)
                g.edge("SAME_IDENTITY", cls, focus, f"ACCUSED_RECORD:{m['accused_id']}", w, cid)
            assoc_count = min(len(members), limit)
        else:
            channel = {"POLICE_STATION": "same_station", "DISTRICT": "same_district",
                       "CRIME_SUBHEAD": "same_subhead"}.get(ftype)
            pool = {"POLICE_STATION": station_cases, "DISTRICT": district_cases,
                    "CRIME_SUBHEAD": subhead_cases}.get(ftype, [])
            if channel:
                rel, cls, w = _CHANNELS[channel]
                for cid in list(dict.fromkeys(pool))[:limit]:
                    cn = g.node("CASE", cid, f"Case {cid}")
                    g.edge(rel, cls, cn, focus, w, cid)
                assoc_count = min(len(set(pool)), limit)

    return {
        "synthetic": True,
        "params": params,
        "seed": {"case_id": cid0, "subhead": s["subhead_name"],
                 "station": s["station_name"], "district": s["district_name"]},
        "focus": focus,
        "channel": channel,
        "association_count": assoc_count,
        "total_related": len(set(station_cases) | set(district_cases) | set(subhead_cases)
                             | {c for m in suspect_by_acc.values() for c in m}),
        "expandable": expandable,
        "nodes": list(g.nodes.values()),
        "edges": list(g.edges.values()),
    }
