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


def find_associations(case_id: int | str, *, limit: int = 40, **filters) -> dict:
    """Association graph for a seed case: related cases + the entities linking them."""
    df = data.enriched_cases()
    seed = df[df["CaseMasterID"] == str(case_id)]
    active = {k: v for k, v in filters.items() if v not in (None, "")}
    params = {"case_id": str(case_id), "limit": limit, "filters": active}
    if seed.empty:
        return {"synthetic": True, "params": params, "seed": None,
                "association_count": 0, "nodes": [], "edges": []}
    s = seed.iloc[0]

    accused = data.accused_records()
    victims = data.victim_records()
    acc_by_case: dict[str, list[dict]] = {}
    vic_by_case: dict[str, list[dict]] = {}
    for a in accused:
        acc_by_case.setdefault(a["case_id"], []).append(a)
    for v in victims:
        vic_by_case.setdefault(v["case_id"], []).append(v)

    seed_accused = acc_by_case.get(str(case_id), [])
    ident_idx = _same_suspect_index()
    # same-suspect: seed accused -> other cases sharing an identity cluster
    same_suspect: dict[str, list[tuple[dict, dict]]] = {}
    for sa in seed_accused:
        for m in ident_idx.get(sa["accused_id"], []):
            if m["case_id"] != str(case_id):
                same_suspect.setdefault(m["case_id"], []).append((sa, m))

    # score every other case by its association channels (single pass)
    scored: list[tuple[str, list[str], float]] = []
    for row in df.itertuples(index=False):
        cid = row.CaseMasterID
        if cid == str(case_id):
            continue
        bases = []
        if row.station_id == s["station_id"]:
            bases.append("same_station")
        if row.subhead_id == s["subhead_id"]:
            bases.append("same_subhead")
        if row.district_id == s["district_id"]:
            bases.append("same_district")
        if cid in same_suspect:
            bases.append("same_suspect")
        if not bases:
            continue
        if not _passes_filters(cid, row, acc_by_case, vic_by_case, filters):
            continue
        strength = sum(_CHANNELS[b][2] for b in bases)
        scored.append((cid, bases, strength))

    scored.sort(key=lambda x: x[2], reverse=True)
    scored = scored[:limit]

    # ---- build the graph ----
    g = _G()
    seed_case = g.node("CASE", case_id, f"Case {case_id}")
    st = g.node("POLICE_STATION", s["station_id"], s["station_name"] or "Station")
    di = g.node("DISTRICT", s["district_id"], s["district_name"] or "District")
    sh = g.node("CRIME_SUBHEAD", s["subhead_id"], s["subhead_name"] or "Sub-head")
    g.edge("REGISTERED_AT", "FACT", seed_case, st, 1.0, case_id)
    g.edge("OCCURRED_IN", "FACT", seed_case, di, 1.0, case_id)
    g.edge("CLASSIFIED_AS", "FACT", seed_case, sh, 1.0, case_id)
    for a in seed_accused:
        an = g.node("ACCUSED_RECORD", a["accused_id"], a["name"])
        g.edge("ACCUSED_IN", "FACT", an, seed_case, 1.0, case_id)
    for v in vic_by_case.get(str(case_id), []):
        vn = g.node("VICTIM_RECORD", v["victim_id"], v["name"])
        g.edge("VICTIM_IN", "FACT", vn, seed_case, 1.0, case_id)

    for cid, bases, _strength in scored:
        cn = g.node("CASE", cid, f"Case {cid}")
        for b in bases:
            rel, cls, w = _CHANNELS[b]
            if b == "same_station":
                g.edge(rel, cls, cn, st, w, cid)
            elif b == "same_district":
                g.edge(rel, cls, cn, di, w, cid)
            elif b == "same_subhead":
                g.edge(rel, cls, cn, sh, w, cid)
            elif b == "same_suspect":
                for seed_acc, other in same_suspect[cid]:
                    oa = g.node("ACCUSED_RECORD", other["accused_id"], other["name"])
                    sa = g.node("ACCUSED_RECORD", seed_acc["accused_id"], seed_acc["name"])
                    g.edge("ACCUSED_IN", "FACT", oa, cn, 1.0, cid)
                    g.edge("SAME_IDENTITY", "POTENTIAL_ASSOCIATION", sa, oa, w, cid)

    return {
        "synthetic": True,
        "params": params,
        "seed": {"case_id": str(case_id), "subhead": s["subhead_name"],
                 "station": s["station_name"], "district": s["district_name"]},
        "association_count": len(scored),
        "channels": sorted({b for _, bs, _ in scored for b in bs}),
        "nodes": list(g.nodes.values()),
        "edges": list(g.edges.values()),
    }
