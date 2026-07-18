from fastapi.testclient import TestClient

from kavach.api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_health_deps_reports_modules() -> None:
    r = client.get("/health/deps")
    assert r.status_code == 200
    deps = r.json()["dependencies"]
    assert set(deps) == {"numpy", "pandas", "sklearn", "networkx"}
    # scientific stack must actually be importable (CAT-005 AppSail check)
    assert all(deps.values()), deps


def test_health_datastore_reports_unconfigured_locally(monkeypatch) -> None:
    """No Catalyst env → explicit 'unconfigured', never a fake success."""
    import kavach.config as config

    monkeypatch.setattr(
        config, "settings", config.Settings(env="local", catalyst_project_id=None)
    )
    r = client.get("/health/datastore")
    assert r.status_code == 200
    assert r.json()["status"] == "unconfigured"
