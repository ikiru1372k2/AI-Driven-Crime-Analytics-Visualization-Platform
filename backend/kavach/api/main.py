"""FastAPI application entry point (Catalyst AppSail target, ADR-010)."""

from fastapi import FastAPI

from kavach import __version__

app = FastAPI(
    title="KAVACH AI Analytics API",
    version=__version__,
    description=(
        "Karnataka Crime Intelligence & Analytical Platform — analytics runtime. "
        "All intelligence responses carry data classification and provenance "
        "(docs/schema/derived-intelligence-schema.md)."
    ),
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/health/deps")
def health_deps() -> dict:
    """Report availability of scientific dependencies (verified for AppSail in CAT-005)."""
    deps: dict[str, str | None] = {}
    for mod in ("numpy", "pandas", "sklearn", "networkx"):
        try:
            deps[mod] = __import__(mod).__version__
        except ImportError:
            deps[mod] = None
    return {"status": "ok", "dependencies": deps}
