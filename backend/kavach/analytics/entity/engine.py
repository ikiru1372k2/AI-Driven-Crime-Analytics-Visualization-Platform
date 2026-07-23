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


def _name_partial(query: str, cand: list[str]) -> float:
    """Loose search-box match: does the typed text appear in the candidate name?

    Unlike ``_name_sim`` (which anchors on the given name to resolve the SAME
    person), this powers the top search box — any typed fragment that prefixes or
    sits inside any name token is a hit, so "naik", "haris" or "kumar" all find
    people regardless of where the fragment falls. Returns a coverage score in
    [0, 1]; 0 means no hit (every typed token must land somewhere).
    """
    q = re.sub(r"[^a-z ]", " ", (query or "").lower()).split()
    if not q or not cand:
        return 0.0
    scores = []
    for qt in q:
        best = 0.0
        for ct in cand:
            if ct == qt:
                m = 1.0
            elif ct.startswith(qt):
                m = 0.9  # prefix: "haris" -> "harish"
            elif qt in ct:
                m = 0.75  # substring: "aris" -> "harish"
            else:
                m = SequenceMatcher(None, qt, ct).ratio()
            best = max(best, m)
        if best < 0.6:
            return 0.0  # this fragment matches nothing -> not a hit
        scores.append(best)
    return sum(scores) / len(scores)


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
def _resolve_cached(district_id: int | None, min_cluster_size: int) -> dict:
    """Positional-arg cache impl behind ``resolve_identities`` (see wrapper).

    Keyed positionally so every caller — the warmer's ``resolve_identities()``,
    the route's ``resolve_identities(district_id=None, min_cluster_size=2)`` and
    association's same-suspect index — share ONE cache entry. Keying on keyword
    args (the old bug) made ``f()`` and ``f(district_id=None)`` distinct keys, so
    the warmer's prime was never reused and the route recomputed cold → 408.
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


def resolve_identities(*, district_id: int | None = None, min_cluster_size: int = 2) -> dict:
    """Discover candidate cross-FIR identities from accused attributes.

    Returns identity clusters (size >= ``min_cluster_size``) for human review -
    each with its member records, a confidence, and the pairwise signal
    breakdown. Nothing is auto-merged (human-in-the-loop, #49).

    Thin keyword wrapper over the positionally-cached ``_resolve_cached`` so all
    callers hit the same cache entry (the pairwise comparison runs over every
    accused record and is the expensive step; the dataset is static per run,
    ADR-011). Tests/warmer that switch data call ``resolve_identities.cache_clear()``.
    """
    return _resolve_cached(district_id, min_cluster_size)


#: expose the underlying cache controls on the public name (warmer/tests use it)
resolve_identities.cache_clear = _resolve_cached.cache_clear
resolve_identities.cache_info = _resolve_cached.cache_info


def find_similar(
    name: str,
    age: int | None = None,
    gender: str | None = None,
    *,
    limit: int = 50,
    min_name_sim: float = 0.5,
    partial: bool = False,
) -> list[dict]:
    """People whose attributes resemble one query person — an ON-DEMAND search.

    The single-person counterpart to ``resolve_identities``: it scores the query
    (name, optional age, optional sex) against every DISTINCT accused person once
    — O(n), never the O(n^2) all-pairs scan — so it can run live on the request
    path without timing out. Reuses the same explainable scorers (``_name_sim``,
    ``_age_score``) and weights as the cluster path, so a match here means the
    same thing there.

    Matching (ADR-003, attributes only):
      - **sex** is a hard filter when given (opposite gender never matches);
      - **name** — with ``partial`` (the top search box) any typed fragment that
        prefixes or sits inside a name token is a hit (``_name_partial``); without
        it (a row's "find similar") the stricter same-person scorer ``_name_sim``
        applies and must clear ``min_name_sim``;
      - **age**, when given, is a band: a gap over ``_MAX_AGE_GAP`` is a hard
        contradiction and excluded; otherwise it blends into the score. With no
        age (the name-only top search) the score is the name similarity alone.
    Returns matches sorted by confidence desc, capped at ``limit``.
    """
    q_tokens = _tokens(name)
    q_gender = (gender or "").strip() or None
    matches: list[dict] = []
    for person in data.ranked_accused():
        if q_gender and person["gender"] and person["gender"] != q_gender:
            continue  # sex is a hard filter
        cand_tokens = _tokens(person["name"])
        if partial:
            name_sim = _name_partial(name, cand_tokens)
            if name_sim <= 0:
                continue  # typed fragment matches nothing
        else:
            name_sim = _name_sim(q_tokens, cand_tokens)
            if name_sim < min_name_sim:
                continue

        contributing, contradictory = [], []
        if partial:
            contributing.append(f"name matches {name!r} ({name_sim:.2f})")
        else:
            contributing.append(
                f"name: {name!r} ~ {person['name']!r} ({name_sim:.2f})"
                if name_sim >= 0.8
                else f"name partially matches ({name_sim:.2f})"
            )
        if q_gender and person["gender"]:
            contributing.append(f"same sex ({person['gender']})")

        if age is not None and person["age"] is not None:
            age_sc, gap = _age_score(age, person["age"])
            if gap is not None and gap > _MAX_AGE_GAP:
                continue  # age band: too far apart to be the same person
            score = _W_NAME * name_sim + _W_AGE * age_sc
            if gap is not None and gap <= 3:
                contributing.append(f"age within {gap} year{'s' if gap != 1 else ''}")
        else:
            gap = None
            score = name_sim  # name-only search: no age signal to blend

        matches.append(
            {
                "name": person["name"],
                "age": person["age"],
                "gender": person["gender"],
                "districts": person["districts"],
                "case_count": person["case_count"],
                "confidence": round(score, 3),
                "name_sim": round(name_sim, 3),
                "age_gap": gap,
                "contributing": contributing,
                "contradictory": contradictory,
                "cross_district": len(person["districts"]) > 1,
            }
        )
    matches.sort(key=lambda m: (-m["confidence"], -m["case_count"]))
    return matches[:limit]
