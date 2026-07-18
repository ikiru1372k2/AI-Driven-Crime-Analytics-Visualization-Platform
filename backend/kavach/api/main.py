"""FastAPI application entry point (Catalyst AppSail target, ADR-010)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kavach import __version__
from kavach.api.routes import router as analytics_router

app = FastAPI(
    title="KAVACH AI Analytics API",
    version=__version__,
    description=(
        "Karnataka Crime Intelligence & Analytical Platform — analytics runtime. "
        "All intelligence responses carry data classification and provenance "
        "(docs/schema/derived-intelligence-schema.md)."
    ),
)

# Local dev: the Vite frontend runs on a separate origin. Vite falls through to
# the next free port (5173, 5174, …) when one is taken, so allow any localhost
# port for the dev path. (The Catalyst deployment serves same-origin — CAT-*.)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)


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
