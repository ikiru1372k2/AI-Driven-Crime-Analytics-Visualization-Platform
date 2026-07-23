"""FastAPI application entry point (Catalyst AppSail target, ADR-010)."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from kavach import __version__
from kavach.api.audit_routes import router as audit_router
from kavach.api.evidence_routes import router as evidence_router
from kavach.api.graph_routes import router as graph_router
from kavach.api.mo_routes import router as mo_router
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
# port for the dev path. Hosted: the Catalyst-served Web Client origin
# (*.catalystserverless.in) is allowed by regex so the deployed app never hits a
# CORS wall even if KAVACH_ALLOWED_ORIGINS (comma-separated env, set on AppSail)
# is unset; extra explicit origins can still be added through that env.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1):\d+"
        r"|https://[a-z0-9.-]+\.catalystserverless\.in"
    ),
    allow_origins=[
        o.strip()
        for o in os.environ.get("KAVACH_ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(graph_router)
app.include_router(audit_router)
app.include_router(evidence_router)
app.include_router(mo_router)


_WEB_DIR = Path(os.environ.get("KAVACH_WEB_DIR", Path(__file__).resolve().parents[2] / "web"))


@app.on_event("startup")
def _seed_dev_auth() -> None:
    """Seed the demo role assignments so demo identities resolve to a role and
    scope. Runs for the local dev path (x-kavach-dev-user) and for a deployed
    demo (KAVACH_DEMO_IDENTITY) — both are explicit opt-ins; with neither set
    nothing is seeded and every identity must come from Catalyst Auth."""
    from kavach.auth import role_repo
    from kavach.auth.demo_users import seed_demo_assignments
    from kavach.auth.validator import demo_identity, is_catalyst_runtime

    local_dev = os.environ.get("KAVACH_DEV_AUTH") == "1" and not is_catalyst_runtime()
    if local_dev or demo_identity():
        seed_demo_assignments(role_repo())


@app.on_event("startup")
def _start_warmer() -> None:
    """Start the background snapshot warmer (PERF-001).

    A no-op in CSV mode; in Data Store mode it keeps an in-memory snapshot fresh
    on a daemon thread so no request ever blocks on the ~30s cold Data Store read
    (which exceeds AppSail's 30s HTTP limit and caused the timeout death-spiral).
    """
    from kavach.api import warmer

    warmer.start()


@app.on_event("shutdown")
def _stop_warmer() -> None:
    from kavach.api import warmer

    warmer.stop()


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


@app.get("/health/snapshot")
def health_snapshot() -> dict:
    """Report the background warmer's published snapshot (PERF-001).

    ``ready`` false in CSV mode is expected — the warmer only runs in Data Store
    mode; CSV requests read the bundled files directly. In Data Store mode a
    ``source: "datastore"`` snapshot means live data is being served off the
    request path; ``source: "csv"`` means the warm-start bootstrap is still up
    while the first live read completes.
    """
    from kavach.api import snapshot, warmer

    return {"status": "ok", "snapshot": snapshot.status(), "warmer": warmer.status()}


@app.get("/health/datastore")
def health_datastore(request: Request) -> dict:
    """Sample scoped Data Store query from the deployed runtime (CAT-005).

    Local/dev (no Catalyst env): reports "unconfigured" honestly — there is
    no fake integration. On AppSail the SDK is initialized with the incoming
    request's Catalyst headers (it has no ambient credential; initializing
    without them fails with "Catalyst headers are empty"), then runs one
    scoped ZCQL row count against CaseMaster.
    """
    import os

    if not (os.environ.get("CATALYST_PROJECT_ID") or os.environ.get("KAVACH_ENV") == "catalyst"):
        return {
            "status": "unconfigured",
            "detail": "not running on Catalyst — local mode (dev fixture)",
        }
    try:
        import zcatalyst_sdk  # type: ignore[import-not-found]
    except ImportError:
        return {"status": "error", "detail": "zcatalyst-sdk not installed in runtime"}
    try:
        catalyst_app = zcatalyst_sdk.initialize(req=dict(request.headers))
        rows = catalyst_app.zcql().execute_query(
            "SELECT COUNT(ROWID) FROM CaseMaster"
        )
        return {"status": "ok", "sample_query": "COUNT(CaseMaster)", "result": rows}
    except Exception as exc:  # pragma: no cover - live-environment path
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}


# -- console (single-origin hosting) ------------------------------------------
# Registered LAST, deliberately: a mount at "/" matches any path not already
# claimed, so declaring it earlier swallows /health and every later route.
#
# The built SPA ships inside the deployment bundle and is served by THIS app,
# so console and API share one origin. Two reasons:
#
#  1. No CORS. Hosting the console separately made every API call
#     cross-origin, and AppSail's proxy appends its own
#     Access-Control-Allow-Origin on top of the app's — browsers reject the
#     duplicated header ("contains multiple values"), so the hosted console
#     could not reach its API at all.
#  2. The console answers at "/" instead of "/app/index.html".
#
# No-op in local dev, where Vite serves the UI and this directory is absent.
if (_WEB_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="console")
