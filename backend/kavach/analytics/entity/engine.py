"""Cross-FIR entity resolution (EPIC-ER-RES, issues #47/#48).

Links accused persons that recur across FIRs under fragmented identities -
"Ravi Kumar", "Ravi K", "Ravi Kumar S" are one person - while refusing to merge
different people who merely share a name ("Suresh Babu", 24 vs 52). Identity is
*discovered* from attributes (name, gender, age); the per-record PersonID is
never used to join across cases (ADR-003).

Three stages:
  1. Blocking - group by (gender, first name token) so we never score all O(N^2)
     pairs, only plausible ones.
  2. Explainable match scoring - a weighted blend of fuzzy name similarity and
     age proximity, gated by gender, with every contributing and contradictory
     signal recorded so a reviewer can see *why*.
  3. Clustering - union candidate links into identity groups. These are
     candidates for human review; nothing is auto-merged.

Input data is SYNTHETIC (ADR-011). This module discovers identities from the
data alone; it never reads the generator's planted answer key.
"""

from __future__ import annotations

import functools
import re
from difflib import SequenceMatcher

from kavach.api import data

# scoring weights / gates. The name gate is deliberately high: sharing only a
# common given name ("Ravi ...") must NOT link people - the surname has to match
# too, otherwise single-link clustering chains every "Ravi" into one blob.
_W_NAME = 0.65
_W_AGE = 0.35
_MIN_SCORE = 0.72
_MIN_NAME_SIM = 0.82
_MAX_AGE_GAP = 8  # a larger gap is a hard contradiction (defeats same-name decoys)
_CLUSTER_AGE_SPAN = 10  # a single identity can't span more age than this (no chaining)


def _tokens(name: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z ]", " ", (name or "").lower()).split() if t]


