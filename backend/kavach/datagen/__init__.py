"""Deterministic SYNTHETIC demo dataset generator (DATA-001 / #14, ADR-011).

Everything produced here is SYNTHETIC DEMO DATA. The generator embeds
statistical ground-truth patterns (documented in ground_truth.json) that the
analytics engines must *discover* — results are never inserted directly.

Engines must never import this package or read ground_truth.json
(enforced by tests/conformance guard, ER-007/#12).
"""
