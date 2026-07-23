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
          "the flyover service lane", "a bank entrance", "the metro station",
          "a wine shop", "the apartment gate", "a construction site",
          "the government hospital", "a shopping mall", "the lake bund",
          "a private layout", "the auto stand", "a wedding hall",
          "the college campus", "a farmland boundary", "the highway toll",
          "a cinema hall", "the fish market", "a lodge", "the panchayat office",
          "a mobile showroom", "the tea stall", "an under-construction building"]
ROADS = ["Tumakuru Road", "Magadi Road", "the ring road", "the service road", "NH-48",
         "Kanakapura Road", "the bypass road", "Old Airport Road", "Hosur Road",
         "Bannerghatta Road", "Mysuru Road", "Sarjapur Road", "the outer ring road",
         "Ballari Road", "Kolar Road", "the village main road", "NH-75",
         "the market bylane", "the arterial road", "Whitefield Main Road"]

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
#: the method — a real FIR often does. For the five sub-heads scored by the MO
#: action-agreement oracle (32/71/72/73/111) every wording states the offence's
#: own action verb and avoids a higher-precedence verb, so extraction agrees.
BACKGROUND = {
    31: [  # murder / culpable homicide
        "A quarrel between the deceased and the accused escalated near {place}; "
        "the deceased succumbed to injuries.",
        "The accused assaulted the deceased following an altercation at {place}, "
        "causing fatal injuries.",
        "A dispute over money near {place} ended in a violent attack on the deceased.",
        "The body of the deceased was found near {place} with grievous injuries; "
        "the family suspects foul play by known persons.",
        "Following a long-standing enmity, the accused fatally attacked the "
        "deceased near {place}.",
    ],
    32: [  # hurt / assault
        "The accused assaulted the complainant with hands and a stick near {place} "
        "following a property dispute.",
        "Following a quarrel at {place}, the accused attacked the complainant and "
        "caused injuries.",
        "The complainant was assaulted near {place} by known persons after an "
        "argument over parking.",
        "An altercation near {place} led to the accused attacking the complainant.",
        "Over an old money dispute, the accused assaulted the complainant near "
        "{place} and caused hurt.",
        "The complainant was attacked with bare hands near {place} during a heated "
        "exchange with neighbours.",
    ],
    33: [  # kidnapping / missing
        "The complainant reported that her son was taken away by known persons "
        "from near {place}.",
        "The complainant states that his daughter was missing from {place} since "
        "the previous evening.",
        "Unknown persons took away a minor from near {place} without consent.",
        "The complainant alleges his sister was lured away from {place} on a false "
        "pretext and has not returned.",
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
        "A delivery agent was intercepted near {place} and robbed of the cash he "
        "was carrying.",
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
        "The complainant's cycle was stolen from outside {place}.",
        "Unknown persons stole electrical cables from a site near {place}.",
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
        "Unknown persons broke open the shutter of a locked showroom near {place} "
        "at night and committed theft.",
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
        "The accused cheated the complainant with a fake gold-loan scheme and "
        "collected an advance.",
    ],
    112: [  # public nuisance / obstruction
        "Nuisance was reported near {place}; the accused obstructed the public "
        "road.",
        "The accused created a disturbance at {place} and obstructed traffic.",
        "A group obstructed the public road near {place} causing inconvenience.",
        "The accused caused a public nuisance near {place} by playing loud music "
        "late into the night.",
    ],
    # ---- added offence types (unconstrained by the MO oracle) --------------
    34: [  # attempt to murder
        "The accused attacked the complainant with a lethal weapon near {place} "
        "with intent to kill; the complainant survived with grievous injuries.",
        "During an enmity dispute near {place}, the accused stabbed the complainant "
        "who is battling for life in hospital.",
    ],
    35: [  # rioting
        "A group armed with sticks gathered near {place} and indulged in rioting, "
        "damaging property.",
        "Two factions clashed near {place}; an unlawful assembly pelted stones and "
        "disturbed public peace.",
    ],
    36: [  # grievous hurt
        "The accused assaulted the complainant with an iron rod near {place}, "
        "causing a fracture.",
        "In a dispute over a boundary near {place}, the accused caused grievous "
        "injuries to the complainant.",
    ],
    37: [  # rash & negligent driving
        "A speeding vehicle driven rashly near {place} knocked down the "
        "complainant, causing injuries.",
        "The accused drove a lorry in a rash and negligent manner near {place} and "
        "hit a two-wheeler.",
    ],
    74: [  # vehicle theft
        "The complainant's motorcycle parked near {place} was stolen by unknown "
        "persons.",
        "A car parked outside {place} was stolen overnight; theft was noticed in "
        "the morning.",
        "Unknown persons stole a parked scooter from near {place}.",
    ],
    75: [  # criminal trespass
        "The accused trespassed into the complainant's site near {place} and "
        "refused to leave despite objection.",
        "Unknown persons unlawfully entered the complainant's fenced land near "
        "{place} and put up a temporary shed.",
    ],
    76: [  # extortion
        "The accused threatened the complainant near {place} and demanded money to "
        "avoid harm.",
        "The complainant received threatening calls demanding a large sum, failing "
        "which harm was threatened near {place}.",
    ],
    77: [  # mischief / vandalism
        "Unknown persons damaged the complainant's parked vehicle near {place} out "
        "of enmity.",
        "The accused pelted stones and damaged the shopfront near {place}, causing "
        "loss.",
    ],
    113: [  # criminal intimidation
        "The accused threatened the complainant with dire consequences near "
        "{place} over a civil dispute.",
        "The complainant was intimidated by the accused near {place} and warned "
        "against filing a complaint.",
    ],
    114: [  # forgery
        "The accused fabricated documents to transfer the complainant's property "
        "near {place} and used them as genuine.",
        "The complainant alleges the accused forged his signature on a cheque "
        "presented near {place}.",
    ],
    115: [  # defamation
        "The accused circulated defamatory messages about the complainant, harming "
        "his reputation in the {place} area.",
        "The complainant alleges the accused made false and defamatory statements "
        "in public near {place}.",
    ],
    131: [  # outraging modesty
        "The accused outraged the modesty of the complainant near {place} and fled "
        "when she raised an alarm.",
        "The complainant was harassed and touched inappropriately by the accused "
        "near {place}.",
    ],
    132: [  # domestic cruelty
        "The complainant states that her husband and in-laws subjected her to "
        "cruelty and harassment at the matrimonial home near {place}.",
        "The complainant alleges continued mental and physical harassment by "
        "family members over a domestic dispute.",
    ],
    133: [  # dowry harassment
        "The complainant alleges harassment by the accused for additional dowry "
        "since her marriage.",
        "The complainant states she was subjected to cruelty for non-fulfilment of "
        "dowry demands near {place}.",
    ],
    134: [  # offence against child
        "The complainant reported an offence against a minor child near {place}; "
        "the matter is being handled with due care.",
        "An incident endangering the safety of a child near {place} was reported by "
        "the guardian.",
    ],
    231: [  # NDPS (drugs)
        "The accused was found in possession of a quantity of contraband near "
        "{place} during a routine check.",
        "A tip-off led to the seizure of narcotic substances from the accused near "
        "{place}.",
    ],
    232: [  # arms act
        "The accused was found carrying an unlicensed firearm near {place} without "
        "authority.",
        "An illegal weapon was seized from the accused during a check near {place}.",
    ],
    233: [  # excise act
        "The accused was found transporting illicit liquor near {place} in "
        "contravention of the Excise Act.",
        "Illicitly distilled liquor was seized from a shed near {place}.",
    ],
    234: [  # gambling act
        "A group was found gambling for stakes in a public place near {place}; "
        "cards and cash were seized.",
        "The accused organised betting near {place}; gambling material was seized.",
    ],
    251: [  # cyber fraud
        "The complainant was cheated of a large sum through a fraudulent online "
        "investment link.",
        "An unknown caller posing as a bank officer obtained the complainant's OTP "
        "and cheated him of money.",
        "The complainant was defrauded through a fake customer-care number in an "
        "online scam.",
    ],
    252: [  # counterfeiting
        "The accused was found in possession of counterfeit currency notes near "
        "{place}.",
        "Fake branded goods were seized from the accused's shop near {place}.",
    ],
    253: [  # criminal breach of trust
        "The accused, entrusted with the complainant's funds, dishonestly "
        "misappropriated them.",
        "The complainant alleges the accused, an employee, misappropriated cash "
        "entrusted to him for deposit.",
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
