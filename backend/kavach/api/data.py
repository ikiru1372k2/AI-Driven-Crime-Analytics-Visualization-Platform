"""Synthetic-data access for the analytics API (CSV or Catalyst Data Store).

Reads each source table into a string-typed pandas DataFrame, joins human-readable
lookup names, and caches the result. The row *source* is chosen at runtime by
``KAVACH_DATA_SOURCE``: ``"csv"`` (bundled synthetic CSVs from ``data/synthetic``,
the prod-safe default) or ``"datastore"`` (live Catalyst Data Store, so edits made
in the Zoho console show up in the app). Both sources yield the *same* column
shape and string cells, so nothing below ``_read`` — nor any API/analytics
consumer — changes when the flag flips.

All data is SYNTHETIC (ADR-011). Nothing here reads the generator's answer key.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from kavach.api.ttl_cache import timed_cache
from kavach.config import settings

#: repo root = backend/kavach/api/data.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    """Directory holding the generated CSVs (override with KAVACH_DATA_DIR)."""
    return Path(os.environ.get("KAVACH_DATA_DIR", _REPO_ROOT / "data" / "synthetic"))


def _use_datastore() -> bool:
    """True when the live Catalyst Data Store is the configured source."""
    return settings.data_source.strip().lower() == "datastore"


def _cache_ttl() -> float:
    """Cache lifetime for the joined frames: forever for static CSVs, else TTL.

    CSV data is static for a run, so it caches for the process lifetime (as
    before). Data Store rows can change under us, so the joined result expires
    after the configured TTL and is rebuilt, picking up console edits.
    """
    return settings.datastore_cache_ttl if _use_datastore() else float("inf")


def _read(name: str) -> pd.DataFrame:
    """Read one source table as strings ("" for blanks), from the active source.

    Resolution order (PERF-001): the in-memory **snapshot** first (published by
    ``warmer.py`` off the request path), so no request ever blocks on a cold
    whole-dataset read; then the live Data Store; then the bundled CSV. All three
    yield the same columns and string cells, so callers are source-agnostic.
    """
    from kavach.api import snapshot  # leaf module, no cycle

    if snapshot.has_table(name):
        return snapshot.get_table(name)
    if _use_datastore():
        from kavach.api import datastore  # lazy: CSV mode never imports it

        return datastore.read_table(name)
    path = data_dir() / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - generate the dataset first: "
            "PYTHONPATH=backend backend/.venv/Scripts/python.exe scripts/generate_dataset.py"
        )
    return pd.read_csv(path, dtype=str, keep_default_na=False)


@timed_cache(_cache_ttl)
def enriched_cases() -> pd.DataFrame:
    """CaseMaster joined with its lookup names, one row per FIR.

    Adds: subhead_name, head_id/head_name, category, gravity, status,
    station_name, district_id/district_name, plus typed lat/lon and dates.
    Cached until the TTL (forever for static CSVs; briefly for the live Data
    Store so console edits appear).
    """
    cases = _read("CaseMaster")
    subheads = _read("CrimeSubHead")[["CrimeSubHeadID", "CrimeHeadID", "CrimeHeadName"]]
    heads = _read("CrimeHead")[["CrimeHeadID", "CrimeGroupName"]]
    units = _read("Unit")[["UnitID", "UnitName", "DistrictID"]]
    districts = _read("District")[["DistrictID", "DistrictName"]]
    categories = _read("CaseCategory")[["CaseCategoryID", "LookupValue"]]
    gravity = _read("GravityOffence")[["GravityOffenceID", "LookupValue"]]
    statuses = _read("CaseStatusMaster")[["CaseStatusID", "CaseStatusName"]]

    df = cases.merge(
        subheads, left_on="CrimeMinorHeadID", right_on="CrimeSubHeadID", how="left"
    ).merge(heads, on="CrimeHeadID", how="left")

    df = df.merge(units, left_on="PoliceStationID", right_on="UnitID", how="left")
    df = df.merge(districts, on="DistrictID", how="left")
    df = df.merge(
        categories, left_on="CaseCategoryID", right_on="CaseCategoryID", how="left"
    )
    df = df.merge(
        gravity, left_on="GravityOffenceID", right_on="GravityOffenceID",
        how="left", suffixes=("", "_grav"),
    )
    df = df.merge(statuses, left_on="CaseStatusID", right_on="CaseStatusID", how="left")

    # typed / renamed convenience columns
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["registered_date"] = pd.to_datetime(df["CrimeRegisteredDate"], errors="coerce")
    df["incident_from"] = pd.to_datetime(df["IncidentFromDate"], errors="coerce")
    df = df.rename(
        columns={
            "CrimeHeadName": "subhead_name",
            "CrimeHeadID": "head_id",
            "CrimeGroupName": "head_name",
            "UnitName": "station_name",
            "DistrictName": "district_name",
            "LookupValue": "category",
            "LookupValue_grav": "gravity",
            "CaseStatusName": "status",
            "CrimeMinorHeadID": "subhead_id",
            "PoliceStationID": "station_id",
            "DistrictID": "district_id",
        }
    )
    return df


#: fields returned to the client for a single case (map-friendly)
_CASE_FIELDS = [
    "CaseMasterID", "CrimeNo", "registered_date", "incident_from",
    "latitude", "longitude", "subhead_id", "subhead_name", "head_id", "head_name",
    "category", "gravity", "status", "station_id", "station_name",
    "district_id", "district_name",
]


def case_records(
    *,
    subhead_id: int | None = None,
    district_id: int | None = None,
    station_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    with_coords: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Filtered, JSON-ready case rows for the map/list views."""
    df = enriched_cases()
    if with_coords:
        df = df[df["latitude"].notna() & df["longitude"].notna()]
    if subhead_id is not None:
        df = df[df["subhead_id"] == str(subhead_id)]
    if district_id is not None:
        df = df[df["district_id"] == str(district_id)]
    if station_id is not None:
        df = df[df["station_id"] == str(station_id)]
    if date_from:
        df = df[df["registered_date"] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df["registered_date"] <= pd.to_datetime(date_to)]
    if limit is not None:
        df = df.head(limit)

    out = df[_CASE_FIELDS].copy()
    out["registered_date"] = out["registered_date"].dt.strftime("%Y-%m-%d")
    out["incident_from"] = out["incident_from"].dt.strftime("%Y-%m-%d %H:%M")
    return out.where(out.notna(), None).to_dict(orient="records")


