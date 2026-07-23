"""Catalyst Data Store read adapter (CAT-002 / PR-B).

Reads whole source tables out of the live Catalyst Data Store over OAuth REST and
returns them as string-typed pandas DataFrames **shaped exactly like the CSVs**
``data.py`` reads — same columns, same string cells (``""`` for blanks) — so
every consumer of ``data.py`` works unchanged when ``KAVACH_DATA_SOURCE`` flips
to ``datastore``. It is the read-side mirror of ``scripts/catalyst/
seed_datastore.py`` (the write side), and authenticates like
``catalyst/quickml.py``: a self-client refresh token mints a short-lived access
token, cached process-wide.

Why ZCQL, not the row API: the ``GET /table/{id}/row`` endpoint does not accept
paging params, but ZCQL does (``LIMIT``/``OFFSET``), capped at **300 rows per
query** — so a table is read by looping ``SELECT * FROM T LIMIT 300 OFFSET k``
until a short page. Results come back wrapped as ``{"<Table>": {...}}`` per row.

Liveness: each table is cached for ``KAVACH_DATASTORE_TTL`` seconds (a short TTL,
not the process lifetime), so an edit made in the Zoho console appears in the app
within the TTL without a redeploy.

Requires a refresh token scoped ``ZohoCatalyst.tables.rows.READ`` — a *different*
scope from the QuickML token, minted as a separate console step. No secrets are
read from the repo (ADR-001); everything comes from the environment via config.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from kavach.config import settings

#: ZCQL hard cap — a single query may return at most this many rows.
_ZCQL_PAGE = 300
#: Catalyst system columns — present on every row, never part of the CSV shape.
_SYSTEM_COLUMNS = {"ROWID", "CREATORID", "CREATEDTIME", "MODIFIEDTIME"}
_TOKEN_TIMEOUT_S = 12
_QUERY_TIMEOUT_S = 30
#: Refresh the access token this many seconds before it actually expires.
_TOKEN_SKEW_S = 60

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Process-wide access-token cache, keyed by (accounts_url, client_id,
#: refresh_token) — same rationale as quickml.py's cache.
_token_cache: dict[tuple[str, str, str], tuple[str, float]] = {}
_token_lock = threading.Lock()

#: Per-table row cache: table_name -> (monotonic_ts, DataFrame).
_table_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_table_lock = threading.Lock()

#: Cached schema-manifest columns (table_name -> [columns]).
_manifest_columns: dict[str, list[str]] | None = None
_manifest_lock = threading.Lock()


class DataStoreUnavailable(RuntimeError):
    """The Data Store is unconfigured, unreachable, or returned junk."""


# --- schema (column set per table, so NULL-only columns still appear) -------
def _manifest_path() -> Path:
    """Locate schema-manifest.json in both the repo and the deployed bundle."""
    env = os.environ.get("KAVACH_SCHEMA_MANIFEST")
    candidates = [
        *([Path(env)] if env else []),
        _REPO_ROOT / "docs/schema/schema-manifest.json",
        Path.cwd() / "docs/schema/schema-manifest.json",
        Path(__file__).resolve().parents[2] / "docs/schema/schema-manifest.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise DataStoreUnavailable(
        "schema-manifest.json not found; looked in: "
        + ", ".join(str(c) for c in candidates)
    )


def _columns_for(table: str) -> list[str]:
    """Documented columns for a table (the CSV header), from the manifest."""
    global _manifest_columns
    with _manifest_lock:
        if _manifest_columns is None:
            raw = json.loads(_manifest_path().read_text())
            _manifest_columns = {
                k: v["columns"] for k, v in raw.items() if not k.startswith("_")
            }
    cols = _manifest_columns.get(table)
    if cols is None:
        raise DataStoreUnavailable(f"table {table!r} is not in the schema manifest")
    return cols


# --- OAuth (self-client refresh token -> access token) ----------------------
def _refresh_token() -> str | None:
    """Data Store-scoped refresh token, falling back to the shared one."""
    return settings.datastore_refresh_token or settings.zoho_refresh_token


def _oauth_configured() -> bool:
    return bool(settings.zoho_client_id and settings.zoho_client_secret and _refresh_token())


def _access_token() -> str:
    """A valid access token, minted/refreshed via the refresh token (cached)."""
    if not _oauth_configured():
        raise DataStoreUnavailable("data store oauth self-client not configured")
    refresh = _refresh_token() or ""
    key = (settings.zoho_accounts_url, settings.zoho_client_id or "", refresh)
    now = time.monotonic()
    with _token_lock:
        cached = _token_cache.get(key)
        if cached and cached[1] - _TOKEN_SKEW_S > now:
            return cached[0]

    params = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": settings.zoho_client_id,
            "client_secret": settings.zoho_client_secret,
            "refresh_token": refresh,
        }
    ).encode("utf-8")
    url = settings.zoho_accounts_url.rstrip("/") + "/oauth/v2/token"
    req = urllib.request.Request(url, data=params, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TOKEN_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise DataStoreUnavailable(
            f"oauth token request failed: {type(exc).__name__}: {exc}"
        ) from exc
    token = payload.get("access_token")
    if not token:
        raise DataStoreUnavailable(f"oauth token error: {payload.get('error', payload)}")
    expires_in = float(payload.get("expires_in", 3600))
    with _token_lock:
        _token_cache[key] = (token, now + expires_in)
    return token


# --- ZCQL query transport ---------------------------------------------------
def _project_base() -> str:
    project_id = settings.catalyst_project_id
    if not project_id:
        raise DataStoreUnavailable("CATALYST_PROJECT_ID not configured")
    return f"{settings.datastore_api_base.rstrip('/')}/baas/v1/project/{project_id}"


def _query(zcql: str) -> list[dict]:
    """Run one ZCQL statement, returning the raw ``data`` list (row wrappers)."""
    token = _access_token()
    body = json.dumps({"query": zcql}).encode("utf-8")
    req = urllib.request.Request(
        _project_base() + "/query",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_QUERY_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise DataStoreUnavailable(f"zcql HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise DataStoreUnavailable(
            f"zcql query failed: {type(exc).__name__}: {exc}"
        ) from exc
    return payload.get("data", []) or []


def _cell(value: object) -> str:
    """Coerce a ZCQL value to the CSV string form (parity with pandas dtype=str)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        # Data Store booleans come back true/false; the CSVs store BIT as 1/0.
        return "1" if value else "0"
    return str(value)


