"""SYNTHETIC dataset orchestrator (DATA-001/#14, ADR-011).

Deterministic for a fixed seed: single random.Random instance, fixed time
anchor (config.ANCHOR), no wall-clock/os.urandom anywhere. Output: one CSV per
source table with exact documented columns + ground_truth.json + marker file.
"""

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from random import Random

from kavach.datagen import config as cfg
from kavach.datagen import narratives
from kavach.datagen.lookups import build_lookups

_SUBHEAD_TO_HEAD = {s: h for s, h, _ in cfg.CRIME_SUBHEADS}
#: gravity=Heinous sub-heads (cosmetic GravityOffenceID; not an oracle input).
_HEINOUS_SUBHEADS = {31, 33, 34, 36, 71, 76, 131, 133, 134, 231}


def _offset_coords(rng: Random, lat: float, lon: float, max_m: float) -> tuple[float, float]:
    """Uniform point within max_m metres of (lat, lon)."""
    r = max_m * math.sqrt(rng.random())
    theta = rng.random() * 2 * math.pi
    dlat = (r * math.cos(theta)) / 111_320
    dlon = (r * math.sin(theta)) / (111_320 * math.cos(math.radians(lat)))
    return round(lat + dlat, 6), round(lon + dlon, 6)


def _person_name(rng: Random, gender: str) -> str:
    first = rng.choice(cfg.FIRST_NAMES_F if gender == "F" else cfg.FIRST_NAMES_M)
    return f"{first} {rng.choice(cfg.LAST_NAMES)}"


