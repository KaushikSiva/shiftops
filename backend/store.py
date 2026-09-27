"""SQLite is the authoritative operation log, approvals and resource ledger."""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, session TEXT NOT NULL, request_key TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(session,request_key));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, mission TEXT NOT NULL, created REAL NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, mission TEXT UNIQUE NOT NULL, session TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS inventory(session TEXT NOT NULL, part TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>=0), PRIMARY KEY(session,part));
            CREATE TABLE IF NOT EXISTS poses(mission TEXT NOT NULL, tick INTEGER NOT NULL, sim_time REAL NOT NULL, pose TEXT NOT NULL, PRIMARY KEY(mission,tick));
            CREATE INDEX IF NOT EXISTS session_missions ON missions(session,created);
            CREATE INDEX IF NOT EXISTS mission_events ON events(mission,id);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def event(self, db, mission, kind, title, detail):
        db.execute(
            "INSERT INTO events(mission,created,kind,title,detail) VALUES(?,?,?,?,?)",
            (mission, time.time(), kind, title, json.dumps(detail)),
        )

    def save(self, db, state):
        db.execute(
            "UPDATE missions SET state=?,updated=? WHERE id=?",
            (json.dumps(state), time.time(), state["id"]),
        )

    def mission(self, mid, session=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT state FROM missions WHERE id=?"
                + (" AND session=?" if session else ""),
                (mid, session) if session else (mid,),
            ).fetchone()
        return json.loads(row["state"]) if row else None

    def view(self, session):
        with self.connect() as db:
            missions = [
                json.loads(r["state"])
                for r in db.execute(
                    "SELECT state FROM missions WHERE session=? ORDER BY created DESC LIMIT 30",
                    (session,),
                )
            ]
            orders = [
                json.loads(r["state"])
                for r in db.execute(
                    "SELECT state FROM orders WHERE session=? ORDER BY created DESC LIMIT 50",
                    (session,),
                )
            ]
            inventory = {
                r["part"]: r["quantity"]
                for r in db.execute(
                    "SELECT * FROM inventory WHERE session=?", (session,)
                )
            }
            for m in missions:
                m.pop("physics", None)
                m.pop("session", None)
                m["events"] = [
                    dict(r) | {"detail": json.loads(r["detail"])}
                    for r in db.execute(
                        "SELECT * FROM events WHERE mission=? ORDER BY id", (m["id"],)
                    )
                ]
        return {
            "missions": missions,
            "orders": orders,
            "inventory": inventory,
            "server_time": time.time(),
        }
