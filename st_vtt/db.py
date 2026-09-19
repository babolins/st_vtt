"""SQLite persistence. Entities are stored as JSON documents with a revision counter."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    owner TEXT,
    playbook TEXT,
    name TEXT,
    data TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shared_sheets (
    id TEXT PRIMARY KEY,
    template TEXT NOT NULL,
    name TEXT,
    data TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT,
    data TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    author TEXT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    visibility TEXT
);
CREATE INDEX IF NOT EXISTS messages_ts ON messages(ts);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- records
    def list_records(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM records ORDER BY created_at").fetchall()
        return [self._record_row(r) for r in rows]

    def get_record(self, rid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        return self._record_row(row) if row else None

    def insert_record(self, rid: str, kind: str, doc: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO records (id, kind, name, data, revision, created_at, updated_at) VALUES (?,?,?,?,0,?,?)",
                (rid, kind, doc.get("name"), json.dumps(doc), now, now),
            )
            self._conn.commit()
        return self.get_record(rid)  # type: ignore[return-value]

    def save_record(self, rid: str, doc: dict[str, Any]) -> int:
        with self._lock:
            row = self._conn.execute("SELECT revision FROM records WHERE id=?", (rid,)).fetchone()
            rev = (row["revision"] if row else 0) + 1
            self._conn.execute(
                "UPDATE records SET data=?, name=?, revision=?, updated_at=? WHERE id=?",
                (json.dumps(doc), doc.get("name"), rev, time.time(), rid),
            )
            self._conn.commit()
        return rev

    def delete_record(self, rid: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM records WHERE id=?", (rid,))
            self._conn.commit()

    @staticmethod
    def _record_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "data": json.loads(row["data"]),
            "revision": row["revision"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ------------------------------------------------------------- characters
    def list_characters(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM characters ORDER BY created_at").fetchall()
        return [self._char_row(r) for r in rows]

    def get_character(self, cid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM characters WHERE id=?", (cid,)).fetchone()
        return self._char_row(row) if row else None

    def insert_character(self, cid: str, owner: str | None, doc: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO characters (id, owner, playbook, name, data, revision, created_at, updated_at)"
                " VALUES (?,?,?,?,?,0,?,?)",
                (cid, owner, doc.get("playbook"), doc.get("name"), json.dumps(doc), now, now),
            )
            self._conn.commit()
        return self.get_character(cid)  # type: ignore[return-value]

    def save_character(self, cid: str, doc: dict[str, Any]) -> int:
        """Persist a modified document; returns the new revision."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE characters SET data=?, playbook=?, name=?, revision=revision+1, updated_at=? WHERE id=?",
                (json.dumps(doc), doc.get("playbook"), doc.get("name"), time.time(), cid),
            )
            if cur.rowcount == 0:
                raise KeyError(cid)
            rev = self._conn.execute("SELECT revision FROM characters WHERE id=?", (cid,)).fetchone()[0]
            self._conn.commit()
        return int(rev)

    def set_character_owner(self, cid: str, owner: str | None) -> None:
        with self._lock:
            self._conn.execute("UPDATE characters SET owner=?, updated_at=? WHERE id=?", (owner, time.time(), cid))
            self._conn.commit()

    def delete_character(self, cid: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM characters WHERE id=?", (cid,))
            self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _char_row(r: sqlite3.Row) -> dict[str, Any]:
        doc = json.loads(r["data"])
        return {"id": r["id"], "owner": r["owner"], "revision": r["revision"], "updated_at": r["updated_at"], "data": doc}

    # ------------------------------------------------------------ shared sheets
    def list_shared(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM shared_sheets ORDER BY created_at").fetchall()
        return [self._shared_row(r) for r in rows]

    def get_shared(self, sid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM shared_sheets WHERE id=?", (sid,)).fetchone()
        return self._shared_row(row) if row else None

    def insert_shared(self, sid: str, template: str, doc: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO shared_sheets (id, template, name, data, revision, created_at, updated_at) VALUES (?,?,?,?,0,?,?)",
                (sid, template, doc.get("name"), json.dumps(doc), now, now),
            )
            self._conn.commit()
        return self.get_shared(sid)  # type: ignore[return-value]

    def save_shared(self, sid: str, doc: dict[str, Any]) -> int:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE shared_sheets SET data=?, name=?, revision=revision+1, updated_at=? WHERE id=?",
                (json.dumps(doc), doc.get("name"), time.time(), sid),
            )
            if cur.rowcount == 0:
                raise KeyError(sid)
            rev = self._conn.execute("SELECT revision FROM shared_sheets WHERE id=?", (sid,)).fetchone()[0]
            self._conn.commit()
        return int(rev)

    def delete_shared(self, sid: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM shared_sheets WHERE id=?", (sid,))
            self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _shared_row(r: sqlite3.Row) -> dict[str, Any]:
        return {"id": r["id"], "template": r["template"], "revision": r["revision"], "created_at": r["created_at"], "updated_at": r["updated_at"], "data": json.loads(r["data"])}

    # ---------------------------------------------------------------- messages
    def add_message(self, author: str | None, kind: str, payload: dict[str, Any], visibility: list[str] | None = None) -> dict[str, Any]:
        ts = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (ts, author, kind, payload, visibility) VALUES (?,?,?,?,?)",
                (ts, author, kind, json.dumps(payload), json.dumps(visibility) if visibility is not None else None),
            )
            self._conn.commit()
            mid = cur.lastrowid
        return {"id": mid, "ts": ts, "author": author, "kind": kind, "payload": payload, "visibility": visibility}

    def list_messages(self, limit: int = 200, before: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if before is None:
                rows = self._conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM messages WHERE id<? ORDER BY id DESC LIMIT ?", (before, limit)).fetchall()
        out = [
            {
                "id": r["id"],
                "ts": r["ts"],
                "author": r["author"],
                "kind": r["kind"],
                "payload": json.loads(r["payload"]),
                "visibility": json.loads(r["visibility"]) if r["visibility"] else None,
            }
            for r in rows
        ]
        out.reverse()
        return out

    def get_message(self, mid: int) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        if r is None:
            return None
        return {
            "id": r["id"], "ts": r["ts"], "author": r["author"], "kind": r["kind"],
            "payload": json.loads(r["payload"]),
            "visibility": json.loads(r["visibility"]) if r["visibility"] else None,
        }

    def update_message(self, mid: int, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute("UPDATE messages SET payload=? WHERE id=?", (json.dumps(payload), mid))
            self._conn.commit()

    def clear_messages(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.commit()

    # -------------------------------------------------------------------- meta
    def get_meta(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))
            self._conn.commit()

    # ------------------------------------------------------------------ export
    def export_all(self) -> dict[str, Any]:
        return {
            "characters": self.list_characters(),
            "shared": self.list_shared(),
            "messages": self.list_messages(limit=100000),
        }
