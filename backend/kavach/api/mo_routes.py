"""MO intelligence API (MO-002/#38).

Serves the extracted profile beside the narrative it came from, with the
character spans that justified each attribute — so the console can highlight
the exact phrase behind every value (demo moment D3).

Responses are AI_DERIVED and therefore carry model_version; the envelope
validator refuses that classification without one.
"""

from __future__ import annotations

import functools
import json
import threading

from fastapi import APIRouter, HTTPException, Query

from kavach.analytics.mo import (
    METHOD_NAME,
    MODEL_VERSION,
    ExtractionSkipped,
    MoProfile,
    MoRepository,
    MoValidationError,
    extract,
    run_extraction,
    unknown_rate,
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
    reset_mo_index()


_index_lock = threading.Lock()


def _extract_profile(case_id: int, narrative: str) -> MoProfile | None:
    """Extract one narrative's MO in memory — no persistence, no provenance.

    Persisting each profile and emitting its provenance evidence (what the
    durable store does) is thousands of write transactions across the corpus;
    on Catalyst's networked storage that ran ~40s and 408'd every cold request.
    The serving API only needs the extracted attributes and their spans, which
    extraction alone produces in microseconds. The durable, audit-grade store
    (repository.py) is still built off the request path for the provenance
    trail #38 requires — it is just no longer in the way of a page load.
    """
    try:
        return extract(case_id, narrative, None).profile
    except (ExtractionSkipped, MoValidationError):
        return None


@functools.lru_cache(maxsize=1)
def _mo_index() -> dict[int, MoProfile]:
    """The whole corpus's MO, extracted once into memory and cached.

    Built lazily on first use (and off the request path by the warmer), so no
    single request pays the whole-corpus cost. This backs the cross-case
    features the console needs — keyword/attribute filtering and similar-MO
    search — while the paged list and single-case detail serialize only the
    handful of profiles they actually return.
    """
    index: dict[int, MoProfile] = {}
    for case_id, narrative in data.case_narratives().items():
        profile = _extract_profile(case_id, narrative)
        if profile is not None:
            index[case_id] = profile
    return index


def mo_index() -> dict[int, MoProfile]:
    with _index_lock:
        return _mo_index()


def reset_mo_index() -> None:
    with _index_lock:
        _mo_index.cache_clear()


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
    """Extraction coverage and per-attribute UNKNOWN rates.

    Reported from the in-memory index — the numbers describe what the extractor
    produces over the corpus, which needs no durable run to compute — so this
    stays cheap on the request path.
    """
    index = mo_index()
    profiles = list(index.values())
    processed = len(profiles)
    total = len(data.case_narratives())
    return {
        "synthetic": True,
        "run_id": f"mo-index-{MODEL_VERSION}",
        "model_version": MODEL_VERSION,
        "extractor": "RULE_BASED (deterministic; Zia runs offline)",
        "processed": processed,
        "skipped": max(total - processed, 0),
        "failed": 0,
        "zia_extractions": 0,
        "zia_unavailable_reason": None,
        "unknown_rates": unknown_rate(profiles),
        "profile_count": processed,
        "intelligence": _envelope(),
    }


@router.get("/profiles")
def list_profiles(
    q: str | None = Query(default=None, description="FIR number or words in the narrative"),
    action: str | None = Query(default=None, description="filter: crime_action"),
    target: str | None = Query(default=None, description="filter: target_type"),
    mobility: str | None = Query(default=None, description="filter: mobility"),
    limit: int = Query(default=15, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Search, filter and page the extracted profiles.

    Filtering by MO keyword runs across the whole corpus — that is the point,
    "find every case committed this way" — but only one page of profiles is
    ever serialized into the response. The per-request cost scales with the
    page size, not the FIR count, so it stays well inside AppSail's HTTP limit
    as the corpus grows (see docs/analytics/mo-schema-v1.md on scaling).
    """
    index = mo_index()
    narratives = data.case_narratives()

    def keep(case_id: int) -> bool:
        profile = index[case_id]
        if action and str(profile.crime_action.value) != action:
            return False
        if target and str(profile.target_type.value) != target:
            return False
        if mobility and str(profile.mobility.value) != mobility:
            return False
        if q:
            needle = q.strip().lower()
            if needle not in str(case_id) and needle not in (
                narratives.get(case_id, "") or ""
            ).lower():
                return False
        return True

    matched = [cid for cid in sorted(index) if keep(cid)]
    total = len(matched)
    page_ids = matched[offset : offset + limit]
    return {
        "synthetic": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(page_ids),
        "profiles": [
            {
                **json.loads(index[cid].model_dump_json()),
                "narrative_preview": (narratives.get(cid, "") or "")[:160],
            }
            for cid in page_ids
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
    index = mo_index()
    target = index.get(case_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"no MO profile for case {case_id}")

    narratives = data.case_narratives()
    matches = find_similar(target, list(index.values()), limit=limit)
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
    """One case: the narrative and the MO extracted from it, with spans.

    Extracted on demand for just this case — nothing else is loaded to answer
    it — so selecting a case fetches only what that case needs.
    """
    narrative = data.case_narratives().get(case_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail=f"no narrative for case {case_id}")
    profile = _extract_profile(case_id, narrative)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"no MO profile for case {case_id} (narrative may be too short to extract)",
        )
    return {
        "synthetic": True,
        "case_master_id": case_id,
        "narrative": narrative,
        "profile": json.loads(profile.model_dump_json()),
        "intelligence": _envelope(),
    }
