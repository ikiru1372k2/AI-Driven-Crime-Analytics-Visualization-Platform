"""Catalyst platform adapters (QuickML, LLM Serving).

Thin clients over the Catalyst SDK / OAuth endpoints. Each degrades to a
typed ``*Unavailable`` error so callers can fall back honestly rather than
crash or fabricate a result (ADR-001: Catalyst-native, credentials from env).
"""
