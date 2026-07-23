"""Data Store read adapter (CAT-002 / PR-B).

Network-free: the ZCQL transport (`datastore._query`) is stubbed, so these
tests exercise the paging, coercion, reindex, cache, and source-selector logic
without a live Data Store or any credentials.
"""

from __future__ import annotations

import types

import pandas as pd
import pytest

from kavach.api import data, datastore
from kavach.api.ttl_cache import timed_cache


@pytest.fixture(autouse=True)
def _clear_caches():
    datastore.cache_clear()
    data.enriched_cases.cache_clear()
    yield
    datastore.cache_clear()


def _wrap(table: str, rows: list[dict]) -> list[dict]:
    """Shape rows like the ZCQL envelope: [{"<Table>": {...}}, ...]."""
    return [{table: r} for r in rows]


# --- cell coercion (CSV string parity) -------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),          # NULL -> blank, like keep_default_na=False
        (True, "1"),         # Data Store boolean -> CSV BIT 1
        (False, "0"),
        (44, "44"),          # bigint arrives as int or str; both -> str
        ("44", "44"),
        (13.9361, "13.9361"),  # double round-trips through str()
    ],
)
def test_cell_matches_csv_string_form(value, expected):
    assert datastore._cell(value) == expected


# --- keyset paging ----------------------------------------------------------
def test_read_table_pages_by_keyset_without_duplicates(monkeypatch):
    """Two full-ish pages: cursor advances by ROWID, no row repeats, stops on a
    short page."""
    monkeypatch.setattr(datastore, "_ZCQL_PAGE", 2)  # tiny page to force paging
    monkeypatch.setattr(datastore, "_columns_for", lambda t: ["DistrictID", "DistrictName"])

    all_rows = [
        {"ROWID": "100", "DistrictID": "1", "DistrictName": "A"},
        {"ROWID": "101", "DistrictID": "2", "DistrictName": "B"},
        {"ROWID": "102", "DistrictID": "3", "DistrictName": "C"},
    ]
    seen_queries: list[str] = []

    def fake_query(zcql: str):
        seen_queries.append(zcql)
        # parse the "ROWID > N" cursor
        after = int(zcql.split("ROWID >")[1].split()[0])
        page = [r for r in all_rows if int(r["ROWID"]) > after][: datastore._ZCQL_PAGE]
        return _wrap("District", page)

    monkeypatch.setattr(datastore, "_query", fake_query)
    df = datastore._fetch_table("District")

    assert list(df["DistrictID"]) == ["1", "2", "3"]  # every row, once, in order
    assert list(df.columns) == ["DistrictID", "DistrictName"]  # ROWID dropped
    # 2 rows/page over 3 rows => page1 (100,101), page2 (102 -> short, stop)
    assert len(seen_queries) == 2
    assert "ROWID > 0" in seen_queries[0] and "ROWID > 101" in seen_queries[1]


def test_read_table_reindexes_missing_columns_to_blank(monkeypatch):
    """A column that is NULL for every row (ZCQL omits it) still appears, blank —
    so downstream ``df[[cols]]`` never KeyErrors, exactly like a CSV."""
    monkeypatch.setattr(datastore, "_columns_for", lambda t: ["DistrictID", "Active"])

    def fake_query(zcql: str):
        if "ROWID > 0" not in zcql:
            return []
        return _wrap("District", [{"ROWID": "1", "DistrictID": "7"}])  # no Active key

    monkeypatch.setattr(datastore, "_query", fake_query)
    df = datastore._fetch_table("District")
    assert df.loc[0, "DistrictID"] == "7"
    assert df.loc[0, "Active"] == ""  # missing -> blank string


def test_read_table_empty_has_columns(monkeypatch):
    monkeypatch.setattr(datastore, "_columns_for", lambda t: ["DistrictID", "DistrictName"])
    monkeypatch.setattr(datastore, "_query", lambda z: [])
    df = datastore._fetch_table("District")
    assert df.empty and list(df.columns) == ["DistrictID", "DistrictName"]