def case_detail(case_id: int) -> dict | None:
    """Everything we know about one FIR, or None if the id is unknown.

    Deliberately light (PERF-001): a plain restatement of what's already on the
    warm caches — the FIR basics (``_CASE_FIELDS``), the people named on it
    (accused + victims), and the narrative. No graph metrics, no cross-FIR
    linking, no inference — a case click shows the case at a glance; deeper
    exploration is a Navigate away.
    """
    df = enriched_cases()
    cid = str(case_id)
    row = df[df["CaseMasterID"].astype(str) == cid]
    if row.empty:
        return None
    out = row[_CASE_FIELDS].copy()
    out["registered_date"] = out["registered_date"].dt.strftime("%Y-%m-%d")
    out["incident_from"] = out["incident_from"].dt.strftime("%Y-%m-%d %H:%M")
    detail = out.where(out.notna(), None).to_dict(orient="records")[0]

    def _people(records: list[dict]) -> list[dict]:
        return [
            {"name": r["name"], "age": r["age"], "gender": r["gender"]}
            for r in records
            if str(r["case_id"]) == cid
        ]

    detail["accused"] = _people(accused_records())
    detail["victims"] = _people(victim_records())
    detail["narrative"] = case_narratives().get(int(case_id))
    return detail


@timed_cache(_cache_ttl)
def accused_records() -> list[dict]:
    """Accused persons joined to their case's district, for entity resolution.

    Deliberately does NOT expose PersonID: identity must be *discovered* from
    attributes across FIRs, never joined on the per-record PersonID (ADR-003).

    Memoized (PERF-001): three engines (association, anomaly, entity) rebuild
    this per request otherwise. The warmer primes it; the TTL keeps datastore
    edits fresh (inf for CSV). Callers treat the result as read-only.
    """
    cols = ["AccusedMasterID", "CaseMasterID", "AccusedName", "AgeYear", "GenderID"]
    acc = _read("Accused")[cols]
    cases = enriched_cases()[["CaseMasterID", "district_id", "district_name"]]
    df = acc.merge(cases, on="CaseMasterID", how="left")
    df["age"] = pd.to_numeric(df["AgeYear"], errors="coerce")
    out = df.rename(
        columns={
            "AccusedMasterID": "accused_id",
            "CaseMasterID": "case_id",
            "AccusedName": "name",
            "GenderID": "gender",
        }
    )[["accused_id", "case_id", "name", "age", "gender", "district_id", "district_name"]]
    recs = out.to_dict(orient="records")
    for r in recs:  # age -> int|None for clean JSON / comparison
        r["age"] = None if pd.isna(r["age"]) else int(r["age"])
        for k in ("name", "gender", "district_id", "district_name"):
            if pd.isna(r[k]):
                r[k] = None
    return recs


