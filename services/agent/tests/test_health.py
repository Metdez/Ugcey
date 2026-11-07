from fastapi.testclient import TestClient

from ugecy.main import app


def test_healthz():
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "ugecy-agent"}