class DatasetGenerator:
    def __init__(self, seed: int = cfg.DEFAULT_SEED, background_cases: int = 2000):
        self.rng = Random(seed)
        self.seed = seed
        self.background_cases = background_cases
        self.tables, self.ctx = build_lookups(self.rng)
        for name in ("CaseMaster", "ComplainantDetails", "Victim", "Accused",
                     "ActSectionAssociation", "ArrestSurrender", "ChargesheetDetails"):
            self.tables[name] = []
        self._ids = {"case": 5000, "complainant": 1, "victim": 1, "accused": 1,
                     "arrest": 1, "cs": 1}
        self._serials: dict[tuple[int, int, int], int] = {}
        self.ground_truth: dict = {"seed": seed, "language": "en",
                                   "note": "SYNTHETIC DEMO DATA (ADR-011)"}

    # -- id/number helpers -------------------------------------------------
    def _next(self, kind: str) -> int:
        self._ids[kind] += 1
        return self._ids[kind]

    def _crime_no(self, category: int, district: int, unit: int, year: int) -> tuple[str, str]:
        key = (unit, category, year)
        self._serials[key] = self._serials.get(key, 0) + 1
        serial = self._serials[key]
        crime_no = f"{category}{district:04d}{unit:04d}{year:04d}{serial:05d}"
        return crime_no, crime_no[-9:]

    # -- core case factory ---------------------------------------------------
    def _add_case(self, unit_id: int, sub_head_id: int, occurred: datetime, *,
                  coords: tuple[float, float] | None = "auto", brief: str | None = None,
                  accused_specs: list[tuple[str, int | None, str]] | None = None,
                  category: int = 1, court_id: int | None = "auto") -> int:
        rng = self.rng
        case_id = self._next("case")
        district_id = self.ctx["district_of_unit"][unit_id]
        if coords == "auto":
            base = self.ctx["station_coords"][unit_id]
            coords = (None, None) if rng.random() < cfg.MISSING_COORD_RATE \
                else _offset_coords(rng, *base, 3000)
        lat, lon = coords if coords else (None, None)
        registered = occurred + timedelta(hours=rng.randint(2, 30))
        crime_no, case_no = self._crime_no(category, district_id, unit_id, registered.year)
        if court_id == "auto":
            court_id = self.ctx["court_by_district"][district_id]
        status = rng.choices([1, 2, 3], weights=[6, 2, 2])[0]
        emp = self.ctx["emp_by_unit"][unit_id][0]
        self.tables["CaseMaster"].append({
            "CaseMasterID": case_id, "CrimeNo": crime_no, "CaseNo": case_no,
            "CrimeRegisteredDate": registered.date().isoformat(),
            "PolicePersonID": emp, "PoliceStationID": unit_id,
            "CaseCategoryID": category,
            "GravityOffenceID": 1 if sub_head_id in _HEINOUS_SUBHEADS else 2,
            "CrimeMajorHeadID": _SUBHEAD_TO_HEAD[sub_head_id],
            "CrimeMinorHeadID": sub_head_id, "CaseStatusID": status,
            "CourtID": court_id,
            "IncidentFromDate": occurred.isoformat(sep=" "),
            "IncidentToDate": (occurred + timedelta(minutes=rng.randint(5, 90))
                               ).isoformat(sep=" "),
            "InfoReceivedPSDate": registered.isoformat(sep=" "),
            "latitude": lat, "longitude": lon,
            "BriefFacts": brief or narratives.background_narrative(rng, sub_head_id),
        })
        self._add_children(case_id, unit_id, district_id, sub_head_id, occurred,
                           status, accused_specs)
        return case_id

    def _add_children(self, case_id, unit_id, district_id, sub_head_id, occurred,
                      status, accused_specs) -> None:
        rng = self.rng
        # complainant (1 per case)
        g = rng.choice(["M", "F"])
        self.tables["ComplainantDetails"].append({
            "ComplainantID": self._next("complainant"), "CaseMasterID": case_id,
            "ComplainantName": _person_name(rng, g),
            "AgeYear": None if rng.random() < cfg.MISSING_AGE_RATE else rng.randint(18, 75),
            "OccupationID": rng.randint(1, 8), "ReligionID": rng.randint(1, 4),
            "CasteID": rng.randint(1, 6), "GenderID": g,
        })
        # victims (0-2)
        for _ in range(rng.choices([0, 1, 2], weights=[3, 6, 1])[0]):
            vg = rng.choice(["M", "F", "m", "f"])  # mixed-case codes on purpose
            self.tables["Victim"].append({
                "VictimMasterID": self._next("victim"), "CaseMasterID": case_id,
                "VictimName": _person_name(rng, vg.upper()),
                "AgeYear": None if rng.random() < cfg.MISSING_AGE_RATE
                else rng.randint(10, 80),
                "GenderID": vg, "VictimPolice": "0" if rng.random() > 0.02 else "1",
            })
        # accused
        if accused_specs is None:
            n = rng.choices([0, 1, 2, 3], weights=[4, 4, 2, 1])[0]
            accused_specs = [(_person_name(rng, "M"), rng.randint(18, 60), "M")
                             for _ in range(n)]
        accused_ids = []
        for i, (name, age, gender) in enumerate(accused_specs, 1):
            aid = self._next("accused")
            accused_ids.append(aid)
            self.tables["Accused"].append({
                "AccusedMasterID": aid, "CaseMasterID": case_id, "AccusedName": name,
                "AgeYear": age, "GenderID": gender, "PersonID": f"A{i}",
            })
        # act/section associations
        for j, sec in enumerate(cfg.SUBHEAD_SECTIONS[sub_head_id], 1):
            self.tables["ActSectionAssociation"].append({
                "CaseMasterID": case_id, "ActID": 1, "SectionID": int(sec),
                "ActOrderID": 1, "SectionOrderID": j,
            })
        # arrests (~40% of accused) + chargesheet for closed/chargesheeted cases
        io = self.ctx["emp_by_unit"][unit_id][1]
        for aid in accused_ids:
            if rng.random() < 0.4:
                self.tables["ArrestSurrender"].append({
                    "ArrestSurrenderID": self._next("arrest"), "CaseMasterID": case_id,
                    "ArrestSurrenderTypeID": rng.choices([1, 2], weights=[8, 2])[0],
                    "ArrestSurrenderDate": (occurred + timedelta(
                        days=rng.randint(1, 60))).date().isoformat(),
                    "ArrestSurrenderStateId": cfg.STATE[0],
                    "ArrestSurrenderDistrictId": district_id,
                    "PoliceStationID": unit_id, "IOID": io,
                    "CourtID": self.ctx["court_by_district"][district_id],
                    "AccusedMasterID": aid, "IsAccused": 1, "IsComplainantAccused": 0,
                })
        if status in (2, 3) and accused_ids:
            self.tables["ChargesheetDetails"].append({
                "CSID": self._next("cs"), "CaseMasterID": case_id,
                "csdate": (occurred + timedelta(days=rng.randint(30, 120))
                           ).isoformat(sep=" "),
                "cstype": rng.choices(["A", "B", "C"], weights=[7, 1, 2])[0],
                "PolicePersonID": io,
            })

    # -- pattern + background generation -------------------------------------
    def generate(self) -> None:
        self._gen_peenya_robbery_with_hotspot_and_spike()
        self._gen_background()
        self._gen_identity_fragment()
        self._gen_same_name_control()
        self._gen_anomaly_case()
        self._apply_dangling_courts()
        self._finalize_ground_truth()

    def _gen_peenya_robbery_with_hotspot_and_spike(self) -> None:
        rng, h, sp = self.rng, cfg.HOTSPOT, cfg.TREND_SPIKE
        unit = h["unit_id"]
        end = cfg.ANCHOR
        weeks = cfg.HISTORY_DAYS // 7  # baseline spans the whole history span
        occurrences: list[datetime] = []
        for week in range(weeks):  # baseline 4/week across the history
            wk_start = end - timedelta(days=(weeks - week) * 7)
            for _ in range(sp["baseline_weekly_mean"]):
                occurrences.append(wk_start + timedelta(
                    minutes=rng.randint(0, 7 * 24 * 60 - 1)))
        for _ in range(sp["spike_extra_cases"]):  # spike in final 14 days
            occurrences.append(end - timedelta(
                minutes=rng.randint(0, sp["spike_days"] * 24 * 60 - 1)))
        occurrences.sort()

        recent_cutoff = end - timedelta(days=h["recent_days"])
        recent = [o for o in occurrences if o >= recent_cutoff]
        cluster_times = set(recent[: h["case_count"]])
        cluster_ids, mo_ids, spike_ids = [], [], []
        for occ in occurrences:
            in_cluster = occ in cluster_times
            if in_cluster:
                start_h, end_h = h["hours"]  # night window spanning midnight
                hour = rng.choice(list(range(start_h, 24)) + list(range(0, end_h + 1)))
                occ = occ.replace(hour=hour, minute=rng.randint(0, 59))
                coords = _offset_coords(rng, h["center_lat"], h["center_lon"],
                                        h["radius_m"])
                brief = (narratives.mo_narrative(rng)
                         if len(mo_ids) < cfg.MO_PATTERN["cases_from_hotspot"] else None)
            else:
                coords, brief = "auto", None
            cid = self._add_case(unit, h["sub_head_id"], occ, coords=coords, brief=brief)
            if in_cluster:
                cluster_ids.append(cid)
                if brief:
                    mo_ids.append(cid)
            if occ >= end - timedelta(days=sp["spike_days"]):
                spike_ids.append(cid)
        self.ground_truth["hotspot"] = {**h, "hours": list(h["hours"]),
                                        "case_ids": cluster_ids}
        self.ground_truth["mo_pattern"] = {**cfg.MO_PATTERN, "case_ids": mo_ids}
        self.ground_truth["trend_spike"] = {
            **sp, "window_from": (end - timedelta(days=sp["spike_days"])).isoformat(),
            "window_to": end.isoformat(), "case_ids": spike_ids,
        }

    def _gen_background(self) -> None:
        """Background FIRs with geographic, seasonal and diurnal structure.

        A case is drawn as district (by volume) -> station -> offence (by that
        district's mix) -> a date weighted by month/day-of-week/recency and an
        hour weighted by the offence's diurnal profile. All draws are off the
        single seeded rng, so output stays byte-identical per seed.
        """
        rng = self.rng
        stations_by_district: dict[int, list[int]] = {}
        for u, d, _, _ in self.ctx["stations"]:
            if u == cfg.HOTSPOT["unit_id"]:  # planted hotspot owns its own phase
                continue
            stations_by_district.setdefault(d, []).append(u)
        districts = list(stations_by_district)
        dist_weights = [cfg.DISTRICT_VOLUME_WEIGHT.get(d, 5) for d in districts]
        day_offsets, day_weights = self._background_day_weights()

        for _ in range(self.background_cases):
            d = rng.choices(districts, weights=dist_weights)[0]
            unit_id = rng.choice(stations_by_district[d])
            mix = cfg.CRIME_MIX_PROFILES[cfg.DISTRICT_PROFILE.get(d, "urban")]
            sub = rng.choices(list(mix), weights=list(mix.values()))[0]
            occ = self._draw_background_datetime(sub, day_offsets, day_weights)
            self._add_case(unit_id, sub, occ)

    def _background_day_weights(self) -> tuple[list[int], list[float]]:
        """Per-day sampling weights over the history: seasonality x day-of-week
        x gentle year-on-year growth. Uses only the fixed ANCHOR calendar (no
        wall-clock), so it is deterministic."""
        offsets = list(range(1, cfg.HISTORY_DAYS + 1))  # >=1 day => always < ANCHOR
        weights = []
        for off in offsets:
            day = cfg.ANCHOR - timedelta(days=off)
            w = cfg.SEASONAL_MONTH_WEIGHT[day.month - 1]
            w *= cfg.DOW_WEIGHT[day.weekday()]
            w *= (1 + cfg.GROWTH_PER_YEAR) ** ((cfg.HISTORY_DAYS - off) / 365.0)
            weights.append(w)
        return offsets, weights

    def _draw_background_datetime(self, sub_head_id: int, day_offsets: list[int],
                                  day_weights: list[float]) -> datetime:
        rng = self.rng
        off = rng.choices(day_offsets, weights=day_weights)[0]
        profile = cfg.HOUR_PROFILES.get(sub_head_id, cfg.HOUR_PROFILE_DEFAULT)
        hour = rng.choices(range(24), weights=profile)[0]
        return (cfg.ANCHOR - timedelta(days=off)).replace(
            hour=hour, minute=rng.randint(0, 59))

    def _gen_identity_fragment(self) -> None:
        rng, frag = self.rng, cfg.IDENTITY_FRAGMENT
        ids = []
        for i, (name, age, district) in enumerate(frag["variants"]):
            unit = next(u for u, d, _, _ in self.ctx["stations"] if d == district)
            occ = cfg.ANCHOR - timedelta(days=200 - i * 70, hours=rng.randint(0, 23))
            cid = self._add_case(unit, 71, occ, brief=narratives.mo_narrative(rng),
                                 accused_specs=[(name, age, frag["gender"])])
            ids.append({"case_id": cid, "accused_master_id": self._ids["accused"],
                        "name": name, "age": age, "district_id": district})
        self.ground_truth["identity_fragment"] = {"gender": frag["gender"], "records": ids}

    def _gen_same_name_control(self) -> None:
        rng, ctl = self.rng, cfg.SAME_NAME_CONTROL
        ids = []
        for age, district in ctl["records"]:
            unit = next(u for u, d, _, _ in self.ctx["stations"] if d == district)
            occ = cfg.ANCHOR - timedelta(days=rng.randint(30, 300))
            cid = self._add_case(unit, 72, occ,
                                 accused_specs=[(ctl["name"], age, ctl["gender"])])
            ids.append({"case_id": cid, "accused_master_id": self._ids["accused"],
                        "age": age, "district_id": district})
        self.ground_truth["same_name_control"] = {"name": ctl["name"], "records": ids}

    def _gen_anomaly_case(self) -> None:
        a = cfg.ANOMALY_CASE
        occ = (cfg.ANCHOR - timedelta(days=20)).replace(hour=a["hour"], minute=10)
        specs = [(_person_name(self.rng, "M"), self.rng.randint(20, 45), "M")
                 for _ in range(a["accused_count"])]
        cid = self._add_case(a["unit_id"], a["sub_head_id"], occ,
                             brief=narratives.ANOMALY_NARRATIVE, accused_specs=specs)
        self.ground_truth["anomaly_case"] = {**a, "case_id": cid}

    def _apply_dangling_courts(self) -> None:
        """Deliberate dangling FKs to exercise data-quality reporting."""
        cases = self.tables["CaseMaster"]
        step = max(1, len(cases) // cfg.DANGLING_COURT_CASES)
        dangling = []
        for row in cases[::step][: cfg.DANGLING_COURT_CASES]:
            row["CourtID"] = 9999
            dangling.append(row["CaseMasterID"])
        self.ground_truth["dangling_court_case_ids"] = dangling

    def _finalize_ground_truth(self) -> None:
        cases = self.tables["CaseMaster"]
        n = len(cases)
        missing_coords = sum(1 for c in cases if c["latitude"] is None)
        self.ground_truth["data_quality"] = {
            "total_cases": n,
            "missing_coordinate_cases": missing_coords,
            "designed_missing_coord_rate": cfg.MISSING_COORD_RATE,
            "dangling_court_cases": cfg.DANGLING_COURT_CASES,
        }

    # -- output ---------------------------------------------------------------
    def write(self, out_dir: str | Path, manifest_path: str | Path) -> None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        manifest = json.loads(Path(manifest_path).read_text())
        for table, spec in manifest.items():
            if table.startswith("_"):
                continue
            cols = spec["columns"]
            rows = self.tables.get(table, [])
            with (out / f"{table}.csv").open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in rows:
                    w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
        (out / "ground_truth.json").write_text(
            json.dumps(self.ground_truth, indent=2, default=str) + "\n")
        (out / "_SYNTHETIC_DATA_MARKER.txt").write_text(
            "SYNTHETIC DEMO DATA — generated by kavach.datagen (seed "
            f"{self.seed}); not real crime records. See ADR-011.\n")


def generate_dataset(out_dir: str | Path, manifest_path: str | Path,
                     seed: int = cfg.DEFAULT_SEED, background_cases: int = 2000
                     ) -> DatasetGenerator:
    gen = DatasetGenerator(seed=seed, background_cases=background_cases)
    gen.generate()
    gen.write(out_dir, manifest_path)
    return gen