#: light per-case fields returned inside a person's "other cases" list
_PERSON_CASE_FIELDS = [
    "CaseMasterID", "CrimeNo", "subhead_name", "district_name",
    "registered_date", "status",
]


def _person_key(rec: dict) -> tuple[str, int | None, str | None]:
    """The exact same-person match key: normalized name + age + gender.

    There is NO id that spans cases (AccusedMasterID/VictimMasterID are unique
    per record, and PersonID is unusable + ADR-003-forbidden), so a person is
    linked across FIRs by exact name+age+gender. This is an inference, not a
    fact — two different people can share all three (namesakes) — hence the
    POTENTIAL_ASSOCIATION classification on the endpoint.
    """
    return ((rec.get("name") or "").strip().lower(), rec.get("age"), rec.get("gender"))


@timed_cache(_cache_ttl)
def _person_case_index() -> dict:
    """(role, name, age, gender) -> the person's records across all cases.

    Cheap O(n) group-by over the already-memoized accused/victim records — the
    same-victim-name index pattern, extended to accused with age+gender. Primed
    by the warmer; TTL keeps datastore edits fresh. Read-only to callers.
    """
    idx: dict[tuple, list[dict]] = {}
    for role, records, idkey in (
        ("accused", accused_records(), "accused_id"),
        ("victim", victim_records(), "victim_id"),
    ):
        for r in records:
            key = (role, *_person_key(r))
            idx.setdefault(key, []).append(
                {
                    "record_id": r[idkey],
                    "case_id": r["case_id"],
                    "name": r["name"],
                    "age": r["age"],
                    "gender": r["gender"],
                    "district_id": r["district_id"],
                    "district_name": r["district_name"],
                }
            )
    return idx


@timed_cache(_cache_ttl)
def ranked_accused() -> list[dict]:
    """Distinct accused persons, ranked by how many crimes they committed.

    A "person" is the attribute identity name+age+gender (ADR-003 — never
    PersonID); their crime count is the number of DISTINCT cases those records
    span. Cheap O(n) group-by over the already-memoized ``_person_case_index``
    (the same index the person-detail path uses) — deliberately NOT
    ``resolve_identities`` (the O(n^2) path that times out). This backs the
    Identities tab's ranked list and its per-person similarity search.
    """
    out: list[dict] = []
    for key, members in _person_case_index().items():
        role = key[0]
        if role != "accused":
            continue
        districts = sorted({m["district_name"] for m in members if m["district_name"]})
        out.append(
            {
                "name": members[0]["name"],
                "age": members[0]["age"],
                "gender": members[0]["gender"],
                "districts": districts,
                "case_count": len({str(m["case_id"]) for m in members}),
            }
        )
    # most crimes first; stable secondary sort by name for deterministic paging
    out.sort(key=lambda p: (-p["case_count"], (p["name"] or "").lower()))
    return out


def person_detail(role: str, record_id: str) -> dict | None:
    """A person (accused/victim) and every case they appear in, or None.

    Deliberately light (PERF-001): the clicked record's own attributes (a FACT
    restatement) plus the cases sharing the same name+age+gender — a potential
    association, never `resolve_identities()` (the O(n²) path). Cases are light
    FIR restatements sorted by registration date.
    """
    role = role.lower()
    if role == "accused":
        records, idkey = accused_records(), "accused_id"
    elif role == "victim":
        records, idkey = victim_records(), "victim_id"
    else:
        return None
    rid = str(record_id)
    me = next((r for r in records if str(r[idkey]) == rid), None)
    if me is None:
        return None

    members = _person_case_index().get((role, *_person_key(me)), [])
    case_ids = {str(m["case_id"]) for m in members} | {str(me["case_id"])}

    df = enriched_cases()
    rows = df[df["CaseMasterID"].astype(str).isin(case_ids)][_PERSON_CASE_FIELDS].copy()
    rows["registered_date"] = rows["registered_date"].dt.strftime("%Y-%m-%d")
    rows = rows.sort_values("registered_date", na_position="last")
    cases = [
        {
            "case_id": r["CaseMasterID"],
            "crime_no": r["CrimeNo"],
            "subhead_name": r["subhead_name"],
            "district_name": r["district_name"],
            "registered_date": r["registered_date"],
            "status": r["status"],
        }
        for r in rows.where(rows.notna(), None).to_dict(orient="records")
    ]
    return {
        "role": role,
        "record_id": rid,
        "name": me["name"],
        "age": me["age"],
        "gender": me["gender"],
        "district_id": me["district_id"],
        "district_name": me["district_name"],
        "case_count": len(cases),
        "cases": cases,
    }


