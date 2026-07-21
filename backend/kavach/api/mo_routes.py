"""MO intelligence API (MO-002/#38).

Serves the extracted profile beside the narrative it came from, with the
character spans that justified each attribute — so the console can highlight
the exact phrase behind every value (demo moment D3).

Responses are AI_DERIVED and therefore carry model_version; the envelope
validator refuses that classification without one.
"""

from __future__ import annotations

import functools
import threading

from fastapi import APIRouter, HTTPException, Query

from kavach.analytics.mo import (
    METHOD_NAME,
    MODEL_VERSION,
    MoRepository,
    run_extraction,
)
from kavach.analytics.mo.runner import (
    ExtractionRunResult,
    load_precomputed,
    precomputed_path,
)
from kavach.analytics.mo.similarity import find_similar
from kavach.analytics.mo.zia import ZiaClient
from kavach.api import data
from kavach.api.envelope import envelope
from kavach.provenance import DataClassification, ProvenanceRepository
from kavach.repositories.dev_fixture import connect

router = APIRouter(prefix="/api/v1/mo", tags=["mo"])

_lock = threading.Lock()

_MO_LIMITATIONS = (
    "AI_DERIVED from the FIR narrative only — not a finding of fact",
    "extraction is anchored to narrative spans; UNKNOWN means no evidence in the text",
    "synthetic data (ADR-011)",
)


@functools.lru_cache(maxsize=1)
def _store() -> tuple[MoRepository, ExtractionRunResult]:
    """Load (or extract) profiles once per process, then serve from memory.

    zcatalyst_sdk.initialize() requires Catalyst platform headers that only
    accompany authenticated requests, so a deployed runtime cannot call Zia
    while building this cache. Zia therefore runs offline against the real
    project (scripts/mo_precompute.py) and its output ships with the bundle;
    without that file the deterministic extractor runs instead. Either way the
    profile records which extractor produced it — the difference is never
    hidden from the analyst.
    """
    conn = connect(check_same_thread=False)
    provenance = ProvenanceRepository(conn)

    # Prefer profiles extracted with Zia ahead of deployment; they are
    # re-validated on load, so a stale file cannot smuggle in bad data.
    path = precomputed_path()
    if path is not None:
        loaded = load_precomputed(conn, provenance, path)
        if loaded is not None and loaded.processed:
            return MoRepository(conn), loaded

    result = run_extraction(conn, provenance, data.case_narratives(), zia=_zia_client())
    return MoRepository(conn), result


def _zia_client() -> ZiaClient | None:
    """Zia client when the runtime can reach it, else None (fallback path)."""
    from kavach.auth.validator import is_catalyst_runtime

    return ZiaClient() if is_catalyst_runtime() else None


def mo_store() -> tuple[MoRepository, ExtractionRunResult]:
    with _lock:
        return _store()


def reset_mo_store() -> None:
    """Test hook: re-extract after KAVACH_DATA_DIR changes."""
    with _lock:
        _store.cache_clear()


def _envelope() -> dict:
    return envelope(
        classification=DataClassification.AI_DERIVED,
        method_name=METHOD_NAME,
        method_version=MODEL_VERSION,
        model_version=MODEL_VERSION,
        limitations=_MO_LIMITATIONS,
    )


@router.get("/vocabulary")
def vocabulary() -> dict:
    """Allowed values per filterable MO attribute.

    Served from the schema so the console's filter options cannot drift from
    what the extractor is permitted to produce (schema.py is the one source).
    """
    from kavach.analytics.mo.schema import ACTION, MOBILITY, TARGET, UNKNOWN

    def options(vocab: tuple[str, ...]) -> list[str]:
        # UNKNOWN is filterable too: "which FIRs never said how they travelled?"
        return [v for v in vocab if v != "other"] if UNKNOWN in vocab else list(vocab)

    return {
        "crime_action": options(ACTION),
        "target_type": options(TARGET),
        "mobility": options(MOBILITY),
    }


