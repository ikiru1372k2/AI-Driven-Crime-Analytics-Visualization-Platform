"""Investigative association search (EPIC-ASSOC).

Given a seed case, surface *related* cases across the dataset so an analyst can
find "anything relatable". Associations come from several channels, each with a
strength weight and its own evidence:

  same_suspect  - an accused resolves to the SAME PERSON as one of the seed's
                  accused (entity resolution, #46-50). Strongest signal; drawn
                  as a POTENTIAL_ASSOCIATION (candidate for human review).
  same_victim   - a victim with the same name across FIRs.
  same_station  - filed at the same police station.
  same_subhead  - the same crime sub-head (e.g. Robbery).
  same_district - occurred in the same district (weak on its own).

Progressive by design (PERF-001):
  * OVERVIEW (focus=None) is TRIVIAL — just the seed case and its own direct
    entities (station / district / crime / accused / victims), each flagged as
    expandable. It runs NO entity resolution, NO victim matching and NO dataset
    scan, so it never blocks on the request budget.
  * EXPANSION (focus="TYPE:id") pulls the related cases for the ONE clicked
    entity, applies the caller's attribute filters SERVER-SIDE, and paginates.
    Same-person resolution (accused/victim) happens ONLY here, on demand.

Two orthogonal controls (design):
  * View   = which node types the client renders (projection; done client-side).
  * Filter = which records QUALIFY (predicates applied HERE, server-side).

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
    "same_victim": ("SAME_IDENTITY", "POTENTIAL_ASSOCIATION", 1.0),
    "same_station": ("REGISTERED_AT", "FACT", 0.4),
    "same_subhead": ("CLASSIFIED_AS", "FACT", 0.35),
    "same_district": ("OCCURRED_IN", "FACT", 0.2),
}

#: place/charge focus type -> (channel, the enriched_cases column it shares)
_PLACE_FOCUS = {
    "POLICE_STATION": ("same_station", "station_id"),
    "DISTRICT": ("same_district", "district_id"),
    "CRIME_SUBHEAD": ("same_subhead", "subhead_id"),
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


# --- cached, cheap indices (built once from the memoized record tables) --------

@functools.lru_cache(maxsize=1)
def _people_by_case() -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """(accused_by_case, victims_by_case). One O(n) pass over memoized records."""
    acc: dict[str, list[dict]] = {}
    vic: dict[str, list[dict]] = {}
    for a in data.accused_records():
        acc.setdefault(a["case_id"], []).append(a)
    for v in data.victim_records():
        vic.setdefault(v["case_id"], []).append(v)
    return acc, vic


@functools.lru_cache(maxsize=1)
def _rows_by_cid() -> dict:
    """CaseMasterID -> enriched row, for server-side filtering of an expansion."""
    df = data.enriched_cases()
    return {r.CaseMasterID: r for r in df.itertuples(index=False)}


@functools.lru_cache(maxsize=1)
def _same_suspect_index() -> dict[str, list[dict]]:
    """accused_id -> the identity cluster's members (same-person candidates).

    Runs entity resolution (the expensive step) — reached ONLY when an accused
    node is expanded, never on the overview.
    """
    idx: dict[str, list[dict]] = {}
    for cluster in resolve_identities()["candidates"]:
        for m in cluster["members"]:
            idx[m["accused_id"]] = cluster["members"]
    return idx


@functools.lru_cache(maxsize=1)
def _victim_name_index() -> dict[str, list[dict]]:
    """normalized victim name -> victim records sharing it (same-victim channel).

    Reached ONLY when a victim node is expanded. Cheap O(n) group-by, no O(n²).
    """
    idx: dict[str, list[dict]] = {}
    for v in data.victim_records():
        key = (v.get("name") or "").strip().lower()
        if key:
            idx.setdefault(key, []).append(v)
    return idx


def cache_clear() -> None:
    """Drop all association caches (called by the warmer after a data swap)."""
    _people_by_case.cache_clear()
    _rows_by_cid.cache_clear()
    _same_suspect_index.cache_clear()
    _victim_name_index.cache_clear()


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


def _seed_block(s, cid0: str, seed_accused: list[dict]) -> dict:
    """The seed's ids + primary-accused profile (client pre-applies as filters)."""
    a0 = seed_accused[0] if seed_accused else None
    return {
        "case_id": cid0, "subhead": s["subhead_name"],
        "station": s["station_name"], "district": s["district_name"],
        "subhead_id": s["subhead_id"], "district_id": s["district_id"],
        "station_id": s["station_id"],
        "accused_name": a0["name"] if a0 else None,
        "accused_age": a0["age"] if a0 else None,
        "accused_gender": a0["gender"] if a0 else None,
    }


def _empty(params: dict) -> dict:
    return {"synthetic": True, "params": params, "seed": None, "focus": params.get("focus"),
            "channel": None, "association_count": 0, "total_matches": 0, "offset": 0,
            "total_related": 0, "expandable": {}, "nodes": [], "edges": []}


