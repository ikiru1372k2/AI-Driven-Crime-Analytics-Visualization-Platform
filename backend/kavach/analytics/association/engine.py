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

#: How far an "age band" reaches around the seed suspect's age for the default
#: similar-profile pre-filter. MUST match AGE_BAND in the web client
#: (frontend/src/app/GraphView.tsx, preFilterFor) so overview hint counts equal
#: what an expansion actually shows.
_AGE_BAND = 5

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
    case_id: int | str, *, focus: str | None = None, limit: int = 40, offset: int = 0, **filters
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

    # A case's identity is its CaseMasterID; a full row is only needed when a
    # caller filter (or an expansion) actually inspects one, so the row index is
    # built lazily — the common, unfiltered overview never materialises it.
    all_ids = set(df["CaseMasterID"])
    rows_by_cid: dict | None = None

    def _rows() -> dict:
        nonlocal rows_by_cid
        if rows_by_cid is None:
            rows_by_cid = {r.CaseMasterID: r for r in df.itertuples(index=False)}
        return rows_by_cid

    def _case_passes(cid: str, f: dict) -> bool:
        row = _rows().get(cid)
        return row is not None and _passes_filters(cid, row, acc_by_case, vic_by_case, f)

    def qualifies(cid: str) -> bool:
        # with no active filters, qualifying is just "a real, non-seed case"
        return cid in all_ids if not active else _case_passes(cid, filters)

    # Per-channel candidate pools — needed only to PAGINATE an expansion. The
    # overview counts its channels with vectorised masks instead (see below), so
    # it never makes this full O(n) pass over the dataset.
    station_cases, district_cases, subhead_cases = [], [], []
    if focus is not None:
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

    # how many related cases each entity would reveal, and the overall universe.
    if focus is not None:
        # in an expansion the request already carries the active filters, so the
        # per-channel pools are correctly scoped — count them directly.
        expandable = {
            st: len(set(station_cases)),
            di: len(set(district_cases)),
            sh: len(set(subhead_cases)),
        }
        for sa in seed_accused:
            aid = sa["accused_id"]
            expandable[f"ACCUSED_RECORD:{aid}"] = len(suspect_by_acc.get(aid, {}))
        total_related = len(
            set(station_cases) | set(district_cases) | set(subhead_cases)
            | {c for m in suspect_by_acc.values() for c in m}
        )
    else:
        # OVERVIEW: show the count a node reveals when expanded BY DEFAULT — i.e.
        # under the seed's similar-profile pre-filter the client pre-applies — so
        # a node's badge/hover matches what clicking it shows. Each entity drops
        # its own attribute from the profile. Keep this in step with preFilterFor
        # in the web client (frontend/src/app/GraphView.tsx).
        #
        # Computed WITHOUT a full scan: narrow to the rows a channel could reach
        # with vectorised masks first, then run the people-based profile checks
        # only on that (small) survivor set — "read only what's needed".
        acc0 = seed_accused[0] if seed_accused else None
        prof: dict = {}
        if acc0 and acc0.get("gender"):
            prof["gender"] = acc0["gender"]
        if acc0 and acc0.get("age") is not None:
            prof["age_min"] = max(0, acc0["age"] - _AGE_BAND)
            prof["age_max"] = min(120, acc0["age"] + _AGE_BAND)
        if acc0 and acc0.get("name"):
            prof["name_contains"] = acc0["name"].split()[0]

        not_seed = df["CaseMasterID"] != cid0
        m_station = not_seed & (df["station_id"] == s["station_id"])
        m_district = not_seed & (df["district_id"] == s["district_id"])
        m_subhead = not_seed & (df["subhead_id"] == s["subhead_id"])

        # district & sub-head expansions share the effective filter (crime +
        # district + suspect profile); a station additionally pins the station.
        # Both pin crime AND district, so their candidate rows are identical —
        # count once, and take the station-matching share for the station node.
        station_id = s["station_id"]
        n_place = n_station = 0
        for row in df[m_subhead & m_district].itertuples(index=False):
            cid = row.CaseMasterID
            if active and not _passes_filters(cid, row, acc_by_case, vic_by_case, filters):
                continue
            if not _passes_filters(cid, row, acc_by_case, vic_by_case, prof):
                continue
            n_place += 1
            if row.station_id == station_id:
                n_station += 1
        expandable = {st: n_station, di: n_place, sh: n_place}

        # the same-person (accused) channel is scoped only to the seed's crime type
        subhead_ids = set(df.loc[m_subhead, "CaseMasterID"])
        for sa in seed_accused:
            aid = sa["accused_id"]
            members = suspect_by_acc.get(aid, {})
            expandable[f"ACCUSED_RECORD:{aid}"] = sum(
                1 for cid in members if cid in subhead_ids and qualifies(cid)
            )

        # overall related universe (union across channels), caller-filtered
        union_ids = set(df.loc[m_station | m_district | m_subhead, "CaseMasterID"])
        if active:
            union_ids = {c for c in union_ids if qualifies(c)}
        union_ids |= {c for m in suspect_by_acc.values() for c in m}
        total_related = len(union_ids)

    # ---- expand one entity into its related cases (paginated) ----
    assoc_count = 0
    total_matches = 0
    channel = None
    if focus:
        ftype, fid = focus.split(":", 1)
        if ftype == "ACCUSED_RECORD":
            channel = "same_suspect"
            _, cls, w = _CHANNELS[channel]
            members = suspect_by_acc.get(fid, {})
            ordered = list(members)
            total_matches = len(ordered)
            for cid in ordered[offset:offset + limit]:
                m = members[cid]
                cn = g.node("CASE", cid, f"Case {cid}")
                g.node("ACCUSED_RECORD", m["accused_id"], m["name"])
                g.edge("ACCUSED_IN", "FACT", f"ACCUSED_RECORD:{m['accused_id']}", cn, 1.0, cid)
                g.edge("SAME_IDENTITY", cls, focus, f"ACCUSED_RECORD:{m['accused_id']}", w, cid)
            assoc_count = max(0, min(total_matches - offset, limit))
        else:
            channel = {"POLICE_STATION": "same_station", "DISTRICT": "same_district",
                       "CRIME_SUBHEAD": "same_subhead"}.get(ftype)
            pool = {"POLICE_STATION": station_cases, "DISTRICT": district_cases,
                    "CRIME_SUBHEAD": subhead_cases}.get(ftype, [])
            if channel:
                rel, cls, w = _CHANNELS[channel]
                ordered = list(dict.fromkeys(pool))
                total_matches = len(ordered)
                for cid in ordered[offset:offset + limit]:
                    cn = g.node("CASE", cid, f"Case {cid}")
                    g.edge(rel, cls, cn, focus, w, cid)
                assoc_count = max(0, min(total_matches - offset, limit))

    return {
        "synthetic": True,
        "params": {**params, "offset": offset},
        "seed": {"case_id": cid0, "subhead": s["subhead_name"],
                 "station": s["station_name"], "district": s["district_name"],
                 # ids + the primary accused's profile so the client can pre-apply
                 # the seed's attributes as filters when expanding an entity
                 # ("similar cases here / similar suspects / by this person")
                 "subhead_id": s["subhead_id"], "district_id": s["district_id"],
                 "station_id": s["station_id"],
                 "accused_name": seed_accused[0]["name"] if seed_accused else None,
                 "accused_age": seed_accused[0]["age"] if seed_accused else None,
                 "accused_gender": seed_accused[0]["gender"] if seed_accused else None},
        "focus": focus,
        "channel": channel,
        "association_count": assoc_count,
        "total_matches": total_matches,
        "offset": offset,
        "total_related": total_related,
        "expandable": expandable,
        "nodes": list(g.nodes.values()),
        "edges": list(g.edges.values()),
    }
