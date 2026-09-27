import asyncio
import json
import math
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .store import Store
from .facility import HOME, FIXTURES, BLOCKAGE, SCENARIOS, plan, route_length
from .physics import Twin

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = {"planning", "navigating", "inspecting", "awaiting_approval", "paused"}


class Intake(BaseModel):
    scenario: Literal["overheat", "leak", "stockout"] = "overheat"
    blocked: bool = True
    request_key: str = Field(min_length=8, max_length=100)
    note: str = Field(default="", max_length=1000)


class Decision(BaseModel):
    action: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)


def create_app(db_path=None, run_worker=True):
    store = Store(
        db_path or os.getenv("SHIFTOPS_DB", str(ROOT / "data/shiftops.sqlite3"))
    )
    engines = {}

    def same_control_revision(db, mission, status):
        """Check operator intent under the same lock used to commit a worker step."""
        row = db.execute(
            "SELECT state FROM missions WHERE id=?", (mission["id"],)
        ).fetchone()
        if not row:
            return False
        current = json.loads(row["state"])
        return current["status"] == status and current.get(
            "control_revision", 0
        ) == mission.get("control_revision", 0)

    async def advance(mid):
        m = store.mission(mid)
        if not m or m["status"] not in {"planning", "navigating", "inspecting"}:
            return
        try:
            if m["status"] == "planning":
                m["route"] = plan(HOME, m["scenario"]["target"], m["blocked"])
                m["route_length"] = route_length(m["route"])
                m["waypoint"] = 1
                m["status"] = "navigating"
                with store.connect() as db:
                    if not same_control_revision(db, m, "planning"):
                        return
                    store.event(
                        db,
                        mid,
                        "plan",
                        "Inspection route planned",
                        {
                            "route": m["route"],
                            "length_m": m["route_length"],
                            "clearance_m": 0.45,
                            "blocked_aisle": m["blocked"],
                            "planner": "A* with clearance and line-of-sight simplification",
                        },
                    )
                    store.event(
                        db,
                        mid,
                        "dispatch",
                        "G1 dispatched",
                        {
                            "controller": "Frozen Unitree LSTM / NumPy",
                            "physics": "MuJoCo CPU",
                            "simulation_only": True,
                        },
                    )
                    store.save(db, m)
                return
            if m["status"] == "navigating":
                revision = m.get("control_revision", 0)
                if mid not in engines or engines[mid][0] != revision:
                    engines[mid] = (
                        revision,
                        await asyncio.to_thread(Twin, m["blocked"], m.get("physics")),
                    )
                twin = engines[mid][1]
                with store.connect() as db:
                    if not same_control_revision(db, m, "navigating"):
                        engines.pop(mid, None)
                        return
                q = await asyncio.to_thread(twin.step, m["route"][m["waypoint"]])
                m["pose"] = q
                m["physics"] = twin.snapshot()
                m["distance"] = round(twin.distance, 2)
                m["sim_seconds"] = round(twin.data.time, 2)
                m["contacts"] = twin.contacts
                m["progress"] = min(
                    0.88,
                    0.1 + 0.78 * m["sim_seconds"] / max(1, m["route_length"] / 0.45),
                )
                with store.connect() as db:
                    # A pause/resume can leave the same status with newer intent.
                    # Never commit its old in-flight pose or resurrect a canceled run.
                    if not same_control_revision(db, m, "navigating"):
                        engines.pop(mid, None)
                        return
                    db.execute(
                        "INSERT OR REPLACE INTO poses VALUES(?,?,?,?)",
                        (mid, twin.counter, m["sim_seconds"], json.dumps(q)),
                    )
                    if math.dist(q[:2], m["route"][m["waypoint"]]) < 0.35:
                        store.event(
                            db,
                            mid,
                            "waypoint",
                            "Waypoint reached",
                            {
                                "position": q[:3],
                                "waypoint": m["waypoint"],
                                "simulation_seconds": m["sim_seconds"],
                            },
                        )
                        m["waypoint"] += 1
                        if m["waypoint"] == len(m["route"]):
                            m["status"] = "inspecting"
                            m["progress"] = 0.9
                            store.event(
                                db,
                                mid,
                                "arrival",
                                "Inspection position reached",
                                {
                                    "distance_to_asset_m": round(
                                        math.dist(q[:2], m["scenario"]["target"]), 3
                                    ),
                                    "obstacle_contacts": twin.contacts,
                                },
                            )
                    if m["sim_seconds"] > 180:
                        raise RuntimeError(
                            "Inspection timed out; operator review required"
                        )
                    store.save(db, m)
                return
            if m["status"] == "inspecting":
                s = m["scenario"]
                m["status"] = "awaiting_approval"
                m["progress"] = 0.95
                m["evidence"] = {
                    "sensor": s["sensor"],
                    "value": s["reading"],
                    "unit": s["unit"],
                    "threshold": s["threshold"],
                    "source": "Simulated facility sensor",
                    "asset": s["asset"],
                    "position": m["pose"][:3],
                    "observed_at": time.time(),
                    "rationale": s["observation"],
                }
                with store.connect() as db:
                    if not same_control_revision(db, m, "inspecting"):
                        return
                    quantity = db.execute(
                        "SELECT quantity FROM inventory WHERE session=? AND part=?",
                        (m["session"], s["part"]),
                    ).fetchone()[0]
                    m["proposal"] = {
                        "part": s["part"],
                        "part_name": s["part_name"],
                        "quantity": 1,
                        "in_stock": quantity,
                        "estimated_cost": s["cost"],
                        "action": "reserve" if quantity else "purchase_request",
                        "assignee": "Facilities maintenance",
                        "approval_required": True,
                    }
                    store.event(
                        db,
                        mid,
                        "evidence",
                        "Equipment observation recorded",
                        m["evidence"],
                    )
                    store.event(
                        db,
                        mid,
                        "inventory",
                        "Inventory checked",
                        {"part": s["part"], "available": quantity},
                    )
                    store.event(
                        db,
                        mid,
                        "approval",
                        "Maintenance handoff needs approval",
                        m["proposal"],
                    )
                    store.save(db, m)
                engines.pop(mid, None)
        except Exception as exc:
            with store.connect() as db:
                row = db.execute(
                    "SELECT state FROM missions WHERE id=?", (mid,)
                ).fetchone()
                latest = json.loads(row["state"]) if row else None
                if (
                    latest
                    and latest["status"] in {"planning", "navigating", "inspecting"}
                    and latest.get("control_revision", 0)
                    == m.get("control_revision", 0)
                ):
                    latest["status"] = "escalated"
                    latest["error"] = str(exc)
                    store.event(
                        db,
                        mid,
                        "error",
                        "Operator intervention required",
                        {"reason": str(exc)},
                    )
                    store.save(db, latest)
            engines.pop(mid, None)

    async def worker():
        while True:
            with store.connect() as db:
                ids = [
                    r["id"]
                    for r in db.execute(
                        "SELECT id FROM missions WHERE json_extract(state,'$.status') IN ('planning','navigating','inspecting') ORDER BY created LIMIT 4"
                    )
                ]
            # A pause or cancellation between steps must also release its model.
            # Resuming reconstructs it from the durable physics checkpoint.
            for mid in list(engines):
                if mid not in ids:
                    engines.pop(mid, None)
            for mid in ids:
                await advance(mid)
            await asyncio.sleep(float(os.getenv("SHIFTOPS_TICK_SECONDS", ".045")))

    @asynccontextmanager
    async def lifespan(app):
        # Explicit recovery, never silently claim interrupted operations completed.
        with store.connect() as db:
            for row in db.execute("SELECT state FROM missions").fetchall():
                m = json.loads(row["state"])
                if m["status"] in {"planning", "navigating", "inspecting"}:
                    m["resume_status"] = m["status"]
                    m["status"] = "paused"
                    m["control_revision"] = m.get("control_revision", 0) + 1
                    store.event(
                        db,
                        m["id"],
                        "recovery",
                        "Run paused after service restart",
                        {"action": "Review state and resume"},
                    )
                    store.save(db, m)
        task = asyncio.create_task(worker()) if run_worker else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="ShiftOps operations API", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.advance = advance

    def session(request):
        sid = request.cookies.get("shiftops_session", "")
        with store.connect() as db:
            found = db.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone()
        if not found:
            raise HTTPException(401, "Start a demo workspace first")
        return sid

    @app.middleware("http")
    async def guard(request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return Response("Cross-origin writes are not allowed", status_code=403)
            try:
                content_length = int(request.headers.get("content-length", "0") or 0)
            except ValueError:
                return Response("Invalid Content-Length", status_code=400)
            if content_length > 16384:
                return Response("Request too large", status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        with store.connect() as db:
            db.execute("SELECT 1").fetchone()
        return {
            "ok": True,
            "service": "ShiftOps",
            "storage": "SQLite WAL",
            "physics": "MuJoCo CPU / NumPy gait",
            "deployment": os.getenv("SHIFTOPS_DEPLOYMENT", "local"),
            "simulation_only": True,
        }

    @app.post("/api/session")
    def bootstrap(request: Request, response: Response):
        sid = request.cookies.get("shiftops_session")
        with store.connect() as db:
            if (
                not sid
                or not db.execute(
                    "SELECT 1 FROM sessions WHERE id=?", (sid,)
                ).fetchone()
            ):
                if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 2000:
                    raise HTTPException(503, "Demo capacity reached")
                sid = secrets.token_urlsafe(32)
                db.execute("INSERT INTO sessions VALUES(?,?)", (sid, time.time()))
                db.executemany(
                    "INSERT INTO inventory VALUES(?,?,?)",
                    [(sid, "BRG-6204", 4), (sid, "SEAL-20", 3), (sid, "FLT-H13", 0)],
                )
        response.set_cookie(
            "shiftops_session",
            sid,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            max_age=604800,
        )
        return {"workspace": "Harbor Works / Demo", "mode": "isolated_simulation"}

    @app.get("/api/facility")
    def facility():
        return {
            "name": "Harbor Works",
            "size": [13, 10],
            "home": HOME,
            "fixtures": FIXTURES,
            "blockage": BLOCKAGE,
            "scenarios": SCENARIOS,
            "robot": "Unitree G1",
            "simulation_only": True,
        }

    @app.get("/api/state")
    def state(request: Request):
        return store.view(session(request))

    @app.get("/api/events")
    async def stream(request: Request):
        sid = session(request)

        async def events():
            while not await request.is_disconnected():
                yield "data: " + json.dumps(store.view(sid)) + "\n\n"
                await asyncio.sleep(0.2)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @app.post("/api/missions", status_code=201)
    def create_mission(body: Intake, request: Request):
        sid = session(request)
        with store.connect() as db:
            previous = db.execute(
                "SELECT state FROM missions WHERE session=? AND request_key=?",
                (sid, body.request_key),
            ).fetchone()
            if previous:
                result = json.loads(previous["state"])
                if (result["scenario_key"], result["blocked"], result["note"]) != (
                    body.scenario,
                    body.blocked,
                    body.note,
                ):
                    raise HTTPException(
                        409, "Request key already used for a different inspection"
                    )
                result.pop("session", None)
                result.pop("physics", None)
                return result
            existing = [
                json.loads(r["state"])
                for r in db.execute(
                    "SELECT state FROM missions WHERE session=?", (sid,)
                )
            ]
            if any(m["status"] in ACTIVE for m in existing):
                raise HTTPException(409, "Finish or cancel the current mission first")
            if len(existing) >= 30:
                raise HTTPException(
                    429, "This demo workspace has reached its 30-run limit"
                )
            count = db.execute(
                "SELECT count(*) FROM missions WHERE json_extract(state,'$.status') IN ('planning','navigating','inspecting')"
            ).fetchone()[0]
            if count >= 4:
                raise HTTPException(
                    429, "Simulation workers are busy. Try again shortly."
                )
            mid = uuid.uuid4().hex[:12]
            m = {
                "id": mid,
                "session": sid,
                "scenario_key": body.scenario,
                "scenario": SCENARIOS[body.scenario],
                "note": body.note,
                "blocked": body.blocked,
                "status": "planning",
                "control_revision": 0,
                "created": time.time(),
                "pose": [1, 1, 0.793, 1, 0, 0, 0] + [-0.1, 0, 0, 0.3, -0.2, 0] * 2,
                "route": [],
                "progress": 0,
                "distance": 0,
                "sim_seconds": 0,
                "contacts": 0,
            }
            db.execute(
                "INSERT INTO missions VALUES(?,?,?,?,?,?)",
                (mid, sid, body.request_key, json.dumps(m), time.time(), time.time()),
            )
            store.event(
                db,
                mid,
                "intake",
                "Incident accepted",
                {
                    "asset": m["scenario"]["asset"],
                    "priority": m["scenario"]["priority"],
                    "source": "Demo scenario",
                    "note": body.note,
                },
            )
            return {k: v for k, v in m.items() if k != "session"}

    @app.post("/api/missions/{mid}/stop")
    def stop(mid: str, request: Request):
        sid = session(request)
        with store.connect() as db:
            row = db.execute(
                "SELECT state FROM missions WHERE id=? AND session=?", (mid, sid)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Mission not found")
            m = json.loads(row["state"])
            if m["status"] == "paused":
                return {"status": "paused"}
            if m["status"] not in {"planning", "navigating", "inspecting"}:
                raise HTTPException(409, "This mission is not moving")
            m["resume_status"] = m["status"]
            m["status"] = "paused"
            m["control_revision"] = m.get("control_revision", 0) + 1
            store.event(
                db,
                mid,
                "stop",
                "Operator paused simulation",
                {"pose": m["pose"], "scope": "This simulated mission"},
            )
            store.save(db, m)
        return {"status": "paused"}

    @app.post("/api/missions/{mid}/resume")
    def resume(mid: str, request: Request):
        sid = session(request)
        with store.connect() as db:
            row = db.execute(
                "SELECT state FROM missions WHERE id=? AND session=?", (mid, sid)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Mission not found")
            m = json.loads(row["state"])
            if m["status"] != "paused":
                raise HTTPException(409, "Only paused missions can resume")
            count = db.execute(
                "SELECT count(*) FROM missions WHERE json_extract(state,'$.status') IN ('planning','navigating','inspecting')"
            ).fetchone()[0]
            if count >= 4:
                raise HTTPException(
                    429, "Simulation workers are busy. Try again shortly."
                )
            m["status"] = m.pop("resume_status")
            m["control_revision"] = m.get("control_revision", 0) + 1
            store.event(
                db,
                mid,
                "resume",
                "Operator resumed simulation",
                {"from_persisted_state": True},
            )
            store.save(db, m)
        return {"status": m["status"]}

    @app.post("/api/missions/{mid}/cancel")
    def cancel(mid: str, request: Request):
        sid = session(request)
        with store.connect() as db:
            row = db.execute(
                "SELECT state FROM missions WHERE id=? AND session=?", (mid, sid)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Mission not found")
            m = json.loads(row["state"])
            if m["status"] == "canceled":
                return {"status": "canceled"}
            if m["status"] not in ACTIVE:
                raise HTTPException(409, "This mission has already finished")
            m["status"] = "canceled"
            m["control_revision"] = m.get("control_revision", 0) + 1
            m.pop("resume_status", None)
            store.event(
                db,
                mid,
                "canceled",
                "Operator canceled inspection",
                {"inventory_reserved": False, "work_order_created": False},
            )
            store.save(db, m)
        return {"status": "canceled"}

    @app.post("/api/missions/{mid}/decision")
    def decision(mid: str, body: Decision, request: Request):
        sid = session(request)
        with store.connect() as db:
            row = db.execute(
                "SELECT state FROM missions WHERE id=? AND session=?", (mid, sid)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Mission not found")
            m = json.loads(row["state"])
            if m["status"] == "complete" and body.action == "approve":
                return {"status": "complete", "order": m["order"]}
            if m["status"] == "rejected" and body.action == "reject":
                return {"status": "rejected"}
            if m["status"] != "awaiting_approval":
                raise HTTPException(
                    409, "Inspection evidence is required before approval"
                )
            if body.action == "reject":
                m["status"] = "rejected"
                store.event(
                    db,
                    mid,
                    "rejected",
                    "Operator rejected handoff",
                    {"note": body.note},
                )
                store.save(db, m)
                return {"status": "rejected"}
            proposal = m["proposal"]
            available = db.execute(
                "SELECT quantity FROM inventory WHERE session=? AND part=?",
                (sid, proposal["part"]),
            ).fetchone()[0]
            if proposal["action"] == "reserve" and not available:
                raise HTTPException(
                    409, "Inventory changed. Review stock before approving."
                )
            if proposal["action"] == "reserve":
                db.execute(
                    "UPDATE inventory SET quantity=quantity-1 WHERE session=? AND part=?",
                    (sid, proposal["part"]),
                )
            order = {
                "id": "WO-" + mid[:6].upper(),
                "mission": mid,
                "asset": m["scenario"]["asset"],
                "title": m["scenario"]["name"],
                "status": "Repair pending"
                if proposal["action"] == "reserve"
                else "Purchase request pending",
                "proposal": proposal,
                "evidence": m["evidence"],
                "approved_at": time.time(),
                "approval_note": body.note,
                "simulation_only": True,
            }
            db.execute(
                "INSERT INTO orders VALUES(?,?,?,?,?)",
                (order["id"], mid, sid, json.dumps(order), time.time()),
            )
            m["status"] = "complete"
            m["progress"] = 1
            m["order"] = order["id"]
            m["completed"] = time.time()
            store.event(
                db,
                mid,
                "approved",
                "Operator approved maintenance handoff",
                {"note": body.note},
            )
            store.event(
                db,
                mid,
                "order",
                "Work order committed",
                {
                    "order": order["id"],
                    "status": order["status"],
                    "inventory_reserved": proposal["action"] == "reserve",
                    "external_purchase_sent": False,
                },
            )
            store.save(db, m)
        return {"status": "complete", "order": order["id"]}

    @app.get("/api/missions/{mid}/evidence")
    def evidence(mid: str, request: Request):
        sid = session(request)
        m = store.mission(mid, sid)
        if not m:
            raise HTTPException(404, "Mission not found")
        view = store.view(sid)
        mission = next(x for x in view["missions"] if x["id"] == mid)
        mission.pop("session", None)
        with store.connect() as db:
            poses = [
                {"time": r["sim_time"], "qpos": json.loads(r["pose"])}
                for r in db.execute(
                    "SELECT * FROM poses WHERE mission=? ORDER BY tick", (mid,)
                )
            ]
        data = {
            "schema": "shiftops.evidence.v1",
            "simulation_only": True,
            "mission": mission,
            "orders": [o for o in view["orders"] if o["mission"] == mid],
            "trajectory": poses,
        }
        return Response(
            json.dumps(data, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="shiftops-{mid}.json"'
            },
        )

    @app.get("/api/missions/{mid}/replay")
    def replay(mid: str, request: Request):
        sid = session(request)
        if not store.mission(mid, sid):
            raise HTTPException(404, "Mission not found")
        with store.connect() as db:
            poses = [
                {"time": r["sim_time"], "qpos": json.loads(r["pose"])}
                for r in db.execute(
                    "SELECT * FROM poses WHERE mission=? ORDER BY tick", (mid,)
                )
            ]
        return {"mission": mid, "source": "Recorded MuJoCo poses", "frames": poses}

    dist = ROOT / "web/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app


app = create_app()
