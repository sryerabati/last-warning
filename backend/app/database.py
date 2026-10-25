"""Small versioned SQLite metadata store and atomic compressed recording storage."""
import gzip
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .campus_presets import campus_seed_records
from .schemas import ACTIONABLE, GENERIC, ScenarioConfig


def identifier():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        for folder in ["recordings", "stimuli", "neural"]:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.path = self.root / "last-warning.sqlite3"
        self.run_slots = threading.BoundedSemaphore(2)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES (1);
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(kind, id)
                );
            """)
            # Seed only once, even if a user later deletes all their warnings.
            if db.execute("SELECT 1 FROM records WHERE kind='settings' AND id='seeded'").fetchone() is None:
                seeds = [
                    ("scenarios", "riverside", ScenarioConfig().model_dump(mode="json")),
                    ("warnings", "generic", GENERIC.model_dump(mode="json")),
                    ("warnings", "actionable", ACTIONABLE.model_dump(mode="json")),
                    ("settings", "seeded", {}),
                ]
                for kind, key, value in seeds:
                    value.update(id=key, created_at=now())
                    db.execute("INSERT INTO records VALUES (?, ?, ?)", (kind, key, json.dumps(value)))
            if db.execute("SELECT 1 FROM records WHERE kind='settings' AND id='disaster-presets-v1'").fetchone() is None:
                presets = [
                    ("generic-wildfire", "Wildfire advisory", "A wildfire is burning near Riverside. Stay informed and exercise caution.", GENERIC),
                    ("actionable-wildfire", "Wildfire evacuation", "WILDFIRE EVACUATION: West District. Leave now using marked open roads. Move away from the fire toward a designated refuge. Do not cross burning streets.", ACTIONABLE),
                    ("generic-tornado", "Severe weather advisory", "Severe weather is possible in Riverside. Stay informed and exercise caution.", GENERIC),
                    ("actionable-tornado", "Tornado shelter warning", "TORNADO WARNING: Riverside. Move immediately to the nearest marked storm shelter. Stay away from windows and the tornado path. Do not attempt to outrun the storm.", ACTIONABLE),
                ]
                for key, name, text, base in presets:
                    value = {**base.model_dump(mode="json"), "name": name, "text": text, "id": key, "created_at": now()}
                    db.execute("INSERT OR IGNORE INTO records VALUES ('warnings', ?, ?)", (key, json.dumps(value)))
                db.execute("INSERT INTO records VALUES ('settings', 'disaster-presets-v1', '{}')")

            # Additive seed migration: never rewrite an existing scenario, warning or recording.
            if db.execute("SELECT 1 FROM records WHERE kind='settings' AND id='campus-presets-v1'").fetchone() is None:
                for kind, key, value in campus_seed_records():
                    value.update(id=key, created_at=now())
                    db.execute("INSERT OR IGNORE INTO records VALUES (?, ?, ?)", (kind, key, json.dumps(value)))
                db.execute("INSERT INTO records VALUES ('settings', 'campus-presets-v1', '{}')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.execute("PRAGMA busy_timeout=20000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self, kind):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, kind, key):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind, key)).fetchone()
        if row is None:
            raise KeyError(f"{kind.rstrip('s').capitalize()} not found")
        return json.loads(row[0])

    def put(self, kind, value, key=None):
        key = key or identifier()
        value = {**value, "id": key}
        value.setdefault("created_at", now())
        with self.connect() as db:
            db.execute("INSERT INTO records VALUES (?, ?, ?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload",
                       (kind, key, json.dumps(value, allow_nan=False)))
        return value

    def delete(self, kind, key):
        self.get(kind, key)
        with self.connect() as db:
            db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, key))

    def write_recording(self, run_id, recording):
        target = self.root / "recordings" / f"{run_id}.json.gz"
        temp = target.with_suffix(".tmp")
        try:
            with gzip.open(temp, "wt", encoding="utf-8", compresslevel=5) as f:
                json.dump(recording, f, separators=(",", ":"), allow_nan=False)
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)

    def recording(self, key):
        run = self.get("runs", key)
        with gzip.open(self.root / "recordings" / f"{run['id']}.json.gz", "rt", encoding="utf-8") as f:
            return json.load(f)
