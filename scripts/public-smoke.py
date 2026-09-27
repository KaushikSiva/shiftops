"""Verify a running public deployment without touching another user's workspace."""

import argparse
import json
import time
import uuid
import httpx

p = argparse.ArgumentParser()
p.add_argument("url")
p.add_argument("--require-vultr", action="store_true")
args = p.parse_args()
base = args.url.rstrip("/")
with httpx.Client(base_url=base, timeout=30) as c:
    health = c.get("/api/health")
    health.raise_for_status()
    print("Health:", health.json())
    if args.require_vultr:
        assert health.json()["deployment"] == "vultr", (
            "Backend not configured as Vultr deployment"
        )
    assert "<title>ShiftOps" in c.get("/").text
    c.post("/api/session").raise_for_status()
    r = c.post(
        "/api/missions",
        json={"scenario": "overheat", "blocked": True, "request_key": uuid.uuid4().hex},
    )
    r.raise_for_status()
    mid = r.json()["id"]
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        state = c.get("/api/state").json()
        m = next(x for x in state["missions"] if x["id"] == mid)
        if m["status"] == "awaiting_approval":
            break
        assert m["status"] not in {"escalated", "rejected", "paused"}, m
        time.sleep(0.5)
    assert m["status"] == "awaiting_approval", m
    assert m["contacts"] == 0
    r = c.post(
        f"/api/missions/{mid}/decision",
        json={"action": "approve", "note": "Automated deployment smoke test"},
    )
    r.raise_for_status()
    c.post(
        f"/api/missions/{mid}/decision", json={"action": "approve"}
    ).raise_for_status()
    state = c.get("/api/state").json()
    assert len(state["orders"]) == 1
    assert state["inventory"]["BRG-6204"] == 3
    evidence = c.get(f"/api/missions/{mid}/evidence")
    evidence.raise_for_status()
    bundle = evidence.json()
    assert len(bundle["trajectory"]) > 20
    print(
        json.dumps(
            {
                "url": base,
                "mission": mid,
                "order": state["orders"][0]["id"],
                "frames": len(bundle["trajectory"]),
                "contacts": m["contacts"],
                "status": "passed",
            },
            indent=2,
        )
    )