def _tok_match(a: str, b: str) -> float:
    if a == b:
        return 1.0
    # single-letter initial against a full token ("k" ~ "kumar")
    if (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return 0.85
    if a.startswith(b) or b.startswith(a):
        return 0.8
    return SequenceMatcher(None, a, b).ratio()


def _covers(src: list[str], dst: list[str]) -> tuple[bool, list[float]]:
    """Can every FULL (len>1) token in ``src`` find a counterpart in ``dst``?

    Initials (len==1) are tolerated (unmatched initials don't penalise), but a
    real surname with no counterpart is a mismatch - this is what stops
    "Ravi Kumar S" from linking to "Ravi Shankar" via the stray "S".
    """
    scores = []
    for t in src:
        if len(t) == 1:
            continue  # initial: optional
        best = max((_tok_match(t, u) for u in dst), default=0.0)
        scores.append(best)
        if best < 0.8:
            return False, scores
    return True, scores


def _name_sim(ta: list[str], tb: list[str]) -> float:
    """Name similarity gated on the given name plus full-surname coverage."""
    if not ta or not tb:
        return 0.0
    given = _tok_match(ta[0], tb[0])
    if given < 0.8:
        return 0.0  # different given names -> not the same person
    a_rest, b_rest = ta[1:], tb[1:]
    ok_a, sa = _covers(a_rest, b_rest)
    ok_b, sb = _covers(b_rest, a_rest)
    if not (ok_a and ok_b):
        return 0.3  # a real surname on one side has no counterpart
    surname_scores = sa + sb
    surname = sum(surname_scores) / len(surname_scores) if surname_scores else given
    return 0.5 * given + 0.5 * surname


def _age_score(a: int | None, b: int | None) -> tuple[float, int | None]:
    if a is None or b is None:
        return 0.5, None
    gap = abs(a - b)
    if gap <= 1:
        return 1.0, gap
    if gap <= 3:
        return 0.85, gap
    if gap <= 6:
        return 0.6, gap
    if gap <= 10:
        return 0.3, gap
    return 0.0, gap


def _score_pair(x: dict, y: dict) -> dict | None:
    """Explainable match score for two accused records, or None if not comparable."""
    if x["gender"] != y["gender"]:
        return None
    name_sim = _name_sim(_tokens(x["name"]), _tokens(y["name"]))
    age_sc, gap = _age_score(x["age"], y["age"])
    score = _W_NAME * name_sim + _W_AGE * age_sc

    contributing, contradictory = [], []
    if name_sim >= 0.8:
        contributing.append(f"name: {x['name']!r} ~ {y['name']!r} ({name_sim:.2f})")
    elif name_sim >= _MIN_NAME_SIM:
        contributing.append(f"name partially matches ({name_sim:.2f})")
    contributing.append(f"gender match ({x['gender']})")
    if gap is not None and gap <= 3:
        contributing.append(f"age within {gap} year{'s' if gap != 1 else ''}")
    if gap is not None and gap > _MAX_AGE_GAP:
        contradictory.append(f"age differs by {gap} years")

    linked = (
        name_sim >= _MIN_NAME_SIM
        and score >= _MIN_SCORE
        and (gap is None or gap <= _MAX_AGE_GAP)
    )
    return {
        "a": x["accused_id"], "b": y["accused_id"],
        "score": round(score, 3), "name_sim": round(name_sim, 3), "age_gap": gap,
        "contributing": contributing, "contradictory": contradictory, "linked": linked,
    }


class _Union:
    def __init__(self) -> None:
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> None:
        self.parent[self.find(a)] = self.find(b)


@functools.lru_cache(maxsize=8)
def resolve_identities(*, district_id: int | None = None, min_cluster_size: int = 2) -> dict:
    """Discover candidate cross-FIR identities from accused attributes.

    Returns identity clusters (size >= ``min_cluster_size``) for human review -
    each with its member records, a confidence, and the pairwise signal
    breakdown. Nothing is auto-merged (human-in-the-loop, #49).

    Cached per (district_id, min_cluster_size): the pairwise comparison runs
    over every accused record and took ~13s per request on the deployed demo,
    which reads as a hung screen. The dataset is static for a run (ADR-011),
    same assumption as data.enriched_cases(). Callers must not mutate the
    returned dict; tests that switch KAVACH_DATA_DIR call
    resolve_identities.cache_clear() alongside enriched_cases.cache_clear().
    """
    records = data.accused_records()
    if district_id is not None:
        records = [r for r in records if str(r["district_id"]) == str(district_id)]
    by_id = {r["accused_id"]: r for r in records}

    # 1. blocking: (gender, first name token) - cheap, keeps only plausible pairs
    blocks: dict[tuple, list[dict]] = {}
    for r in records:
        toks = _tokens(r["name"])
        if not toks or not r["gender"]:
            continue
        blocks.setdefault((r["gender"], toks[0]), []).append(r)

    # 2. score pairs within blocks; keep linked pairs
    uf = _Union()
    links: list[dict] = []
    pairs_scored = 0
    for members in blocks.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                res = _score_pair(members[i], members[j])
                pairs_scored += 1
                if res and res["linked"]:
                    uf.union(res["a"], res["b"])
                    links.append(res)

    # 3. gather components, then split each into age-coherent identities so a
    #    common name can't chain a 23-year-old to a 60-year-old via intermediates
    components: dict = {}
    linked_ids = {i for ln in links for i in (ln["a"], ln["b"])}
    for aid in linked_ids:
        components.setdefault(uf.find(aid), []).append(aid)

    groups: list[list] = []
    for ids in components.values():
        known = sorted(
            (i for i in ids if by_id[i]["age"] is not None), key=lambda i: by_id[i]["age"]
        )
        unknown = [i for i in ids if by_id[i]["age"] is None]
        current: list = []
        for i in known:
            if current and by_id[i]["age"] - by_id[current[0]]["age"] > _CLUSTER_AGE_SPAN:
                groups.append(current)
                current = []
            current.append(i)
        if current:
            current.extend(unknown)  # attach unknown-age members to the last band
            groups.append(current)
        elif unknown:
            groups.append(unknown)

    out = []
    for ids in groups:
        if len(ids) < min_cluster_size:
            continue
        idset = set(ids)
        members = [by_id[i] for i in ids]
        member_links = [ln for ln in links if ln["a"] in idset and ln["b"] in idset]
        if not member_links:
            continue  # split severed all links -> not a coherent identity
        confidence = round(sum(ln["score"] for ln in member_links) / len(member_links), 3)
        ages = [m["age"] for m in members if m["age"] is not None]
        out.append({
            "cluster_id": f"id-{min(ids)}",
            "size": len(ids),
            "confidence": confidence,
            "status": "pending_review",  # never auto-merged
            "gender": members[0]["gender"],
            "name_variants": sorted({m["name"] for m in members}),
            "age_range": [min(ages), max(ages)] if ages else None,
            "districts": sorted({m["district_name"] for m in members if m["district_name"]}),
            "members": members,
            "signals": member_links,
        })
    # rank cross-district identities first - a person recurring across districts
    # is the high-value review item (the "same offender, many places" story)
    out.sort(key=lambda c: (len(c["districts"]), c["confidence"], c["size"]), reverse=True)

    return {
        "synthetic": True,
        "params": {"district_id": district_id, "min_cluster_size": min_cluster_size,
                   "min_score": _MIN_SCORE, "max_age_gap": _MAX_AGE_GAP},
        "accused_total": len(records),
        "pairs_scored": pairs_scored,
        "candidate_count": len(out),
        "candidates": out,
    }