@router.get("/runs/latest")
def latest_run() -> dict:
    """Extraction run metrics: coverage, failures and UNKNOWN rates."""
    repo, result = mo_store()
    return {
        "synthetic": True,
        "run_id": result.run_id,
        "model_version": MODEL_VERSION,
        "extractor": result.extractor_mix,
        "processed": result.processed,
        "skipped": result.skipped,
        "failed": result.failed,
        "zia_extractions": result.zia_used,
        "zia_unavailable_reason": result.zia_unavailable_reason,
        "unknown_rates": result.unknown_rates,
        "profile_count": len(repo.all_profiles()),
        "intelligence": _envelope(),
    }


@router.get("/profiles")
def list_profiles(
    q: str | None = Query(default=None, description="FIR number or words in the narrative"),
    action: str | None = Query(default=None, description="filter: crime_action"),
    target: str | None = Query(default=None, description="filter: target_type"),
    mobility: str | None = Query(default=None, description="filter: mobility"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Search and page the extracted profiles.

    Filtering and paging happen server-side and only one page is serialized:
    the client never receives the whole corpus, which is the shape this needs
    to keep as the FIR count grows (see docs/analytics/mo-schema-v1.md on
    scaling).
    """
    repo, _ = mo_store()
    narratives = data.case_narratives()
    rows = repo.profile_payloads()

    if action:
        rows = [r for r in rows if str(r["crime_action"]["value"]) == action]
    if target:
        rows = [r for r in rows if str(r["target_type"]["value"]) == target]
    if mobility:
        rows = [r for r in rows if str(r["mobility"]["value"]) == mobility]
    if q:
        needle = q.strip().lower()
        rows = [
            r
            for r in rows
            if needle in str(r["case_master_id"])
            or needle in (narratives.get(r["case_master_id"], "") or "").lower()
        ]

    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "synthetic": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(page),
        "profiles": [
            {
                **r,
                "narrative_preview": (narratives.get(r["case_master_id"], "") or "")[:160],
            }
            for r in page
        ],
        "intelligence": _envelope(),
    }


@router.get("/{case_id}/related")
def related_cases(
    case_id: int,
    limit: int = Query(default=15, ge=1, le=50),
) -> dict:
    """Cases committed in a similar way (MO-004/#40).

    A lead to investigate, classified POTENTIAL_ASSOCIATION — never a claim
    that the same person committed both.
    """
    repo, _ = mo_store()
    target = repo.get(case_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"no MO profile for case {case_id}")

    narratives = data.case_narratives()
    matches = find_similar(target, repo.all_profiles(), limit=limit)
    return {
        "synthetic": True,
        "case_master_id": case_id,
        "match_count": len(matches),
        "matches": [
            {
                "case_master_id": m.case_master_id,
                "score": m.score,
                "matched": list(m.matched),
                "differed": list(m.differed),
                "explanation": m.explanation,
                "narrative_preview": (narratives.get(m.case_master_id, "") or "")[:160],
            }
            for m in matches
        ],
        "intelligence": envelope(
            classification=DataClassification.POTENTIAL_ASSOCIATION,
            method_name="mo_attribute_similarity",
            method_version="1.0.0",
            model_version=MODEL_VERSION,
            limitations=(
                "a lead for review, not a finding that the same person is responsible",
                "UNKNOWN attributes never count as agreement",
                "synthetic data (ADR-011)",
            ),
        ),
    }


@router.get("/{case_id}")
def get_profile(case_id: int) -> dict:
    """One case: the narrative and the MO extracted from it, with spans."""
    repo, _ = mo_store()
    narrative = data.case_narratives().get(case_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail=f"no narrative for case {case_id}")
    profile = repo.get(case_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"no MO profile for case {case_id} (narrative may be too short to extract)",
        )
    import json

    return {
        "synthetic": True,
        "case_master_id": case_id,
        "narrative": narrative,
        "profile": json.loads(profile.model_dump_json()),
        "intelligence": _envelope(),
    }
