"""MO-001 (#38): schema v1 validation contract tests."""

import pytest

from kavach.analytics.mo.schema import (
    SIMILARITY_ATTRIBUTES,
    UNKNOWN,
    MoValidationError,
    validate_extraction,
)


def payload(**overrides) -> dict:
    """Worked example: chain-snatching narrative extraction."""
    base = {
        "case_master_id": 5501,
        "schema_version": "mo-schema-v1",
        "extractor": "QUICKML_LLM",
        "model_version": "quickml-test-1",
        "extracted_at": "2026-07-14T22:00:00+05:30",
        "offender_count": {"value": 2, "confidence": 0.95, "source_span": [0, 19]},
        "mobility": {"value": "motorcycle", "confidence": 0.91, "source_span": [34, 44]},
        "approach_method": {"value": "mobile_approach", "confidence": 0.8},
        "crime_action": {"value": "snatching", "confidence": 0.97},
        "target_type": {"value": "gold_chain", "confidence": 0.93},
        "escape_direction": {"value": "Tumakuru Road", "confidence": 0.88},
        "time_context": {"value": "night", "confidence": 0.7},
        "weapon_involved": {"value": UNKNOWN, "confidence": 1.0},
    }
    base.update(overrides)
    return base


def test_valid_extraction_accepted_with_spans_and_unknown():
    p = validate_extraction(payload())
    assert p.mobility.value == "motorcycle"
    assert p.weapon_involved.value == UNKNOWN
    assert p.offender_count.source_span == (0, 19)


def test_unknown_accepted_for_every_attribute():
    unknowns = {
        k: {"value": UNKNOWN, "confidence": 1.0}
        for k in ["offender_count", "mobility", "approach_method", "crime_action",
                  "target_type", "escape_direction", "time_context", "weapon_involved"]
    }
    p = validate_extraction(payload(**unknowns))
    assert p.known_similarity_attributes() == {}


def test_out_of_vocabulary_rejected():
    with pytest.raises(MoValidationError, match="vocabulary"):
        validate_extraction(payload(mobility={"value": "helicopter", "confidence": 0.9}))


def test_invented_attribute_rejected():
    bad = payload()
    bad["gang_affiliation"] = {"value": "yes", "confidence": 0.9}
    with pytest.raises(MoValidationError):
        validate_extraction(bad)


def test_bad_confidence_rejected():
    with pytest.raises(MoValidationError):
        validate_extraction(payload(crime_action={"value": "snatching", "confidence": 1.7}))


def test_offender_count_bands():
    validate_extraction(payload(offender_count={"value": 1, "confidence": 0.5}))
    with pytest.raises(MoValidationError):
        validate_extraction(payload(offender_count={"value": 0, "confidence": 0.5}))
    with pytest.raises(MoValidationError):
        validate_extraction(payload(offender_count={"value": "two", "confidence": 0.5}))


def test_missing_field_and_malformed_span_rejected():
    incomplete = payload()
    del incomplete["time_context"]
    with pytest.raises(MoValidationError):
        validate_extraction(incomplete)
    with pytest.raises(MoValidationError):
        validate_extraction(payload(mobility={"value": "car", "confidence": 0.5,
                                              "source_span": [10, 10]}))


def test_escape_direction_excluded_from_similarity_features():
    assert "escape_direction" not in SIMILARITY_ATTRIBUTES
    p = validate_extraction(payload())
    assert "escape_direction" not in p.known_similarity_attributes()
    assert set(p.known_similarity_attributes()) == {
        "offender_count", "mobility", "approach_method", "crime_action",
        "target_type", "time_context",
    }  # weapon_involved is UNKNOWN in the fixture


def test_wrong_schema_version_rejected():
    with pytest.raises(MoValidationError):
        validate_extraction(payload(schema_version="mo-schema-v2"))
