"""MO-002/#38 acceptance tests: extraction, validation, fallback, ground truth."""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.mo import (
    EXTRACTOR_RULES,
    EXTRACTOR_ZIA,
    MODEL_VERSION,
    MoRepository,
    MoValidationError,
    extract,
    run_extraction,
    unknown_rate,
)
from kavach.analytics.mo.extractor import ExtractionSkipped
from kavach.analytics.mo.schema import UNKNOWN, validate_extraction
from kavach.analytics.mo.zia import ZiaClient, ZiaEntity, ZiaSignal, ZiaUnavailable, parse_signal
from kavach.api import data
from kavach.datagen.generator import generate_dataset
from kavach.provenance import IntelligenceType, ProvenanceRepository, RunStatus
from kavach.repositories.dev_fixture import connect

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"

CHAIN_SNATCH = (
    "Two unknown persons travelling on a motorcycle approached the complainant "
    "near the bus stop and snatched a gold chain before escaping towards Tumakuru Road."
)
NO_MOBILITY = (
    "The accused collected money from the complainant promising a job and failed to return it."
)

#: the live Zia response shape, captured from AI-KSP on 2026-07-21
ZIA_KEYWORDS = [{"keyword_extractor": {
    "keywords": ["motorcycle", "complainant"],
    "keyphrases": ["bus stop", "Tumakuru Road", "gold chain", "unknown persons"],
}}]
ZIA_NER = [{"ner": {"general_entities": [
    {"start_index": "0", "confidence_score": "100", "end_index": "3",
     "ner_tag": "Number", "token": "Two"},
    {"start_index": "107", "confidence_score": "100", "end_index": "111",
     "ner_tag": "Color", "token": "gold"},
]}}]


# -- extraction core -------------------------------------------------------
def test_chain_snatch_narrative_extracts_expected_mo():
    result = extract(1, CHAIN_SNATCH)
    p = result.profile
    assert p.crime_action.value == "snatching"
    assert p.target_type.value == "gold_chain"
    assert p.mobility.value == "motorcycle"
    assert p.offender_count.value == 2
    assert p.escape_direction.value.startswith("Tumakuru")


def test_narrative_without_mobility_yields_unknown():
    """AC2: absence of evidence is UNKNOWN, never a guess."""
    p = extract(2, NO_MOBILITY).profile
    assert p.mobility.value == UNKNOWN
    assert p.target_type.value == "cash"  # "money" is present, weakly
    assert p.mobility.confidence == 0.5  # documented "no evidence" confidence


def test_every_attribute_is_anchored_to_the_narrative():
    """source_span must index back to the exact justifying substring."""
    p = extract(3, CHAIN_SNATCH).profile
    for name in ("mobility", "crime_action", "target_type", "offender_count"):
        attr = getattr(p, name)
        assert attr.source_span is not None, name
        start, end = attr.source_span
        assert CHAIN_SNATCH[start:end], name


def test_short_or_empty_narrative_is_skipped():
    for text in ("", "   ", "Theft."):
        with pytest.raises(ExtractionSkipped):
            extract(4, text)


def test_profile_carries_provenance_fields():
    """AC5: model_version + extractor + extracted_at on every profile."""
    p = extract(5, CHAIN_SNATCH).profile
    assert p.model_version == MODEL_VERSION
    assert p.extractor == EXTRACTOR_RULES
    assert p.extracted_at
    assert p.schema_version == "mo-schema-v1"


def test_longest_phrase_wins_over_weaker_reading():
    """'gold chain' (STRONG) must beat the bare 'chain' (WEAK) reading."""
    p = extract(6, CHAIN_SNATCH).profile
    assert p.target_type.value == "gold_chain"
    assert p.target_type.confidence >= 0.9


# -- Zia integration -------------------------------------------------------
def test_zia_signal_parsed_from_live_response_shape():
    signal = parse_signal(ZIA_KEYWORDS, ZIA_NER)
    assert "motorcycle" in signal.keywords
    assert signal.mentions("gold chain")
    numbers = signal.numbers()
    assert numbers and numbers[0].token == "Two" and numbers[0].confidence == 1.0


