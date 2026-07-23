"""SYNTHETIC DEMO DATA generator configuration (DATA-001/#14, ADR-011).

All values are deterministic inputs. Pattern parameters below ARE the
ground-truth design; the generator writes them to ground_truth.json for
validation suites. Engines never read this module or that file (enforced by
tests/conformance guard).
"""

from datetime import datetime

DEFAULT_SEED = 20260714
#: Fixed "now" anchor — determinism requires no wall-clock reads anywhere.
ANCHOR = datetime(2026, 7, 1, 0, 0, 0)
#: Multi-year history (~3 years) so seasonality and year-on-year growth are
#: visible. The planted hotspot/spike phases anchor to the recent window, so a
#: longer horizon only enriches the background — it never moves the answer key.
HISTORY_DAYS = 1095

STATE = (29, "Karnataka")

#: (DistrictID, name, [ (UnitID, station name, lat, lon) ... ])
#: The first four districts (and their original station ids/coords) are pinned —
#: the planted patterns reference Peenya (4430), Koramangala (4432) and
#: districts 44/12/20/9. Everything below them is added breadth for realism.
DISTRICTS = [
    (44, "Bengaluru City", [
        (4430, "Peenya PS", 13.0300, 77.5200),
        (4431, "Yeshwanthpur PS", 13.0230, 77.5500),
        (4432, "Koramangala PS", 12.9350, 77.6240),
        (4433, "Whitefield PS", 12.9700, 77.7500),
        (4434, "Jayanagar PS", 12.9250, 77.5830),
        (4435, "Indiranagar PS", 12.9720, 77.6410),
        (4436, "Electronic City PS", 12.8450, 77.6600),
        (4437, "Banashankari PS", 12.9250, 77.5460),
    ]),
    (12, "Tumakuru", [
        (1201, "Tumakuru Town PS", 13.3400, 77.1000),
        (1202, "Sira PS", 13.7400, 76.9040),
        (1203, "Tiptur PS", 13.2560, 76.4780),
    ]),
    (20, "Mysuru", [
        (2001, "Mysuru North PS", 12.3200, 76.6400),
        (2002, "Mysuru South PS", 12.2800, 76.6500),
        (2003, "Nazarbad PS", 12.3050, 76.6720),
    ]),
    (9, "Belagavi", [
        (901, "Belagavi City PS", 15.8500, 74.5000),
        (902, "Gokak PS", 16.1700, 74.8200),
    ]),
    (45, "Bengaluru Rural", [
        (4501, "Devanahalli PS", 13.2460, 77.7120),
        (4502, "Hoskote PS", 13.0700, 77.7980),
    ]),
    (21, "Mandya", [
        (2101, "Mandya Town PS", 12.5240, 76.8960),
        (2102, "Maddur PS", 12.5850, 77.0430),
    ]),
    (15, "Hassan", [
        (1501, "Hassan Town PS", 13.0050, 76.1000),
    ]),
    (8, "Ballari", [
        (801, "Ballari City PS", 15.1390, 76.9210),
        (802, "Hosapete PS", 15.2690, 76.3870),
    ]),
    (3, "Kalaburagi", [
        (301, "Kalaburagi City PS", 17.3290, 76.8340),
        (302, "Sedam PS", 17.1790, 77.2850),
    ]),
    (19, "Mangaluru", [
        (1901, "Mangaluru North PS", 12.8700, 74.8420),
        (1902, "Ullal PS", 12.8060, 74.8560),
    ]),
    (6, "Shivamogga", [
        (601, "Shivamogga Town PS", 13.9300, 75.5680),
    ]),
    (18, "Davanagere", [
        (1801, "Davanagere City PS", 14.4640, 75.9210),
    ]),
]