@timed_cache(_cache_ttl)
def case_narratives() -> dict[int, str]:
    """CaseMasterID -> BriefFacts, for MO extraction (MO-002/#38).

    Deliberately NOT part of _CASE_FIELDS: narratives are free text and stay
    off the general case API; only the MO pipeline reads them.
    """
    df = enriched_cases()
    if "BriefFacts" not in df.columns:
        return {}
    out: dict[int, str] = {}
    for case_id, text in zip(df["CaseMasterID"], df["BriefFacts"], strict=True):
        if text is None or (isinstance(text, float) and pd.isna(text)):
            continue
        text = str(text).strip()
        if text:
            out[int(case_id)] = text
    return out


@timed_cache(_cache_ttl)
def victim_records() -> list[dict]:
    """Victim persons joined to their case's district (for association search).

    Memoized (PERF-001) like accused_records; result is read-only to callers.
    """
    cols = ["VictimMasterID", "CaseMasterID", "VictimName", "AgeYear", "GenderID"]
    vic = _read("Victim")[cols]
    cases = enriched_cases()[["CaseMasterID", "district_id", "district_name"]]
    df = vic.merge(cases, on="CaseMasterID", how="left")
    df["age"] = pd.to_numeric(df["AgeYear"], errors="coerce")
    out = df.rename(
        columns={
            "VictimMasterID": "victim_id",
            "CaseMasterID": "case_id",
            "VictimName": "name",
            "GenderID": "gender",
        }
    )[["victim_id", "case_id", "name", "age", "gender", "district_id", "district_name"]]
    recs = out.to_dict(orient="records")
    for r in recs:
        r["age"] = None if pd.isna(r["age"]) else int(r["age"])
        for k in ("name", "gender", "district_id", "district_name"):
            if pd.isna(r[k]):
                r[k] = None
    return recs


def district_stats(window_days: int = 30) -> list[dict]:
    """Per-district case totals and a recent-vs-prior velocity ratio.

    Velocity = cases in the last ``window_days`` divided by cases in the
    ``window_days`` before that (>1 means activity is rising). Powers the
    district choropleth (case velocity) on the map.
    """
    df = enriched_cases()
    df = df[df["registered_date"].notna()]
    latest = df["registered_date"].max()
    recent_cut = latest - pd.Timedelta(days=window_days)
    prior_cut = latest - pd.Timedelta(days=2 * window_days)

    out = []
    for (did, dname), c in df.groupby(["district_id", "district_name"]):
        recent = int((c["registered_date"] > recent_cut).sum())
        prior = int((c["registered_date"] > prior_cut).sum()) - recent
        velocity = round(recent / prior, 2) if prior > 0 else None
        with_coords = c[c["latitude"].notna() & c["longitude"].notna()]
        out.append({
            "district_id": did,
            "district_name": dname,
            "case_count": int(len(c)),
            "cases_with_coords": int(len(with_coords)),
            "recent_count": recent,
            "prior_count": prior,
            "velocity": velocity,
        })
    out.sort(key=lambda d: d["case_count"], reverse=True)
    return out


def meta() -> dict:
    """Lookup values + dataset summary for filters, map centering, and banners."""
    df = enriched_cases()
    with_coords = df[df["latitude"].notna() & df["longitude"].notna()]
    subheads = (
        df[["subhead_id", "subhead_name", "head_id", "head_name"]]
        .drop_duplicates()
        .sort_values("subhead_id")
    )
    districts = (
        df[["district_id", "district_name"]].drop_duplicates().sort_values("district_id")
    )
    stations = (
        df[["station_id", "station_name", "district_id"]]
        .drop_duplicates()
        .sort_values("station_id")
    )
    dmin = df["registered_date"].min()
    dmax = df["registered_date"].max()
    center_lat = float(with_coords["latitude"].mean())
    center_lon = float(with_coords["longitude"].mean())
    return {
        "synthetic": True,
        "total_cases": int(len(df)),
        "cases_with_coords": int(len(with_coords)),
        "date_range": {
            "from": None if pd.isna(dmin) else dmin.strftime("%Y-%m-%d"),
            "to": None if pd.isna(dmax) else dmax.strftime("%Y-%m-%d"),
        },
        "map_center": {"lat": center_lat, "lon": center_lon},
        "crime_subheads": subheads.where(subheads.notna(), None).to_dict(orient="records"),
        "districts": districts.where(districts.notna(), None).to_dict(orient="records"),
        "stations": stations.where(stations.notna(), None).to_dict(orient="records"),
        "statuses": sorted(x for x in df["status"].dropna().unique().tolist()),
    }
