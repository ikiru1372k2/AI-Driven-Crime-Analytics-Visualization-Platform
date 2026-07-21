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
from kavach.analytics.mo.runner import ExtractionRunResult
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
    """Extract once per process, then serve from memory.

    Zia needs Catalyst request headers that are unavailable at startup, so the
    batch runs on the deterministic path and per-request Zia enrichment is a
    later refinement (#39/#64). The extractor records which path produced each
    profile, so the distinction is never hidden.
    """
    conn = connect(check_same_thread=False)
    provenance = ProvenanceRepository(conn)
    narratives = data.case_narratives()
    result = run_extraction(conn, provenance, narratives, zia=_zia_client())
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
def list_profiles(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    """Extracted profiles (queue for the MO view)."""
    repo, _ = mo_store()
    payloads = repo.profile_payloads()
    narratives = data.case_narratives()
    rows = [
        {
            **p,
            "narrative_preview": (narratives.get(p["case_master_id"], "") or "")[:160],
        }
        for p in payloads[:limit]
    ]
    return {
        "synthetic": True,
        "total": len(payloads),
        "count": len(rows),
        "profiles": rows,
        "intelligence": _envelope(),
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