CRIME_HEADS = [
    (3, "Crimes Against Body"),
    (7, "Crimes Against Property"),
    (11, "Other IPC Crimes"),
    (13, "Crimes Against Women & Children"),
    (23, "Special & Local Laws"),
    (25, "Economic Offences"),
]
#: (id, head_id, name). The first eight are pinned — planted patterns reference
#: 71/72 and the MO action-agreement oracle only scores {32,71,72,73,111}. The
#: rest are added breadth so the corpus reads like a real FIR register rather
#: than three offence types; their narratives are unconstrained by that oracle.
CRIME_SUBHEADS = [
    (31, 3, "Murder"), (32, 3, "Assault"), (33, 3, "Kidnapping"),
    (71, 7, "Robbery"), (72, 7, "Theft"), (73, 7, "Burglary"),
    (111, 11, "Cheating"), (112, 11, "Public Nuisance"),
    # crimes against body
    (34, 3, "Attempt to Murder"), (35, 3, "Rioting"),
    (36, 3, "Grievous Hurt"), (37, 3, "Rash & Negligent Driving"),
    # crimes against property
    (74, 7, "Vehicle Theft"), (75, 7, "Criminal Trespass"),
    (76, 7, "Extortion"), (77, 7, "Mischief & Vandalism"),
    # other IPC
    (113, 11, "Criminal Intimidation"), (114, 11, "Forgery"),
    (115, 11, "Defamation"),
    # crimes against women & children
    (131, 13, "Outraging Modesty"), (132, 13, "Domestic Cruelty"),
    (133, 13, "Dowry Harassment"), (134, 13, "Offence Against Child"),
    # special & local laws
    (231, 23, "NDPS (Drugs)"), (232, 23, "Arms Act"),
    (233, 23, "Excise Act"), (234, 23, "Gambling Act"),
    # economic offences
    (251, 25, "Cyber Fraud"), (252, 25, "Counterfeiting"),
    (253, 25, "Criminal Breach of Trust"),
]
#: sub-head id -> plausible IPC/act sections (stored under Act "1"). Values must
#: be integer-parseable (ActSectionAssociation.SectionID is INT), so letter
#: suffixes like 304A/498A are recorded as their numeric stem.
SUBHEAD_SECTIONS = {
    31: ["302"], 32: ["323", "324"], 33: ["363"],
    71: ["392", "397"], 72: ["379"], 73: ["457", "380"],
    111: ["420"], 112: ["268"],
    34: ["307"], 35: ["147", "148"], 36: ["325", "326"], 37: ["279", "304"],
    74: ["379", "356"], 75: ["447"], 76: ["384", "386"], 77: ["427"],
    113: ["506"], 114: ["465", "468"], 115: ["500"],
    131: ["354"], 132: ["498"], 133: ["304"], 134: ["376"],
    231: ["20", "22"], 232: ["25"], 233: ["34"], 234: ["87"],
    251: ["66", "420"], 252: ["489"], 253: ["406", "409"],
}
CASE_CATEGORIES = [(1, "FIR"), (3, "UDR"), (4, "PAR"), (8, "Zero FIR")]
GRAVITY = [(1, "Heinous"), (2, "Non-Heinous")]
CASE_STATUSES = [(1, "Under Investigation"), (2, "Charge Sheeted"), (3, "Closed")]

#: Deliberately wide name pools. Larger pools cut incidental first+last
#: collisions (~an order of magnitude) so the planted identity fragment stays
#: the only strong cross-district merge and the same-name control stays split
#: (test_entity margins). Realism benefits too. "Ravi"/"Suresh"/"Kumar"/"Babu"
#: are kept because the planted phases spell those literals themselves.
FIRST_NAMES_M = ["Ravi", "Suresh", "Manju", "Kiran", "Prakash", "Naveen", "Santosh",
                 "Mahesh", "Girish", "Harish", "Lokesh", "Umesh", "Raghav", "Anil",
                 "Vijay", "Arjun", "Rahul", "Ganesh", "Basava", "Shivu", "Nagaraj",
                 "Chandru", "Vasanth", "Ramesh", "Dinesh", "Praveen", "Gopal",
                 "Madhu", "Srinivas", "Venkatesh", "Ashok", "Yogesh", "Sagar",
                 "Nithin", "Darshan", "Rakesh", "Pramod", "Sandeep", "Bharath",
                 "Vinay", "Karthik", "Abhishek", "Guru", "Mohan", "Ravindra"]
FIRST_NAMES_F = ["Lakshmi", "Manjula", "Asha", "Geetha", "Radha", "Sunitha", "Kavya",
                 "Deepa", "Shobha", "Rekha", "Pooja", "Divya", "Anitha", "Chaitra",
                 "Bhavya", "Sushma", "Nayana", "Roopa", "Vidya", "Meena", "Sowmya",
                 "Ramya", "Sneha", "Priya", "Bhoomika", "Nandini", "Jyothi",
                 "Sahana", "Varsha", "Ambika", "Latha", "Yashoda"]
