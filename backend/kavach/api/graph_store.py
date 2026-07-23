"""Cached graph context for the graph API (GRAPH-003/#45).

Builds the crime graph once per process from the synthetic CSVs
(KAVACH_DATA_DIR): ingest → project (#43) → metrics (#44) over the SQLite
dev fixture, then serves adjacency lookups for BFS subgraph retrieval.
The Catalyst Data Store adapter replaces the loader behind this same
context once CAT-002 provisioning is unblocked.

Scope model: until Catalyst Authentication lands (CAT-003/#19), the
caller's district scope arrives as an explicit request parameter and is
enforced here; #19 swaps the parameter for the authenticated role's scope
without changing the enforcement logic.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from kavach.api.data import _cache_ttl, _use_datastore, data_dir
from kavach.api.ttl_cache import timed_cache
from kavach.graph import (
    CrimeGraphEdge,
    CrimeGraphNode,
    GraphRepository,
    MetricsRepository,
    compute_metrics,
    project_graph,
)
from kavach.ingestion.loader import load_dataset
from kavach.provenance import ProvenanceRepository
from kavach.repositories.dev_fixture import connect

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _manifest_path() -> Path:
    """Locate the schema manifest in both the repo and the deployed bundle.

    The repo layout (backend/kavach/api/… -> ../../../docs) does not exist on
    AppSail, where kavach/ sits at the bundle root. Getting this wrong made
    every graph/evidence endpoint 500 in production while passing locally, so
    the candidates are explicit and the error names what is missing.
    """
    env = os.environ.get("KAVACH_SCHEMA_MANIFEST")
    candidates = [
        *( [Path(env)] if env else [] ),
        _REPO_ROOT / "docs/schema/schema-manifest.json",          # repo checkout
        Path.cwd() / "docs/schema/schema-manifest.json",          # bundle root
        Path(__file__).resolve().parents[2] / "docs/schema/schema-manifest.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "schema-manifest.json not found; looked in: "
        + ", ".join(str(c) for c in candidates)
        + " (set KAVACH_SCHEMA_MANIFEST to override)"
    )


MANIFEST_PATH = _REPO_ROOT / "docs/schema/schema-manifest.json"

_lock = threading.Lock()


@dataclass
class GraphContext:
    graph: GraphRepository
    metrics: MetricsRepository
    provenance: ProvenanceRepository
    nodes: dict[str, CrimeGraphNode]
    adjacency: dict[str, list[CrimeGraphEdge]]
    node_metrics: dict[str, dict]  # request-time lookups avoid SQLite (threads)
    case_district: dict[int, int]  # CaseMasterID -> DistrictID (via station Unit)
    metrics_run_id: str
    projection_run_id: str


def _load_into(conn) -> None:
    """Load the active source into the SQLite fixture.

    CSV source loads straight from ``data_dir()``. Data Store source materialises
    the tables to a temp dir first, so the CSV-based ingestion loader runs
    unchanged, then cleans up.
    """
    if not _use_datastore():
        load_dataset(data_dir(), _manifest_path(), conn)
        return
    from kavach.api import datastore  # lazy: CSV mode never imports it
    from kavach.ingestion.loader import LOAD_ORDER

    tmp = Path(tempfile.mkdtemp(prefix="kavach-ds-"))
    try:
        datastore.materialize_csvs(tmp, LOAD_ORDER)
        load_dataset(tmp, _manifest_path(), conn)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@timed_cache(_cache_ttl)
def _build() -> GraphContext:
    # served read-only from FastAPI worker threads after this build
    conn = connect(check_same_thread=False)
    _load_into(conn)
    provenance = ProvenanceRepository(conn)
    projection = project_graph(conn, provenance)
    metrics_result = compute_metrics(conn, provenance)

    graph = GraphRepository(conn)
    nodes = {n.node_id: n for n in graph.nodes()}
    adjacency: dict[str, list[CrimeGraphEdge]] = {}
    for e in graph.edges():
        adjacency.setdefault(e.source_node_id, []).append(e)
        adjacency.setdefault(e.target_node_id, []).append(e)

    case_district = {}
    for row in conn.execute(
        "SELECT c.CaseMasterID AS cid, u.DistrictID AS did "
        "FROM CaseMaster c JOIN Unit u ON u.UnitID = c.PoliceStationID"
    ):
        if row["did"] is not None:
            case_district[int(row["cid"])] = int(row["did"])

    metrics_repo = MetricsRepository(conn)
    node_metrics = {r["node_id"]: dict(r) for r in metrics_repo.node_metrics()}

    return GraphContext(
        graph=graph,
        metrics=metrics_repo,
        provenance=provenance,
        nodes=nodes,
        adjacency=adjacency,
        node_metrics=node_metrics,
        case_district=case_district,
        metrics_run_id=metrics_result.run_id,
        projection_run_id=projection.run_id,
    )


def graph_context() -> GraphContext:
    """Process-wide graph context (thread-safe lazy build)."""
    with _lock:
        return _build()


def reset_graph_context() -> None:
    """Test hook: rebuild after KAVACH_DATA_DIR changes."""
    with _lock:
        _build.cache_clear()
