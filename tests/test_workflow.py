import asyncio
import json
import math
import uuid

import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.facility import HOME, SCENARIOS, plan, line_clear


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "ops.db", run_worker=False)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        assert c.post("/api/session").status_code == 200
        yield c


def create(client, scenario="overheat", **kwargs):
    r = client.post(
        "/api/missions",
        json={"request_key": uuid.uuid4().hex, "scenario": scenario, **kwargs},
    )
    assert r.status_code == 201, r.text
    return r.json()


def inspect(app, mid):
    async def run():
        for _ in range(1200):
            await app.state.advance(mid)
            m = app.state.store.mission(mid)
            if m["status"] not in {"planning", "navigating", "inspecting"}:
                return m
        pytest.fail("Mission did not finish inspection")

    return asyncio.run(run())


@pytest.mark.parametrize("scenario", ["overheat", "leak", "stockout"])
def test_real_physics_to_approved_work_order(app, client, scenario):
    m = create(client, scenario)
    done = inspect(app, m["id"])
    assert done["status"] == "awaiting_approval", done.get("error")
    assert done["contacts"] == 0
    assert math.dist(done["pose"][:2], SCENARIOS[scenario]["target"]) < 0.35
    assert done["pose"][2] > 0.45
    assert done["sim_seconds"] > 5
    assert client.get("/api/state").json()["orders"] == []
    first = client.post(f"/api/missions/{m['id']}/decision", json={"action": "approve"})
    assert first.status_code == 200
    again = client.post(f"/api/missions/{m['id']}/decision", json={"action": "approve"})
    assert again.json() == first.json()
    view = client.get("/api/state").json()
    assert len(view["orders"]) == 1
    part = SCENARIOS[scenario]["part"]
    expected = {"BRG-6204": 3, "SEAL-20": 2, "FLT-H13": 0}[part]
    assert view["inventory"][part] == expected
    assert view["orders"][0]["status"] == (
        "Purchase request pending" if scenario == "stockout" else "Repair pending"
    )
    bundle = client.get(f"/api/missions/{m['id']}/evidence").json()
    assert bundle["simulation_only"] and len(bundle["mission"]["events"]) >= 9
    assert "session" not in json.dumps(bundle)


def test_isolation_and_idempotency(app, client):
    body = {"request_key": "stable-key-123", "scenario": "leak"}
    first = client.post("/api/missions", json=body).json()
    assert client.post("/api/missions", json=body).json()["id"] == first["id"]
    assert (
        client.post("/api/missions", json=body | {"scenario": "overheat"}).status_code
        == 409
    )
    assert "session" not in first
    assert (
        client.post(
            f"/api/missions/{first['id']}/decision", json={"action": "approve"}
        ).status_code
        == 409
    )
    with TestClient(app) as other:
        other.post("/api/session")
        assert other.get("/api/state").json()["missions"] == []
        assert other.get(f"/api/missions/{first['id']}/evidence").status_code == 404
        assert other.post(f"/api/missions/{first['id']}/stop").status_code == 404


def test_rejection_does_not_reserve(app, client):
    mid = create(client)["id"]
    inspect(app, mid)
    before = client.get("/api/state").json()["inventory"]
    r = client.post(
        f"/api/missions/{mid}/decision",
        json={"action": "reject", "note": "Maintenance window unavailable"},
    )
    assert r.status_code == 200
    view = client.get("/api/state").json()
    assert view["inventory"] == before and not view["orders"]
    assert (
        client.post(
            f"/api/missions/{mid}/decision", json={"action": "approve"}
        ).status_code
        == 409
    )


def test_stop_resume_preserves_physics(app, client):
    mid = create(client)["id"]
    for _ in range(5):
        asyncio.run(app.state.advance(mid))
    before = app.state.store.mission(mid)["pose"]
    assert client.post(f"/api/missions/{mid}/stop").status_code == 200
    asyncio.run(app.state.advance(mid))
    assert app.state.store.mission(mid)["pose"] == before
    assert client.post(f"/api/missions/{mid}/resume").status_code == 200
    done = inspect(app, mid)
    assert done["status"] == "awaiting_approval", done.get("error")


def test_restart_pauses_and_retains_data(tmp_path):
    path = tmp_path / "restart.db"
    app = create_app(path, run_worker=False)
    with TestClient(app) as c:
        c.post("/api/session")
        cookie = c.cookies.get("shiftops_session")
        mid = create(c)["id"]
        asyncio.run(app.state.advance(mid))
        asyncio.run(app.state.advance(mid))
        pose = app.state.store.mission(mid)["pose"]
    restarted = create_app(path, run_worker=False)
    with TestClient(restarted) as c:
        c.cookies.set("shiftops_session", cookie)
        m = c.get("/api/state").json()["missions"][0]
        assert m["status"] == "paused" and m["pose"] == pose
        assert any(e["kind"] == "recovery" for e in m["events"])
        assert c.post(f"/api/missions/{mid}/resume").status_code == 200
        assert inspect(restarted, mid)["status"] == "awaiting_approval"


def test_route_clearance_and_invalid_targets():
    for scenario in SCENARIOS.values():
        for blocked in [True, False]:
            route = plan(HOME, scenario["target"], blocked)
            assert all(line_clear(a, b, blocked) for a, b in zip(route, route[1:]))
    with pytest.raises(ValueError):
        plan(HOME, [4, 4])


def test_invalid_requests_and_cross_origin(app, client):
    assert (
        client.post(
            "/api/missions", json={"scenario": "unknown", "request_key": "xx"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/session", headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )
    create(client)
    assert (
        client.post(
            "/api/missions", json={"scenario": "leak", "request_key": uuid.uuid4().hex}
        ).status_code
        == 409
    )
    with TestClient(app) as unauth:
        assert unauth.get("/api/state").status_code == 401