LAST_NAMES = ["Kumar", "Gowda", "Reddy", "Shetty", "Naik", "Rao", "Babu", "Swamy",
              "Hegde", "Patil", "Murthy", "Shankar", "Nayak", "Bhat", "Kulkarni",
              "Desai", "Iyer", "Prasad", "Achar", "Rai", "Kamath", "Pai",
              "Jain", "Setty", "Gonal", "Angadi", "Hiremath", "Poojary",
              "Ballal", "Chandra", "Nagesh", "Bhandari", "Kotian", "Devar",
              "Halli", "Math", "Uppar", "Kadam", "Sajjan", "Biradar"]

#: data-quality design rates (documented; validated by tests)
MISSING_COORD_RATE = 0.04
MISSING_AGE_RATE = 0.08
DANGLING_COURT_CASES = 5  # deliberate dangling CourtID FKs for DQ reporting

# ---------------------------------------------------------------------------
# Background realism knobs (ADR-011). These shape the *background* only — the
# planted phases below never consult them, so the answer key is untouched. A
# longer, seasonal, geographically-varied background makes the recent-window
# planted signals stand out MORE, not less (density in any recent slice drops).
# ---------------------------------------------------------------------------

#: relative background case volume per district — Bengaluru City dominates so the
#: map centre and "leads volume" story stay in Bengaluru at any scale.
DISTRICT_VOLUME_WEIGHT = {
    44: 34, 45: 8, 12: 7, 20: 11, 9: 8, 21: 5,
    15: 5, 8: 6, 3: 6, 19: 8, 6: 5, 18: 5,
}

#: per-district offence mix — relative weights within a district. Deliberately
#: broad so the register reads like real life: metro skews cyber/property/traffic,
#: urban is balanced, rural skews burglary/assault/excise/land disputes. No
#: single offence dominates the way Theft used to.
CRIME_MIX_PROFILES = {
    "metro": {
        72: 9, 74: 5, 71: 4, 73: 3, 75: 2, 76: 1, 77: 3,        # property
        32: 4, 36: 2, 35: 2, 34: 1, 31: 1, 33: 1, 37: 5,        # body/traffic
        111: 5, 112: 3, 113: 3, 114: 2, 115: 1,                 # other IPC
        131: 3, 132: 3, 133: 1, 134: 1,                         # women & children
        231: 2, 232: 1, 234: 2,                                 # special laws
        251: 6, 252: 2, 253: 3,                                 # economic
    },
    "urban": {
        72: 10, 74: 4, 71: 3, 73: 5, 75: 3, 76: 1, 77: 3,
        32: 6, 36: 3, 35: 2, 34: 1, 31: 1, 33: 1, 37: 4,
        111: 4, 112: 4, 113: 3, 114: 1, 115: 1,
        131: 3, 132: 4, 133: 2, 134: 1,
        231: 2, 232: 1, 233: 2, 234: 2,
        251: 3, 252: 1, 253: 2,
    },
    "rural": {
        72: 6, 74: 2, 71: 2, 73: 8, 75: 4, 76: 1, 77: 3,
        32: 8, 36: 4, 35: 3, 34: 2, 31: 2, 33: 2, 37: 3,
        111: 3, 112: 3, 113: 4, 114: 1, 115: 1,
        131: 2, 132: 4, 133: 3, 134: 1,
        231: 2, 232: 2, 233: 4, 234: 3,
        251: 1, 253: 1,
    },
}
DISTRICT_PROFILE = {
    44: "metro", 45: "urban", 12: "urban", 20: "urban", 9: "urban", 21: "rural",
    15: "rural", 8: "rural", 3: "rural", 19: "urban", 6: "rural", 18: "urban",
}

#: mild monthly seasonality (Jan..Dec) — summer/festival upticks. Amplitude kept
#: low so no background station crosses the trends z-threshold.
SEASONAL_MONTH_WEIGHT = [0.90, 0.90, 1.00, 1.05, 1.10, 1.05,
                         1.00, 1.00, 1.05, 1.15, 1.10, 1.00]
