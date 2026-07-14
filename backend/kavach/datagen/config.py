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
HISTORY_DAYS = 365

STATE = (29, "Karnataka")

#: (DistrictID, name, [ (UnitID, station name, lat, lon) ... ])
DISTRICTS = [
    (44, "Bengaluru City", [
        (4430, "Peenya PS", 13.0300, 77.5200),
        (4431, "Yeshwanthpur PS", 13.0230, 77.5500),
        (4432, "Koramangala PS", 12.9350, 77.6240),
        (4433, "Whitefield PS", 12.9700, 77.7500),
    ]),
    (12, "Tumakuru", [
        (1201, "Tumakuru Town PS", 13.3400, 77.1000),
        (1202, "Sira PS", 13.7400, 76.9040),
    ]),
    (20, "Mysuru", [
        (2001, "Mysuru North PS", 12.3200, 76.6400),
        (2002, "Mysuru South PS", 12.2800, 76.6500),
    ]),
    (9, "Belagavi", [
        (901, "Belagavi City PS", 15.8500, 74.5000),
        (902, "Gokak PS", 16.1700, 74.8200),
    ]),
]

CRIME_HEADS = [
    (3, "Crimes Against Body"),
    (7, "Crimes Against Property"),
    (11, "Other IPC Crimes"),
]
CRIME_SUBHEADS = [  # (id, head_id, name)
    (31, 3, "Murder"), (32, 3, "Assault"), (33, 3, "Kidnapping"),
    (71, 7, "Robbery"), (72, 7, "Theft"), (73, 7, "Burglary"),
    (111, 11, "Cheating"), (112, 11, "Public Nuisance"),
]
#: sub-head id -> plausible IPC-like sections (Act "1")
SUBHEAD_SECTIONS = {
    31: ["302"], 32: ["323", "324"], 33: ["363"],
    71: ["392", "397"], 72: ["379"], 73: ["457", "380"],
    111: ["420"], 112: ["268"],
}
CASE_CATEGORIES = [(1, "FIR"), (3, "UDR"), (4, "PAR"), (8, "Zero FIR")]
GRAVITY = [(1, "Heinous"), (2, "Non-Heinous")]
CASE_STATUSES = [(1, "Under Investigation"), (2, "Charge Sheeted"), (3, "Closed")]

FIRST_NAMES_M = ["Ravi", "Suresh", "Manju", "Kiran", "Prakash", "Naveen", "Santosh",
                 "Mahesh", "Girish", "Harish", "Lokesh", "Umesh", "Raghav", "Anil"]
FIRST_NAMES_F = ["Lakshmi", "Manjula", "Asha", "Geetha", "Radha", "Sunitha", "Kavya",
                 "Deepa", "Shobha", "Rekha"]
LAST_NAMES = ["Kumar", "Gowda", "Reddy", "Shetty", "Naik", "Rao", "Babu", "Swamy",
              "Hegde", "Patil", "Murthy", "Shankar"]

#: data-quality design rates (documented; validated by tests)
MISSING_COORD_RATE = 0.04
MISSING_AGE_RATE = 0.08
DANGLING_COURT_CASES = 5  # deliberate dangling CourtID FKs for DQ reporting

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
