import json
import sqlite3
from pathlib import Path
from typing import Any

class Database:
    """Versioned transactional records; a separate connection per operation."""
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise RuntimeError("This database was created by a newer InferLM version.")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, "
                       "payload TEXT NOT NULL, PRIMARY KEY(kind,id))")
            db.execute("PRAGMA user_version=1")

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def put(self, kind: str, id: str, value: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) "
                       "DO UPDATE SET payload=excluded.payload",
                       (kind,id,json.dumps(value, ensure_ascii=False, allow_nan=False)))

    def get(self, kind: str, id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind,id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT payload FROM records WHERE kind=? ORDER BY rowid DESC", (kind,))]

    def delete(self, kind: str, id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind,id))