#: day-of-week weight (Mon..Sun) — weekends slightly busier.
DOW_WEIGHT = [0.95, 0.95, 1.00, 1.00, 1.10, 1.20, 1.10]
#: gentle year-on-year growth so recent years are denser (recency trend).
GROWTH_PER_YEAR = 0.12

#: diurnal hour-of-day profiles (index 0..23), relative weights. Replaces the
#: crude night-only override with a smooth per-offence profile.
_HOURS_DAY = [1, 1, 1, 1, 1, 1, 2, 3, 5, 6, 6, 6,
              6, 6, 6, 5, 5, 4, 4, 3, 2, 2, 1, 1]
_HOURS_NIGHT = [6, 6, 5, 4, 2, 1, 1, 1, 1, 1, 1, 1,
                1, 1, 1, 1, 2, 3, 4, 5, 6, 6, 6, 6]
_HOURS_EVENING = [2, 1, 1, 1, 1, 1, 1, 2, 3, 3, 3, 3,
                  3, 3, 4, 4, 5, 6, 6, 6, 5, 4, 3, 2]
HOUR_PROFILES = {
    31: _HOURS_EVENING, 32: _HOURS_EVENING, 33: _HOURS_DAY, 71: _HOURS_NIGHT,
    72: _HOURS_DAY, 73: _HOURS_NIGHT, 111: _HOURS_DAY, 112: _HOURS_EVENING,
    34: _HOURS_EVENING, 35: _HOURS_DAY, 36: _HOURS_EVENING, 37: _HOURS_EVENING,
    74: _HOURS_NIGHT, 75: _HOURS_NIGHT, 76: _HOURS_EVENING, 77: _HOURS_NIGHT,
    113: _HOURS_EVENING, 114: _HOURS_DAY, 115: _HOURS_DAY,
    131: _HOURS_EVENING, 132: _HOURS_EVENING, 133: _HOURS_DAY, 134: _HOURS_DAY,
    231: _HOURS_NIGHT, 232: _HOURS_NIGHT, 233: _HOURS_NIGHT, 234: _HOURS_NIGHT,
    251: _HOURS_DAY, 252: _HOURS_DAY, 253: _HOURS_DAY,
}
HOUR_PROFILE_DEFAULT = _HOURS_DAY

# ---------------------------------------------------------------------------
# Embedded ground-truth patterns (ADR-011). Engines must DISCOVER these.
# ---------------------------------------------------------------------------

HOTSPOT = {
    "district_id": 44,
    "unit_id": 4430,  # Peenya PS
    "center_lat": 13.0310,
    "center_lon": 77.5185,
    "radius_m": 700,
    "hours": (21, 2),  # night window spanning midnight (cyclic-time test bed)
    "sub_head_id": 71,  # Robbery
    "case_count": 60,
    "recent_days": 90,
}

TREND_SPIKE = {
    # extra robbery volume at Peenya in the final 2 weeks vs its own baseline
    "unit_id": 4430,
    "sub_head_id": 71,
    "spike_days": 14,
    "spike_extra_cases": 22,  # on top of HOTSPOT recency
    "baseline_weekly_mean": 4,
}

MO_PATTERN = {
    # recurring chain-snatching MO expressed through BriefFacts narratives
    "cases_from_hotspot": 25,
    "offender_count": 2,
    "mobility": "motorcycle",
    "action": "snatching",
    "target": "gold_chain",
}

IDENTITY_FRAGMENT = {
    # one real person fragmented across districts (engines must candidate it)
    "variants": [
        ("Ravi Kumar", 29, 44),   # (name, age, district)
        ("Ravi K", 30, 12),
        ("Ravi Kumar S", 30, 20),
    ],
    "gender": "M",
}

SAME_NAME_CONTROL = {
    # two DIFFERENT people sharing a common name — must NOT strong-match
    "name": "Suresh Babu",
    "records": [(24, 44), (52, 9)],  # (age, district)
    "gender": "M",
}

ANOMALY_CASE = {
    # behaviorally deviant robbery: pre-dawn, 6 accused, vehicle target
    "unit_id": 4432,
    "sub_head_id": 71,
    "hour": 4,
    "accused_count": 6,
    "target": "vehicle",
}
