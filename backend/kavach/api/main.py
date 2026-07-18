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


@app.get("/health/datastore")
def health_datastore() -> dict:
    """Sample scoped Data Store query from the deployed runtime (CAT-005).

    Local/dev (no Catalyst env): reports "unconfigured" honestly — there is
    no fake integration. On AppSail with project env + SDK present it runs
    one scoped ZCQL row count against CaseMaster.
    """
    from kavach.config import settings

    if not settings.catalyst_project_id:
        return {
            "status": "unconfigured",
            "detail": "CATALYST_PROJECT_ID not set — local mode (dev fixture)",
        }
    try:
        import zcatalyst_sdk  # type: ignore[import-not-found]
    except ImportError:
        return {"status": "error", "detail": "zcatalyst-sdk not installed in runtime"}
    try:
        catalyst_app = zcatalyst_sdk.initialize()
        rows = catalyst_app.zcql().execute_query(
            "SELECT COUNT(ROWID) FROM CaseMaster"
        )
        return {"status": "ok", "sample_query": "COUNT(CaseMaster)", "result": rows}
    except Exception as exc:  # pragma: no cover - live-environment path
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}
