"""KAVACH AI analytics runtime.

Layering (see docs/architecture/target-architecture.md):
- domain/        ER-mapped source entities (exact FIR schema, docs/schema/er-conformance-matrix.md)
- repositories/  Catalyst Data Store access (+ local dev fixture)
- provenance/    IntelligenceRun / IntelligenceEvidence framework
- analytics/     engines: hotspot, trends, mo, graph, entity, anomaly, risk
- ingestion/     dataset validation + load
- api/           FastAPI routers (deployed on Catalyst AppSail)
"""

__version__ = "0.1.0"