def test_zia_corroboration_raises_confidence_and_marks_extractor():
    signal = parse_signal(ZIA_KEYWORDS, ZIA_NER)
    without = extract(7, CHAIN_SNATCH).profile
    with_zia = extract(7, CHAIN_SNATCH, signal)
    assert with_zia.extractor == EXTRACTOR_ZIA
    assert with_zia.profile.mobility.confidence > without.mobility.confidence
    assert with_zia.profile.mobility.confidence <= 0.95  # ceiling
    assert with_zia.zia_corroborations > 0


def test_zia_cannot_originate_a_value_the_lexicon_did_not_find():
    """ADR-006 guard: free-form output never becomes analytical truth."""
    fabricated = ZiaSignal(
        keywords=("helicopter", "machete"),
        keyphrases=("gold chain",),
        entities=(ZiaEntity(token="Nine", tag="Number", start=0, end=4, confidence=1.0),),
    )
    p = extract(8, NO_MOBILITY, fabricated).profile
    assert p.mobility.value == UNKNOWN      # "helicopter" cannot set mobility
    assert p.weapon_involved.value == UNKNOWN  # "machete" is not in the narrative
    assert p.offender_count.value == UNKNOWN   # Number without a lexicon match


def test_zia_number_only_used_when_pattern_agrees():
    """A Number entity that disagrees with the text is ignored, not trusted."""
    disagreeing = ZiaSignal(
        entities=(ZiaEntity(token="Nine", tag="Number", start=0, end=4, confidence=1.0),),
    )
    p = extract(9, CHAIN_SNATCH, disagreeing).profile
    assert p.offender_count.value == 2  # from the narrative, not from Zia


def test_malformed_zia_payload_degrades_gracefully():
    signal = parse_signal({"unexpected": True}, [{"ner": {"general_entities": [{"bad": 1}]}}])
    assert signal.keywords == () and signal.entities == ()
    assert extract(10, CHAIN_SNATCH, signal).profile.mobility.value == "motorcycle"


def test_zia_client_unavailable_without_sdk():
    with pytest.raises(ZiaUnavailable):
        ZiaClient().analyse(CHAIN_SNATCH)


# -- validation / whole-rejection -----------------------------------------
def test_invalid_payload_is_rejected_whole():
    """AC1: invalid output never becomes a profile."""
    with pytest.raises(MoValidationError):
        validate_extraction({
            "case_master_id": 1,
            "extractor": EXTRACTOR_ZIA,
            "model_version": MODEL_VERSION,
            "extracted_at": "2026-07-21T00:00:00Z",
            "offender_count": {"value": 2, "confidence": 0.9},
            "mobility": {"value": "helicopter", "confidence": 0.9},  # out of vocabulary
            "approach_method": {"value": UNKNOWN, "confidence": 0.5},
            "crime_action": {"value": UNKNOWN, "confidence": 0.5},
            "target_type": {"value": UNKNOWN, "confidence": 0.5},
            "escape_direction": {"value": UNKNOWN, "confidence": 0.5},
            "time_context": {"value": UNKNOWN, "confidence": 0.5},
            "weapon_involved": {"value": UNKNOWN, "confidence": 0.5},
        })