def _fetch_table(table: str) -> pd.DataFrame:
    """Read an entire table via paged ZCQL into a string DataFrame (CSV-shaped).

    Uses **keyset pagination** on ROWID (``WHERE ROWID > <last>``) rather than
    LIMIT/OFFSET: ZCQL's OFFSET overlaps rows at page boundaries (the last row
    of a page reappears as the first of the next), which would insert duplicates.
    Keyset paging walks strictly forward by the unique, monotonic system PK, so
    it never repeats or skips a row — and is unaffected by concurrent inserts.
    """
    columns = _columns_for(table)
    cols = ", ".join(["ROWID", *columns])  # ROWID drives the cursor
    rows: list[dict[str, str]] = []
    last_rowid = "0"
    while True:
        page = _query(
            f"SELECT {cols} FROM {table} WHERE ROWID > {last_rowid} "
            f"ORDER BY ROWID LIMIT {_ZCQL_PAGE}"
        )
        for wrapper in page:
            raw = wrapper.get(table, wrapper)  # unwrap {"<Table>": {...}}
            last_rowid = str(raw.get("ROWID", last_rowid))
            rows.append({c: _cell(raw.get(c)) for c in columns})
        if len(page) < _ZCQL_PAGE:
            break
    # Build with explicit columns so an empty table still has the right shape.
    return pd.DataFrame(rows, columns=columns, dtype=str)


# --- public API -------------------------------------------------------------
def read_table(table: str) -> pd.DataFrame:
    """Return a table as a CSV-shaped string DataFrame, cached for the TTL.

    The returned frame is a copy, so callers may mutate it freely without
    corrupting the cache.
    """
    ttl = settings.datastore_cache_ttl
    now = time.monotonic()
    with _table_lock:
        hit = _table_cache.get(table)
        if hit and (ttl > 0) and (now - hit[0] < ttl):
            return hit[1].copy()
    df = _fetch_table(table)
    with _table_lock:
        _table_cache[table] = (now, df)
    return df.copy()


def materialize_csvs(dest: Path, tables: list[str]) -> None:
    """Write each table to ``dest/<table>.csv`` in the CSV shape.

    Lets CSV-only consumers (the ingestion loader behind ``graph_store``) run
    unchanged against Data Store rows: fetch → dump to a temp dir → load. Blank
    cells are written as empty fields, matching the bundled CSVs.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for table in tables:
        read_table(table).to_csv(dest / f"{table}.csv", index=False)


def cache_clear() -> None:
    """Drop the per-table row cache (next read re-fetches). Test/ops hook."""
    with _table_lock:
        _table_cache.clear()