def find_associations(
    case_id: int | str, *, focus: str | None = None, limit: int = 40, offset: int = 0, **filters
) -> dict:
    """Association graph for a seed case, revealed progressively (see module doc).

    focus=None       -> the OVERVIEW: seed + its own entities, each `expandable`.
    focus="TYPE:id"  -> EXPAND that entity into related cases (filtered, paged).
    """
    df = data.enriched_cases()
    cid0 = str(case_id)
    active = {k: v for k, v in filters.items() if v not in (None, "")}
    params = {"case_id": cid0, "focus": focus, "limit": limit, "offset": offset, "filters": active}
    seed = df[df["CaseMasterID"] == cid0]
    if seed.empty:
        return _empty(params)
    s = seed.iloc[0]
    acc_by_case, vic_by_case = _people_by_case()
    seed_accused = acc_by_case.get(cid0, [])
    seed_victims = vic_by_case.get(cid0, [])

    # ---- seed + its own entities (always present) ----
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
    for v in seed_victims:
        g.node("VICTIM_RECORD", v["victim_id"], v["name"])
        g.edge("VICTIM_IN", "FACT", f"VICTIM_RECORD:{v['victim_id']}", seed_case, 1.0, case_id)

    # ---- OVERVIEW: flag the seed's entities expandable; compute nothing else ----
    if focus is None:
        expandable = {st: 1, di: 1, sh: 1}
        for a in seed_accused:
            expandable[_nid("ACCUSED_RECORD", a["accused_id"])] = 1
        for v in seed_victims:
            expandable[_nid("VICTIM_RECORD", v["victim_id"])] = 1
        return {
            "synthetic": True, "params": params, "seed": _seed_block(s, cid0, seed_accused),
            "focus": None, "channel": None, "association_count": 0, "total_matches": 0,
            "offset": 0, "total_related": 0, "expandable": expandable,
            "nodes": list(g.nodes.values()), "edges": list(g.edges.values()),
        }

    # ---- EXPANSION: the ONE clicked entity -> related cases (filtered, paged) ----
    ftype, fid = focus.split(":", 1)
    channel: str | None = None
    ordered: list[str] = []
    members_by_cid: dict[str, dict] = {}

    if ftype in ("ACCUSED_RECORD", "VICTIM_RECORD"):
        # same-person channel — entity resolution / victim matching happens here
        if ftype == "ACCUSED_RECORD":
            channel = "same_suspect"
            cluster = _same_suspect_index().get(fid, [])
        else:
            channel = "same_victim"
            vname = next(
                ((v.get("name") or "").strip().lower()
                 for v in seed_victims if v["victim_id"] == fid),
                None,
            )
            cluster = _victim_name_index().get(vname, []) if vname else []
        idkey = "accused_id" if channel == "same_suspect" else "victim_id"
        for m in cluster:
            mcid = m["case_id"]
            if mcid != cid0 and mcid not in members_by_cid:
                members_by_cid[mcid] = m
        ordered = list(members_by_cid)
    elif ftype in _PLACE_FOCUS:
        channel, col = _PLACE_FOCUS[ftype]
        mask = (df["CaseMasterID"] != cid0) & (df[col] == s[col])
        ordered = list(df.loc[mask, "CaseMasterID"])

    # apply the caller's attribute filters SERVER-SIDE (orthogonal to the View)
    if active:
        rows = _rows_by_cid()
        ordered = [
            c for c in ordered
            if c in rows and _passes_filters(c, rows[c], acc_by_case, vic_by_case, filters)
        ]

    total_matches = len(ordered)

    # draw only the requested page
    if channel in ("same_suspect", "same_victim"):
        _, cls, w = _CHANNELS[channel]
        ntype = "ACCUSED_RECORD" if channel == "same_suspect" else "VICTIM_RECORD"
        fact_rel = "ACCUSED_IN" if channel == "same_suspect" else "VICTIM_IN"
        idkey = "accused_id" if channel == "same_suspect" else "victim_id"
        for cid in ordered[offset:offset + limit]:
            m = members_by_cid[cid]
            cn = g.node("CASE", cid, f"Case {cid}")
            g.node(ntype, m[idkey], m["name"])
            g.edge(fact_rel, "FACT", f"{ntype}:{m[idkey]}", cn, 1.0, cid)
            g.edge("SAME_IDENTITY", cls, focus, f"{ntype}:{m[idkey]}", w, cid)
    elif channel:
        rel, cls, w = _CHANNELS[channel]
        for cid in ordered[offset:offset + limit]:
            cn = g.node("CASE", cid, f"Case {cid}")
            g.edge(rel, cls, cn, focus, w, cid)

    assoc_count = max(0, min(total_matches - offset, limit))
    return {
        "synthetic": True, "params": params, "seed": _seed_block(s, cid0, seed_accused),
        "focus": focus, "channel": channel, "association_count": assoc_count,
        "total_matches": total_matches, "offset": offset, "total_related": total_matches,
        "expandable": {focus: 1}, "nodes": list(g.nodes.values()), "edges": list(g.edges.values()),
    }
