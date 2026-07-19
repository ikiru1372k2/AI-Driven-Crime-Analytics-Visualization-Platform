"""Investigative association search (EPIC-ASSOC).

Given a seed case, find related cases across the dataset via multiple
association channels, with orthogonal attribute filters and explainable,
provenance-tagged links.
"""

from kavach.analytics.association.engine import find_associations

__all__ = ["find_associations"]
