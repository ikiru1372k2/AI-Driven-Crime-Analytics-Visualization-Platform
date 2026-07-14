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
    assert set(r.json()["dependencies"]) == {"numpy", "pandas", "sklearn", "networkx"}
