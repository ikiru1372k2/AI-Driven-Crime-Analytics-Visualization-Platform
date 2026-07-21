"""Deterministic BriefFacts narrative templates (SYNTHETIC).

Two jobs:

1. The MO template narratives are the textual ground truth for MO extraction
   validation (MO-005/#41): whatever wording is drawn, they always state two
   offenders, motorcycle mobility, snatching and a gold chain, so the planted
   pattern stays detectable.

2. Background narratives model how FIRs actually read: the same offence gets
   written many different ways, and any given narrative mentions only some of
   the facts. Weapons, timing, vehicles and offender counts appear in some
   reports and not others, which is what produces a realistic spread of MO
   combinations — and an honest per-attribute UNKNOWN rate rather than a
   uniform one.

Everything is drawn from the caller's seeded Random, so a given seed always
reproduces the same corpus.
"""

import random

# The planted chain-snatching pattern. Phrasing varies; the four ground-truth
# signals (two offenders / motorcycle / snatching / gold chain) never do.
MO_TEMPLATES = [
    "Two unknown persons travelling on a motorcycle approached the complainant "
    "near {place} and snatched a gold chain before escaping towards {road}.",
    "The complainant was walking near {place} when two men on a motorcycle "
    "came from behind, snatched her gold chain and sped away towards {road}.",
    "Two accused riding a motorcycle snatched the gold chain of the complainant "
    "at {place} and escaped in the direction of {road}.",
    "While the complainant was near {place}, two unidentified men on a "
    "motorcycle snatched the gold chain from her neck and fled towards {road}.",
    "Two persons on a motorcycle waylaid the complainant near {place}, snatched "
    "a gold chain and escaped towards {road}. {time_phrase}",
]

PLACES = ["the bus stop", "the market road", "an industrial gate", "the park entrance",
          "a petrol bunk", "the railway underpass", "the temple street",
          "a school gate", "the vegetable market", "an ATM kiosk",
          "the flyover service lane", "a bank entrance"]
ROADS = ["Tumakuru Road", "Magadi Road", "the ring road", "the service road", "NH-48",
         "Kanakapura Road", "the bypass road", "Old Airport Road"]

#: Optional clauses. Each is drawn independently, so different FIRs expose
#: different attributes — the realistic case, and the reason UNKNOWN rates
#: differ per attribute instead of being uniform.
TIME_PHRASES = [
    "The incident occurred at night.",
    "The incident took place during the day.",
    "This happened at around dawn.",
    "The offence occurred late at night.",
    "It was reported to have happened in the afternoon.",
]
WEAPON_PHRASES = [
    "The accused was armed with a knife.",
    "A stick was used to threaten the complainant.",
    "The accused brandished a weapon during the act.",
    "The accused carried no weapon.",
]
VEHICLE_PHRASES = [
    "The accused arrived in a car.",
    "The accused came on a motorcycle.",
    "An autorickshaw was used to flee the spot.",
    "The accused escaped on a bicycle.",
    "The accused arrived on a scooter.",
]
COUNT_PHRASES = [
    "Three persons were involved in the offence.",
    "Four accused persons were seen at the spot.",
    "Two men were reported to have committed the act.",
    "Five miscreants were involved.",
]

