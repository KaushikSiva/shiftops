import asyncio
import json
import math
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.facility import HOME, SCENARIOS, plan, line_clear
from backend.physics import Twin


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
    assert client.post(f"/api/missions/{m['id']}/cancel").status_code == 409
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
        assert other.post(f"/api/missions/{first['id']}/cancel").status_code == 404


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


@pytest.mark.parametrize("commands", [("stop",), ("stop", "resume"), ("cancel",)])
@pytest.mark.parametrize("fault", [False, True])
def test_operator_command_wins_over_inflight_physics(
    app, client, monkeypatch, commands, fault
):
    """Hold a real worker step while HTTP commands change the persisted run."""
    mid = create(client)["id"]
    for _ in range(3):
        asyncio.run(app.state.advance(mid))
    before = app.state.store.mission(mid)
    before_replay = client.get(f"/api/missions/{mid}/replay").json()
    step = Twin.step
    entered, release = threading.Event(), threading.Event()

    def held_step(twin, target):
        entered.set()
        assert release.wait(10), "Test did not release the physics worker"
        if fault:
            raise RuntimeError("Fault in superseded worker step")
        return step(twin, target)

    async def race():
        task = asyncio.create_task(app.state.advance(mid))
        try:
            assert await asyncio.to_thread(entered.wait, 10)
            for command in commands:
                response = await asyncio.to_thread(
                    client.post, f"/api/missions/{mid}/{command}"
                )
                assert response.status_code == 200, response.text
        finally:
            release.set()
            await task

    with monkeypatch.context() as patch:
        patch.setattr(Twin, "step", held_step)
        asyncio.run(race())

    saved = app.state.store.mission(mid)
    expected_status = {"stop": "paused", "resume": "navigating", "cancel": "canceled"}[
        commands[-1]
    ]
    assert saved["status"] == expected_status
    assert saved["pose"] == before["pose"]
    assert saved["physics"] == before["physics"]
    assert "error" not in saved
    assert client.get(f"/api/missions/{mid}/replay").json() == before_replay
    events = client.get(f"/api/missions/{mid}/evidence").json()["mission"]["events"]
    assert not any(e["kind"] == "error" for e in events)

    if expected_status == "canceled":
        asyncio.run(app.state.advance(mid))
        assert app.state.store.mission(mid) == saved
    else:
        if expected_status == "paused":
            assert client.post(f"/api/missions/{mid}/resume").status_code == 200
        # The resumed engine must start from the last committed checkpoint, not
        # the discarded in-memory step (including the controller's LSTM state).
        reference = Twin(before["blocked"], before["physics"])
        expected_pose = reference.step(before["route"][before["waypoint"]])
        asyncio.run(app.state.advance(mid))
        resumed = app.state.store.mission(mid)
        assert resumed["pose"] == pytest.approx(expected_pose, abs=1e-10)
        assert resumed["physics"] == reference.snapshot()


@pytest.mark.parametrize(
    "phase", ["planning", "navigating", "paused", "awaiting_approval"]
)
def test_cancel_retains_evidence_and_releases_workspace(app, client, phase):
    mid = create(client)["id"]
    if phase == "awaiting_approval":
        inspect(app, mid)
    elif phase in {"navigating", "paused"}:
        for _ in range(3):
            asyncio.run(app.state.advance(mid))
        if phase == "paused":
            assert client.post(f"/api/missions/{mid}/stop").status_code == 200
    before = client.get("/api/state").json()
    response = client.post(f"/api/missions/{mid}/cancel")
    assert response.status_code == 200
    assert client.post(f"/api/missions/{mid}/cancel").json() == response.json()
    asyncio.run(app.state.advance(mid))
    after = client.get("/api/state").json()
    assert after["inventory"] == before["inventory"]
    assert after["orders"] == []
    canceled = after["missions"][0]
    assert canceled["status"] == "canceled"
    assert canceled["pose"] == before["missions"][0]["pose"]
    assert canceled.get("evidence") == before["missions"][0].get("evidence")
    assert sum(e["kind"] == "canceled" for e in canceled["events"]) == 1
    assert client.post(f"/api/missions/{mid}/resume").status_code == 409
    assert (
        client.post(
            f"/api/missions/{mid}/decision", json={"action": "approve"}
        ).status_code
        == 409
    )
    assert create(client, "leak")["id"] != mid


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