# -- batch runner ----------------------------------------------------------
@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("mo_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=400)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    data.case_narratives.cache_clear()
    yield out
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()
    data.case_narratives.cache_clear()


def test_narratives_are_exposed_for_extraction(dataset):
    narratives = data.case_narratives()
    assert narratives, "BriefFacts must reach the MO pipeline"
    assert all(isinstance(k, int) and v.strip() for k, v in narratives.items())


def test_batch_run_persists_only_valid_profiles(dataset):
    conn = connect()
    prov = ProvenanceRepository(conn)
    result = run_extraction(conn, prov, data.case_narratives())

    assert result.processed > 0
    run = prov.get_run(result.run_id)
    assert run.status is RunStatus.COMPLETED
    assert run.intelligence_type is IntelligenceType.MO_PROFILE

    repo = MoRepository(conn)
    stored = repo.all_profiles()
    assert len(stored) == result.processed
    for p in stored:  # AC1: everything persisted validates
        validate_extraction(json.loads(p.model_dump_json()))


def test_batch_run_is_idempotent_per_model_version(dataset):
    conn = connect()
    prov = ProvenanceRepository(conn)
    first = run_extraction(conn, prov, data.case_narratives())
    second = run_extraction(conn, prov, data.case_narratives())
    repo = MoRepository(conn)
    assert first.processed == second.processed
    assert len(repo.all_profiles()) == second.processed  # replaced, not duplicated


def test_fallback_path_when_zia_unavailable(dataset):
    """AC4: a Zia client that always fails still yields a complete run."""

    class DeadZia(ZiaClient):
        def analyse(self, text: str) -> ZiaSignal:
            raise ZiaUnavailable("stubbed unavailable")

    conn = connect()
    prov = ProvenanceRepository(conn)
    result = run_extraction(conn, prov, data.case_narratives(), zia=DeadZia())

    assert result.processed > 0
    assert result.zia_used == 0
    assert "stubbed unavailable" in (result.zia_unavailable_reason or "")
    assert all(p.extractor == EXTRACTOR_RULES for p in MoRepository(conn).all_profiles())


def test_ground_truth_extraction_rate_meets_threshold(dataset):
    """AC3: >=80% of the planted chain-snatching cases extract the known MO."""
    ground_truth = json.loads((dataset / "ground_truth.json").read_text())["mo_pattern"]
    case_ids = ground_truth["case_ids"]
    narratives = data.case_narratives()

    hits = 0
    for case_id in case_ids:
        text = narratives.get(int(case_id))
        if not text:
            continue
        p = extract(int(case_id), text).profile
        if (
            p.crime_action.value == ground_truth["action"]
            and p.target_type.value == ground_truth["target"]
            and p.mobility.value == ground_truth["mobility"]
            and p.offender_count.value == ground_truth["offender_count"]
        ):
            hits += 1

    rate = hits / len(case_ids)
    assert rate >= 0.8, f"ground-truth extraction rate {rate:.0%} below the 80% threshold"


def test_unknown_rates_reported_for_drift(dataset):
    conn = connect()
    prov = ProvenanceRepository(conn)
    result = run_extraction(conn, prov, data.case_narratives())
    assert set(result.unknown_rates) >= {"mobility", "crime_action", "target_type"}
    assert all(0.0 <= v <= 1.0 for v in result.unknown_rates.values())


def test_evidence_rows_cite_their_source_case(dataset):
    conn = connect()
    prov = ProvenanceRepository(conn)
    result = run_extraction(conn, prov, data.case_narratives(), limit=5)
    evidence = prov.evidence_for_run(result.run_id)
    per_case = [e for e in evidence if e.result_ref.startswith("mo:")]
    assert per_case
    for e in per_case:
        assert e.classification.value == "AI_DERIVED"
        assert len(e.evidence_case_ids) == 1
        assert e.result_ref == f"mo:{e.evidence_case_ids[0]}"


def test_unknown_rate_helper_on_empty_input():
    assert unknown_rate([]) == {}


# -- precomputed profiles (Zia runs offline; see scripts/mo_precompute.py) --
def test_precomputed_profiles_are_revalidated_on_load(dataset, tmp_path):
    """A shipped file is re-validated, never trusted just because it is on disk."""
    from kavach.analytics.mo.runner import load_precomputed

    good = extract(5001, CHAIN_SNATCH, parse_signal(ZIA_KEYWORDS, ZIA_NER)).profile
    payload = {
        "model_version": MODEL_VERSION,
        "profiles": [
            json.loads(good.model_dump_json()),
            {"case_master_id": 999, "extractor": "ZIA_TEXT_ANALYTICS"},  # malformed
        ],
    }
    path = tmp_path / "mo_profiles.json"
    path.write_text(json.dumps(payload))

    conn = connect()
    prov = ProvenanceRepository(conn)
    result = load_precomputed(conn, prov, path)

    assert result.processed == 1          # the valid one
    assert result.failed == 1             # the malformed one rejected
    assert result.zia_used == 1           # Zia attribution preserved
    stored = MoRepository(conn).all_profiles()
    assert len(stored) == 1 and stored[0].extractor == EXTRACTOR_ZIA


def test_corrupt_precomputed_file_falls_back(dataset, tmp_path):
    from kavach.analytics.mo.runner import load_precomputed

    path = tmp_path / "broken.json"
    path.write_text("{not json")
    conn = connect()
    assert load_precomputed(conn, ProvenanceRepository(conn), path) is None
