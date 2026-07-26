"""Unit tests for /api/cases pagination (offset/limit + total).

Exercises the data layer directly with a tiny in-memory frame (no dataset
generation, no auth): the new ``offset`` slicing and ``case_count`` total must
page the same filtered universe consistently."""

from __future__ import annotations

import pandas as pd
import pytest

from kavach.api import data


def _frame() -> pd.DataFrame:
    """Seven cases: five in district 44 (ids 1–5), two in district 50 (6–7).
    Cases 1–5 are geolocated; 6–7 have no coordinates."""
    rows = []
    for cid in range(1, 8):
        district = "44" if cid <= 5 else "50"
        geo = cid <= 5
        rows.append(
            {
                "CaseMasterID": str(cid),
                "CrimeNo": f"{cid}/2026",
                "latitude": 12.9 if geo else None,
                "longitude": 77.5 if geo else None,
                "subhead_id": "5",
                "subhead_name": "Theft",
                "head_id": "1",
                "head_name": "Property",
                "category": "FIR",
                "gravity": "High",
                "status": "Open",
                "station_id": "4430",
                "station_name": "Peenya PS",
                "district_id": district,
                "district_name": "Bengaluru City" if district == "44" else "Mysuru",
            }
        )
    df = pd.DataFrame(rows)
    df["registered_date"] = pd.to_datetime("2026-01-01")
    df["incident_from"] = pd.to_datetime("2026-01-01 09:00")
    return df


@pytest.fixture(autouse=True)
def _patch_cases(monkeypatch):
    frame = _frame()
    monkeypatch.setattr(data, "enriched_cases", lambda: frame)


def test_case_count_matches_filter():
    # with_coords off counts all 5 district-44 cases; on drops the 2 ungeocoded
    assert data.case_count(district_id=44, with_coords=False) == 5
    assert data.case_count(district_id=50, with_coords=False) == 2
    assert data.case_count(district_id=50, with_coords=True) == 0


def test_offset_limit_pages_are_disjoint_and_complete():
    ids = lambda rows: [r["CaseMasterID"] for r in rows]  # noqa: E731
    page1 = data.case_records(district_id=44, with_coords=False, limit=2, offset=0)
    page2 = data.case_records(district_id=44, with_coords=False, limit=2, offset=2)
    page3 = data.case_records(district_id=44, with_coords=False, limit=2, offset=4)

    assert len(page1) == 2 and len(page2) == 2 and len(page3) == 1  # 5 total
    # no overlap across pages, and together they cover the whole universe
    assert set(ids(page1)) | set(ids(page2)) | set(ids(page3)) == {"1", "2", "3", "4", "5"}
    assert not (set(ids(page1)) & set(ids(page2)))


def test_station_filter_paginates():
    assert data.case_count(station_id=4430, with_coords=False) == 7
    first = data.case_records(station_id=4430, with_coords=False, limit=3, offset=0)
    ids = [r["CaseMasterID"] for r in first]
    assert len(ids) == 3