# --- per-table TTL cache ----------------------------------------------------
def test_read_table_caches_within_ttl(monkeypatch):
    monkeypatch.setattr(datastore, "_columns_for", lambda t: ["DistrictID"])
    monkeypatch.setattr(datastore, "settings", types.SimpleNamespace(datastore_cache_ttl=999))
    calls = {"n": 0}

    def fake_query(zcql: str):
        if "ROWID > 0" not in zcql:
            return []
        calls["n"] += 1
        return _wrap("District", [{"ROWID": "1", "DistrictID": "1"}])

    monkeypatch.setattr(datastore, "_query", fake_query)
    datastore.read_table("District")
    datastore.read_table("District")
    assert calls["n"] == 1  # second read served from cache

    datastore.cache_clear()
    datastore.read_table("District")
    assert calls["n"] == 2  # re-fetched after clear


def test_read_table_ttl_zero_always_refetches(monkeypatch):
    monkeypatch.setattr(datastore, "_columns_for", lambda t: ["DistrictID"])
    monkeypatch.setattr(datastore, "settings", types.SimpleNamespace(datastore_cache_ttl=0))
    calls = {"n": 0}
    monkeypatch.setattr(
        datastore, "_query",
        lambda z: (calls.__setitem__("n", calls["n"] + 1) or []) if "ROWID > 0" in z else [],
    )
    datastore.read_table("District")
    datastore.read_table("District")
    assert calls["n"] == 2  # ttl=0 disables caching


def test_read_table_returns_a_copy(monkeypatch):
    monkeypatch.setattr(datastore, "_columns_for", lambda t: ["DistrictID"])
    monkeypatch.setattr(datastore, "settings", types.SimpleNamespace(datastore_cache_ttl=999))
    monkeypatch.setattr(
        datastore, "_query",
        lambda z: (
            _wrap("District", [{"ROWID": "1", "DistrictID": "1"}]) if "ROWID > 0" in z else []
        ),
    )
    df = datastore.read_table("District")
    df.loc[0, "DistrictID"] = "MUTATED"
    assert datastore.read_table("District").loc[0, "DistrictID"] == "1"  # cache intact


# --- timed_cache decorator --------------------------------------------------
def test_timed_cache_infinite_ttl_caches_forever():
    calls = {"n": 0}

    @timed_cache(lambda: float("inf"))
    def build():
        calls["n"] += 1
        return calls["n"]

    assert build() == 1 and build() == 1  # cached
    build.cache_clear()
    assert build() == 2  # recomputed after clear


def test_timed_cache_zero_ttl_recomputes_each_call():
    calls = {"n": 0}

    @timed_cache(lambda: 0)
    def build():
        calls["n"] += 1
        return calls["n"]

    assert build() == 1 and build() == 2


# --- source selector in data.py --------------------------------------------
def test_source_selector_toggles_read(monkeypatch):
    ns = types.SimpleNamespace(data_source="datastore", datastore_cache_ttl=999)
    monkeypatch.setattr(data, "settings", ns)
    assert data._use_datastore() is True
    assert data._cache_ttl() == 999

    called = {}

    def fake_read(name):
        called["name"] = name
        return pd.DataFrame({"x": ["1"]})

    monkeypatch.setattr(datastore, "read_table", fake_read)
    out = data._read("District")
    assert called["name"] == "District" and list(out["x"]) == ["1"]


def test_source_selector_defaults_to_csv(monkeypatch):
    ns = types.SimpleNamespace(data_source="csv", datastore_cache_ttl=999)
    monkeypatch.setattr(data, "settings", ns)
    assert data._use_datastore() is False
    assert data._cache_ttl() == float("inf")
    # CSV path still reads a real bundled file
    assert not data._read("District").empty
