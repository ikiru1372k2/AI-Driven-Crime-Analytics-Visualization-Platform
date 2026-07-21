"""MO similarity — "show me cases committed the same way" (MO-004/#40).

Compares the schema's SIMILARITY_ATTRIBUTES between two extracted profiles.
Three rules keep the result honest:

* UNKNOWN never matches. Two narratives that both failed to mention a weapon
  have not agreed about anything, so absence is not similarity.
* The score is the share of ATTRIBUTES BOTH CASES ACTUALLY STATE, weighted by
  how discriminating each attribute is — matching an unusual target says more
  than matching a common action.
* Every result carries the attributes that matched, so an officer sees the
  reason rather than a bare number.

Output is POTENTIAL_ASSOCIATION: a lead to check, never a claim that the same
person did both (ADR-004 — nothing is auto-merged).
"""

from __future__ import annotations

from dataclasses import dataclass

from kavach.analytics.mo.schema import SIMILARITY_ATTRIBUTES, UNKNOWN, MoProfile

#: How much each shared attribute contributes. Method and target discriminate
#: far better than the broad action bucket: hundreds of cases are "theft", but
#: "entry_breakin + jewelry on a motorcycle" is a signature.
ATTRIBUTE_WEIGHTS: dict[str, float] = {
    "crime_action": 1.0,
    "target_type": 1.6,
    "mobility": 1.8,
    "approach_method": 1.5,
    "offender_count": 1.2,
    "time_context": 0.8,
    "weapon_involved": 1.0,
}

#: Below this, cases are not worth showing as related.
MIN_SCORE = 0.35
#: A single weak overlap ("both are thefts") is not a lead.
MIN_SHARED_ATTRIBUTES = 2


@dataclass(frozen=True)
class MoMatch:
    case_master_id: int
    score: float
    matched: tuple[str, ...]
    differed: tuple[str, ...]
    #: attributes only one side stated — neither agreement nor disagreement
    uncomparable: tuple[str, ...]

    @property
    def explanation(self) -> str:
        return "same " + ", ".join(a.replace("_", " ") for a in self.matched)


def compare(left: MoProfile, right: MoProfile) -> MoMatch | None:
    """Score two profiles, or None when they are not comparably similar."""
    matched: list[str] = []
    differed: list[str] = []
    uncomparable: list[str] = []
    weight_matched = 0.0
    weight_comparable = 0.0

    for name in SIMILARITY_ATTRIBUTES:
        a = getattr(left, name)
        b = getattr(right, name)
        if a.value == UNKNOWN or b.value == UNKNOWN:
            uncomparable.append(name)  # absence of evidence is not agreement
            continue
        weight = ATTRIBUTE_WEIGHTS.get(name, 1.0)
        weight_comparable += weight
        if a.value == b.value:
            matched.append(name)
            weight_matched += weight
        else:
            differed.append(name)

    if len(matched) < MIN_SHARED_ATTRIBUTES or weight_comparable == 0:
        return None
    score = weight_matched / weight_comparable
    if score < MIN_SCORE:
        return None
    return MoMatch(
        case_master_id=right.case_master_id,
        score=round(score, 4),
        matched=tuple(matched),
        differed=tuple(differed),
        uncomparable=tuple(uncomparable),
    )


def find_similar(
    target: MoProfile, corpus: list[MoProfile], *, limit: int = 20
) -> list[MoMatch]:
    """Cases whose MO resembles `target`, best first.

    Ties break on case id so repeated calls return a stable order.
    """
    matches = []
    for candidate in corpus:
        if candidate.case_master_id == target.case_master_id:
            continue
        match = compare(target, candidate)
        if match is not None:
            matches.append(match)
    matches.sort(key=lambda m: (-m.score, -len(m.matched), m.case_master_id))
    return matches[:limit]
