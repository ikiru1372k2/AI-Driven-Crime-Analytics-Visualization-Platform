"""Deterministic BriefFacts narrative templates (SYNTHETIC).

The MO template narratives are the textual ground truth for MO extraction
validation (MO-005/#41): they explicitly state offender count, motorcycle
mobility, snatching action and gold-chain target. Background narratives vary
by crime sub-head and deliberately omit some attributes (UNKNOWN test bed).
"""

import random

MO_TEMPLATES = [
    "Two unknown persons travelling on a motorcycle approached the complainant "
    "near {place} and snatched a gold chain before escaping towards {road}.",
    "The complainant was walking near {place} when two men on a motorcycle "
    "came from behind, snatched her gold chain and sped away towards {road}.",
    "Two accused riding a motorcycle snatched the gold chain of the complainant "
    "at {place} and escaped in the direction of {road}.",
]

PLACES = ["the bus stop", "the market road", "an industrial gate", "the park entrance",
          "a petrol bunk", "the railway underpass"]
ROADS = ["Tumakuru Road", "Magadi Road", "the ring road", "the service road", "NH-48"]

BACKGROUND = {
    31: ["A quarrel between the deceased and the accused escalated near {place}; "
         "the deceased succumbed to injuries."],
    32: ["The accused assaulted the complainant with hands and a stick near {place} "
         "following a property dispute."],
    33: ["The complainant reported that her son was taken away by known persons "
         "from near {place}."],
    71: ["Unknown persons waylaid the complainant near {place} and robbed cash "
         "under threat.",
         "The complainant was stopped near {place} by unknown persons who took his "
         "mobile phone by force."],
    72: ["Unknown person stole the complainant's mobile phone from his pocket at "
         "{place}.",
         "Theft of a parked two-wheeler was reported from {place}."],
    73: ["During the night, unknown persons broke open the lock of the house near "
         "{place} and committed theft of valuables."],
    111: ["The accused collected money from the complainant promising a job and "
          "failed to return it."],
    112: ["Nuisance was reported near {place}; the accused obstructed the public "
          "road."],
}

ANOMALY_NARRATIVE = (
    "At around 4 AM, six accused persons arrived in two cars near the parking yard, "
    "threatened the security guard and drove away with a parked lorry (vehicle)."
)


def mo_narrative(rng: random.Random) -> str:
    t = rng.choice(MO_TEMPLATES)
    return t.format(place=rng.choice(PLACES), road=rng.choice(ROADS))


def background_narrative(rng: random.Random, sub_head_id: int) -> str:
    options = BACKGROUND.get(sub_head_id, BACKGROUND[112])
    return rng.choice(options).format(place=rng.choice(PLACES))