#: Multiple wordings per crime sub-head. Some deliberately omit the target or
#: the method — a real FIR often does.
BACKGROUND = {
    31: [  # murder / culpable homicide
        "A quarrel between the deceased and the accused escalated near {place}; "
        "the deceased succumbed to injuries.",
        "The accused assaulted the deceased following an altercation at {place}, "
        "causing fatal injuries.",
        "A dispute over money near {place} ended in a violent attack on the deceased.",
    ],
    32: [  # hurt / assault
        "The accused assaulted the complainant with hands and a stick near {place} "
        "following a property dispute.",
        "Following a quarrel at {place}, the accused attacked the complainant and "
        "caused injuries.",
        "The complainant was assaulted near {place} by known persons after an "
        "argument over parking.",
        "An altercation near {place} led to the accused attacking the complainant.",
    ],
    33: [  # kidnapping / missing
        "The complainant reported that her son was taken away by known persons "
        "from near {place}.",
        "The complainant states that his daughter was missing from {place} since "
        "the previous evening.",
        "Unknown persons took away a minor from near {place} without consent.",
    ],
    71: [  # robbery
        "Unknown persons waylaid the complainant near {place} and robbed cash "
        "under threat.",
        "The complainant was stopped near {place} by unknown persons who took his "
        "mobile phone by force.",
        "The accused threatened the complainant near {place} and robbed him of "
        "cash and a mobile phone.",
        "The complainant was surrounded near {place} and his valuables were taken "
        "by force.",
        "Unknown persons robbed the complainant of jewellery near {place} under "
        "threat.",
        "The complainant was waylaid near {place} and robbed of cash.",
    ],
    72: [  # theft
        "Unknown person stole the complainant's mobile phone from his pocket at "
        "{place}.",
        "Theft of a parked two-wheeler was reported from {place}.",
        "The complainant's vehicle was stolen from near {place}.",
        "Unknown persons committed theft of cash from a shop at {place}.",
        "The complainant reported theft of ornaments from her house near {place}.",
        "A mobile phone was stolen from the complainant while travelling by bus "
        "near {place}.",
        "Theft of property was reported from a godown at {place}.",
    ],
    73: [  # burglary / house-breaking
        "During the night, unknown persons broke open the lock of the house near "
        "{place} and committed theft of valuables.",
        "Unknown persons broke into a closed shop at {place} and committed theft "
        "of cash.",
        "The accused trespassed into the complainant's premises near {place} and "
        "committed burglary.",
        "The house of the complainant near {place} was broken into and jewellery "
        "was stolen.",
    ],
    111: [  # cheating / fraud
        "The accused collected money from the complainant promising a job and "
        "failed to return it.",
        "The complainant was cheated of cash by the accused who promised a land "
        "deal near {place}.",
        "The accused cheated the complainant by posing as a bank official and "
        "collected money.",
        "The complainant states that the accused failed to return the money taken "
        "for a business investment.",
    ],
    112: [  # public nuisance / obstruction
        "Nuisance was reported near {place}; the accused obstructed the public "
        "road.",
        "The accused created a disturbance at {place} and obstructed traffic.",
        "A group obstructed the public road near {place} causing inconvenience.",
    ],
}

ANOMALY_NARRATIVE = (
    "At around 4 AM, six accused persons arrived in two cars near the parking yard, "
    "threatened the security guard and drove away with a parked lorry (vehicle)."
)


def mo_narrative(rng: random.Random) -> str:
    """The planted chain-snatching MO — always carries its four signals."""
    template = rng.choice(MO_TEMPLATES)
    return template.format(
        place=rng.choice(PLACES),
        road=rng.choice(ROADS),
        time_phrase=rng.choice(TIME_PHRASES),
    ).strip()


def background_narrative(rng: random.Random, sub_head_id: int) -> str:
    """A varied background narrative, with some details present and some absent.

    Each optional clause is drawn independently, so the corpus contains
    narratives that state a weapon but no timing, timing but no vehicle, and so
    on — the mix a real FIR corpus has, and the reason extraction produces a
    spread of MO combinations rather than a handful.
    """
    options = BACKGROUND.get(sub_head_id, BACKGROUND[112])
    parts = [rng.choice(options).format(place=rng.choice(PLACES))]

    if rng.random() < 0.35:
        parts.append(rng.choice(TIME_PHRASES))
    if rng.random() < 0.22:
        parts.append(rng.choice(WEAPON_PHRASES))
    if rng.random() < 0.20:
        parts.append(rng.choice(VEHICLE_PHRASES))
    if rng.random() < 0.18:
        parts.append(rng.choice(COUNT_PHRASES))

    return " ".join(parts)
